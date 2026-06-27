from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from synapse.bench.cache import DiskCache, stable_key
from synapse.bench.judge import grade_completion, judge_pair
from synapse.bench.loaders import load_config, load_suite
from synapse.bench.ollama_client import OllamaBenchClient, bench_client_from_judge_config
from synapse.bench.report import write_outputs
from synapse.bench.schema import BenchmarkConfig, CompletionRecord, PairwiseJudgment, PromptCase, RawOrderJudgment, RubricScore
from synapse.bench.systems import run_system


def run_benchmark(config_path: str, suite_path: str, no_cache: bool = False) -> Path:
    config = load_config(config_path)
    suite = load_suite(suite_path)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_id = f"{config.run_name}-{timestamp}"
    run_dir = Path(config.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cache = DiskCache(config.cache_dir)
    completions = collect_completions(run_id, config, suite, cache, no_cache)
    if not any(not item.error for item in completions):
        raise RuntimeError("Benchmark failed: all completions failed. No report was written.")

    judgments = collect_judgments(run_id, config, suite, completions, cache, no_cache)
    if not judgments:
        raise RuntimeError("Benchmark failed: no pairwise judgments were produced. No report was written.")

    rubric_scores = collect_rubric_scores(run_id, config, suite, completions, cache, no_cache) if config.rubric_grading else []

    write_outputs(
        run_dir,
        config.systems,
        completions,
        judgments,
        rubric_scores,
        config.judge_min_stability,
        config.judge.models or [config.judge.model],
    )
    (run_dir / "config_snapshot.json").write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    return run_dir


def should_cache_rubric_score(score: RubricScore) -> bool:
    return bool(score.valid and score.score is not None and not score.error)


def collect_completions(
    run_id: str,
    config: BenchmarkConfig,
    suite: list[PromptCase],
    cache: DiskCache,
    no_cache: bool,
) -> list[CompletionRecord]:
    records: list[CompletionRecord] = []
    client = OllamaBenchClient(timeout_s=max(system.timeout_s for system in config.systems) if config.systems else 120)
    pending = []
    for case in suite:
        for seed in config.seeds:
            for system in config.systems:
                key = stable_key("completion", system.id, system.kind, system.model, system.profile, case.id, case.prompt, seed)
                cached = None if no_cache else cache.get("completions", key)
                if cached:
                    cached["cache_hit"] = True
                    records.append(CompletionRecord(**cached))
                    continue
                pending.append((key, system, case, seed))
    if config.concurrency <= 1:
        for key, system, case, seed in pending:
            record = run_system(run_id, system, case, seed, ollama_client=client)
            if not record.error:
                cache.set("completions", key, record)
            records.append(record)
    else:
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            futures = {
                executor.submit(run_system, run_id, system, case, seed, None): key
                for key, system, case, seed in pending
            }
            for future in as_completed(futures):
                record = future.result()
                if not record.error:
                    cache.set("completions", futures[future], record)
                records.append(record)
    return records


def collect_judgments(
    run_id: str,
    config: BenchmarkConfig,
    suite: list[PromptCase],
    completions: list[CompletionRecord],
    cache: DiskCache,
    no_cache: bool,
) -> list[PairwiseJudgment]:
    judgments: list[PairwiseJudgment] = []
    completion_by_key = {(item.prompt_id, item.seed, item.system_id): item for item in completions}
    client = bench_client_from_judge_config(config.judge)
    pending = []
    for case in suite:
        for seed in config.seeds:
            pairs = system_pairs(
                [system.id for system in config.systems],
                config.baseline_system,
                config.pairwise_baselines_only,
                config.comparison_pairs,
            )
            for system_a, system_b in pairs:
                left = completion_by_key[(case.id, seed, system_a)]
                right = completion_by_key[(case.id, seed, system_b)]
                if left.error or right.error:
                    continue
                key = stable_key("judge", config.judge.model, config.judge.models, config.rubric_fallback, case.id, seed, system_a, system_b, left.text, right.text)
                cached = None if no_cache else cache.get("judgments", key)
                if cached:
                    judgments.append(PairwiseJudgment(
                        **{**cached, "raw_orders": [
                            RawOrderJudgment(judge_model=item.get("judge_model", cached.get("judge_model", "")), **{k: v for k, v in item.items() if k != "judge_model"})
                            for item in cached.get("raw_orders", [])
                        ]}
                    ))
                    continue
                pending.append((key, case, seed, left, right))
    if config.concurrency <= 1:
        for key, case, seed, left, right in pending:
            judgment = judge_pair(run_id, case, seed, left, right, config.judge, client, config.rubric_fallback)
            if not judgment.error:
                cache.set("judgments", key, judgment)
            judgments.append(judgment)
    else:
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            futures = {
                executor.submit(judge_pair, run_id, case, seed, left, right, config.judge, client, config.rubric_fallback): key
                for key, case, seed, left, right in pending
            }
            for future in as_completed(futures):
                judgment = future.result()
                if not judgment.error:
                    cache.set("judgments", futures[future], judgment)
                judgments.append(judgment)
    return judgments


def collect_rubric_scores(
    run_id: str,
    config: BenchmarkConfig,
    suite: list[PromptCase],
    completions: list[CompletionRecord],
    cache: DiskCache,
    no_cache: bool,
) -> list[RubricScore]:
    scores: list[RubricScore] = []
    case_by_id = {case.id: case for case in suite}
    client = bench_client_from_judge_config(config.judge)
    pending = []
    for completion in completions:
        if completion.error:
            continue
        case = case_by_id[completion.prompt_id]
        key = stable_key("rubric", config.judge.model, completion.prompt_id, completion.seed, completion.system_id, completion.text)
        cached = None if no_cache else cache.get("rubric", key)
        if cached:
            scores.append(RubricScore(**cached))
            continue
        pending.append((key, case, completion))
    if config.concurrency <= 1:
        for key, case, completion in pending:
            score = grade_completion(run_id, case, completion.seed, completion, config.judge, client)
            if should_cache_rubric_score(score):
                cache.set("rubric", key, score)
            scores.append(score)
    else:
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            futures = {
                executor.submit(grade_completion, run_id, case, completion.seed, completion, config.judge, client): key
                for key, case, completion in pending
            }
            for future in as_completed(futures):
                score = future.result()
                if should_cache_rubric_score(score):
                    cache.set("rubric", futures[future], score)
                scores.append(score)
    return scores


def system_pairs(
    system_ids: list[str],
    baseline: str | None,
    baselines_only: bool,
    comparison_pairs: list[list[str]] | None = None,
) -> list[tuple[str, str]]:
    if len(system_ids) < 2:
        return []
    if comparison_pairs:
        return [
            (left, right)
            for left, right in comparison_pairs
            if left in system_ids and right in system_ids and left != right
        ]
    baseline = baseline or system_ids[-1]
    if baselines_only:
        return [(system_id, baseline) for system_id in system_ids if system_id != baseline]
    pairs = []
    for index, left in enumerate(system_ids):
        for right in system_ids[index + 1:]:
            pairs.append((left, right))
    return pairs

