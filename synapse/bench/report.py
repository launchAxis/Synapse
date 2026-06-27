from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from synapse.bench.schema import CompletionRecord, PairwiseJudgment, RubricScore, SystemConfig
from synapse.bench.stats import wilson_interval, win_rate
from synapse.bench.verdict import benchmark_verdict_to_dict, build_benchmark_verdict, summarize_rubrics


def write_outputs(
    run_dir: Path,
    systems: list[SystemConfig],
    completions: list[CompletionRecord],
    judgments: list[PairwiseJudgment],
    rubric_scores: list[RubricScore] | None = None,
    judge_min_stability: float = 0.70,
    judge_models: list[str] | None = None,
) -> None:
    rubric_scores = rubric_scores or []
    fallback_scores = [score for item in judgments for score in item.rubric_fallback_scores]
    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "completions.jsonl", completions)
    write_jsonl(run_dir / "pairwise_judgments.jsonl", judgments)
    write_jsonl(run_dir / "rubric_scores.jsonl", rubric_scores)
    write_jsonl(run_dir / "rubric_fallback_scores.jsonl", fallback_scores)
    write_system_metrics(run_dir / "system_metrics.csv", systems, completions, rubric_scores)
    write_pairwise_metrics(run_dir / "pairwise_metrics.csv", judgments)
    write_human_review_files(run_dir / "human_review_sheet.csv", run_dir / "human_review_key.csv", judgments, completions)
    verdict = build_benchmark_verdict(systems, completions, judgments, rubric_scores, judge_min_stability)
    (run_dir / "benchmark_verdict.json").write_text(
        json.dumps(benchmark_verdict_to_dict(verdict), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(
        summary_markdown(systems, completions, judgments, rubric_scores, judge_min_stability, judge_models or []),
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[object]) -> None:
    lines = [json.dumps(to_jsonable(record), ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines), encoding="utf-8")


def to_jsonable(record: object) -> object:
    if is_dataclass(record):
        return asdict(record)
    if isinstance(record, dict):
        return record
    return record


def record_field(record: object, name: str, default: object = None) -> object:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def write_system_metrics(path: Path, systems: list[SystemConfig], completions: list[CompletionRecord], rubric_scores: list[RubricScore]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["system_id", "label", "completions", "errors", "median_latency_s", "mean_model_calls", "mean_rubric"])
        writer.writeheader()
        for system in systems:
            items = [item for item in completions if item.system_id == system.id]
            scores = [item.score for item in rubric_scores if item.system_id == system.id and item.valid and item.score is not None]
            latencies = sorted(item.latency_s for item in items)
            median = latencies[len(latencies) // 2] if latencies else 0.0
            calls = sum(item.model_calls for item in items) / len(items) if items else 0.0
            mean_rubric = sum(scores) / len(scores) if scores else 0.0
            writer.writerow({
                "system_id": system.id,
                "label": system.label,
                "completions": len(items),
                "errors": sum(1 for item in items if item.error),
                "median_latency_s": f"{median:.3f}",
                "mean_model_calls": f"{calls:.2f}",
                "mean_rubric": f"{mean_rubric:.2f}" if scores else "",
            })


def write_pairwise_metrics(path: Path, judgments: list[PairwiseJudgment]) -> None:
    rows = pairwise_rows(judgments)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "system_id", "baseline_id", "wins", "losses", "ties", "win_rate", "wilson_low", "wilson_high", "unstable_order_rate"
        ])
        writer.writeheader()
        writer.writerows(rows)


def write_human_review_files(
    sheet_path: Path,
    key_path: Path,
    judgments: list[PairwiseJudgment],
    completions: list[CompletionRecord],
) -> None:
    completion_by_key = {(item.prompt_id, item.seed, item.system_id): item for item in completions}
    with sheet_path.open("w", newline="", encoding="utf-8") as sheet, key_path.open("w", newline="", encoding="utf-8") as key:
        sheet_writer = csv.DictWriter(sheet, fieldnames=[
            "review_id", "prompt_id", "seed", "prompt", "answer_a", "answer_b", "human_winner", "human_notes"
        ])
        key_writer = csv.DictWriter(key, fieldnames=[
            "review_id", "prompt_id", "seed", "answer_a_system", "answer_b_system", "auto_winner", "unstable_order", "used_rubric_fallback"
        ])
        sheet_writer.writeheader()
        key_writer.writeheader()
        for index, item in enumerate(judgments, start=1):
            if item.unstable_order or item.final_winner == "tie" or index % 5 == 0:
                left = completion_by_key.get((item.prompt_id, item.seed, item.system_a))
                right = completion_by_key.get((item.prompt_id, item.seed, item.system_b))
                if not left or not right:
                    continue
                review_id = f"R{index:04d}"
                answer_a, answer_b, answer_a_system, answer_b_system = blinded_answers(item, left, right)
                sheet_writer.writerow({
                    "review_id": review_id,
                    "prompt_id": item.prompt_id,
                    "seed": item.seed,
                    "prompt": left.metadata.get("prompt", "") or "",
                    "answer_a": answer_a,
                    "answer_b": answer_b,
                    "human_winner": "",
                    "human_notes": "",
                })
                key_writer.writerow({
                    "review_id": review_id,
                    "prompt_id": item.prompt_id,
                    "seed": item.seed,
                    "answer_a_system": answer_a_system,
                    "answer_b_system": answer_b_system,
                    "auto_winner": item.final_winner,
                    "unstable_order": item.unstable_order,
                    "used_rubric_fallback": item.used_rubric_fallback,
                })


def blinded_answers(
    judgment: PairwiseJudgment,
    left: CompletionRecord,
    right: CompletionRecord,
) -> tuple[str, str, str, str]:
    import random

    rng = random.Random(f"{judgment.prompt_id}:{judgment.seed}:{judgment.system_a}:{judgment.system_b}:human")
    if rng.choice([True, False]):
        return left.text, right.text, judgment.system_a, judgment.system_b
    return right.text, left.text, judgment.system_b, judgment.system_a


def pairwise_rows(judgments: list[PairwiseJudgment]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[PairwiseJudgment]] = {}
    for item in judgments:
        grouped.setdefault((item.system_a, item.system_b), []).append(item)

    rows = []
    for (system_id, baseline_id), items in sorted(grouped.items()):
        wins = sum(1 for item in items if item.final_winner == system_id)
        losses = sum(1 for item in items if item.final_winner == baseline_id)
        ties = sum(1 for item in items if item.final_winner == "tie")
        rate = win_rate(wins, losses, ties)
        low, high = wilson_interval(wins + 0.5 * ties, len(items))
        unstable = sum(1 for item in items if item.unstable_order) / len(items) if items else 0.0
        rows.append({
            "system_id": system_id,
            "baseline_id": baseline_id,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": f"{rate:.3f}",
            "wilson_low": f"{low:.3f}",
            "wilson_high": f"{high:.3f}",
            "unstable_order_rate": f"{unstable:.3f}",
        })
    return rows


def summary_markdown(
    systems: list[SystemConfig],
    completions: list[CompletionRecord],
    judgments: list[PairwiseJudgment],
    rubric_scores: list[RubricScore] | None = None,
    judge_min_stability: float = 0.70,
    judge_models: list[str] | None = None,
) -> str:
    rubric_scores = rubric_scores or []
    judge_models = judge_models or sorted({order.judge_model for item in judgments for order in item.raw_orders})
    verdict = build_benchmark_verdict(systems, completions, judgments, rubric_scores, judge_min_stability)
    lines = ["# Synapse Benchmark Summary", "", "## Systems", ""]
    for system in systems:
        lines.append(f"- `{system.id}`: {system.label} ({system.kind})")
    lines.extend(["", "## Benchmark Verdict", ""])
    lines.append(f"**Run verdict:** `{verdict.verdict}`")
    lines.append("")
    lines.append(verdict.reason)
    lines.extend(["", "| System | Baseline | Verdict | Evidence | Reason |", "|---|---|---|---|---|"])
    for item in verdict.comparisons:
        lines.append(
            f"| `{item.system_id}` | `{item.baseline_id}` | `{item.verdict}` | "
            f"{item.evidence} | {item.reason} |"
        )
    if rubric_scores:
        lines.extend(["", "## Rubric Ranking", ""])
        lines.extend(["| System | Mean score | Std dev | Valid scores | Invalid scores |", "|---|---:|---:|---:|---:|"])
        for summary in sorted(
            summarize_rubrics(systems, rubric_scores),
            key=lambda item: (-(item.mean_score or -1), item.system_id),
        ):
            mean_text = f"{summary.mean_score:.2f}" if summary.mean_score is not None else ""
            std_text = f"{summary.std_dev:.2f}" if summary.std_dev is not None else ""
            lines.append(
                f"| `{summary.system_id}` | {mean_text} | {std_text} | "
                f"{summary.valid_scores} | {summary.invalid_scores} |"
            )
    lines.extend(["", "## Pairwise Metrics", "", "| System | Baseline | Win rate | 95% Wilson CI | W/L/T | Unstable order |", "|---|---|---:|---:|---:|---:|"])
    for row in pairwise_rows(judgments):
        lines.append(
            f"| `{row['system_id']}` | `{row['baseline_id']}` | {row['win_rate']} | "
            f"{row['wilson_low']}-{row['wilson_high']} | {row['wins']}/{row['losses']}/{row['ties']} | {row['unstable_order_rate']} |"
        )
        if float(row["unstable_order_rate"]) > (1 - judge_min_stability):
            lines.append(
                f"\n> Judge unreliable for this pair; do not interpret win rate. Treat pairwise results as diagnostic. "
                f"`{row['system_id']}` vs `{row['baseline_id']}` unstable_order_rate={row['unstable_order_rate']}.\n"
            )
    lines.extend(["", "## Diagnostics", ""])
    lines.append("- Judge models used: " + (", ".join(f"`{model}`" for model in judge_models) if judge_models else "none"))
    lines.append(f"- Completions: {len(completions)}")
    lines.append(f"- Pairwise judgments: {len(judgments)}")
    lines.append(f"- Rubric scores: {len(rubric_scores)}")
    overall_unstable = sum(1 for item in judgments if item.unstable_order) / len(judgments) if judgments else 0.0
    visible_a = sum(1 for item in judgments for order in item.raw_orders if order.winner == "A")
    visible_b = sum(1 for item in judgments for order in item.raw_orders if order.winner == "B")
    visible_tie = sum(1 for item in judgments for order in item.raw_orders if order.winner == "tie")
    fallback_count = sum(1 for item in judgments if item.used_rubric_fallback)
    fallback_scores = [score for item in judgments for score in item.rubric_fallback_scores]
    invalid_fallback_scores = sum(1 for score in fallback_scores if not record_field(score, "valid", False))
    lines.append(f"- Overall unstable_order_rate: {overall_unstable:.3f}")
    lines.append(f"- Visible Answer A choices: {visible_a}")
    lines.append(f"- Visible Answer B choices: {visible_b}")
    lines.append(f"- Visible tie choices: {visible_tie}")
    visible_non_tie = visible_a + visible_b
    if visible_non_tie:
        leading_label = "A" if visible_a >= visible_b else "B"
        leading_count = max(visible_a, visible_b)
        if leading_count / visible_non_tie >= 0.80 and visible_non_tie >= 2:
            lines.append(
                f"- Position-bias warning: visible Answer {leading_label} received "
                f"{leading_count}/{visible_non_tie} non-tie raw judge choices."
            )
    lines.append(f"- Diagnostic rubric fallbacks used: {fallback_count}")
    lines.append(f"- Rubric fallback score records: {len(fallback_scores)}")
    lines.append(f"- Invalid rubric fallback scores: {invalid_fallback_scores}")
    if fallback_scores:
        lines.append("- Rubric fallback is diagnostic only; unstable pairwise comparisons still award no pairwise win.")
    if overall_unstable > 0.75:
        lines.extend(["", "## Inconclusive", ""])
        lines.append("Overall unstable_order_rate is above 0.75. Mark this run as inconclusive; unstable pairwise comparisons award no win and win rates should not be used for release decisions.")
    error_counts = {
        system.id: sum(1 for item in completions if item.system_id == system.id and item.error)
        for system in systems
    }
    if any(error_counts.values()):
        lines.extend(["", "## Warnings", ""])
        lines.append("Some systems had completion errors. Treat benchmark results as incomplete.")
        for system_id, count in error_counts.items():
            lines.append(f"- `{system_id}` errors: {count}")
    lines.append("- Human review sheet includes unstable-order cases, ties, and a small systematic sample.")
    return "\n".join(lines) + "\n"
