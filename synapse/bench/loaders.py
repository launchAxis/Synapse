from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from synapse.bench.schema import BenchmarkConfig, JudgeConfig, PromptCase, SystemConfig


def load_data(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"{path} is not JSON. Install PyYAML from requirements-bench.txt to read YAML files."
        ) from exc
    return yaml.safe_load(text)


def load_suite(path: str | Path) -> list[PromptCase]:
    data = load_data(path)
    return [
        PromptCase(
            id=str(item["id"]),
            title=str(item.get("title", item["id"])),
            category=str(item.get("category", "general")),
            difficulty=str(item.get("difficulty", "medium")),
            prompt=str(item["prompt"]),
            expected_traits=list(item.get("expected_traits", [])),
            max_output_tokens=item.get("max_output_tokens"),
        )
        for item in data.get("prompts", [])
    ]


def load_config(path: str | Path) -> BenchmarkConfig:
    data = load_data(path)
    judge_data = data.get("judge", {})
    return BenchmarkConfig(
        run_name=str(data.get("run_name", "synapse-benchmark")),
        seeds=[int(seed) for seed in data.get("seeds", [1])],
        systems=[SystemConfig(**item) for item in data.get("systems", [])],
        judge=JudgeConfig(**judge_data),
        output_dir=str(data.get("output_dir", "bench_runs")),
        cache_dir=str(data.get("cache_dir", ".bench_cache")),
        baseline_system=data.get("baseline_system"),
        concurrency=int(data.get("concurrency", 1)),
        pairwise_baselines_only=bool(data.get("pairwise_baselines_only", True)),
        comparison_pairs=[list(pair) for pair in data.get("comparison_pairs", [])],
        rubric_grading=bool(data.get("rubric_grading", False)),
        rubric_fallback=bool(data.get("rubric_fallback", False)),
        judge_min_stability=float(data.get("judge_min_stability", 0.70)),
    )
