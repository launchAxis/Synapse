from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptCase:
    id: str
    title: str
    category: str
    difficulty: str
    prompt: str
    expected_traits: list[str] = field(default_factory=list)
    max_output_tokens: int | None = None


@dataclass
class SystemConfig:
    id: str
    kind: str
    label: str
    model: str | None = None
    command: str | None = None
    profile: str | None = None
    system_prompt: str = "Answer the user's request directly and clearly."
    temperature: float = 0.2
    max_output_tokens: int = 900
    timeout_s: int = 300


@dataclass
class JudgeConfig:
    kind: str = "ollama_pairwise"
    model: str = "qwen2.5:3b"
    models: list[str] = field(default_factory=list)
    temperature: float = 0.0
    timeout_s: int = 120
    retry_attempts: int = 0
    retry_backoff_s: float = 2.0
    retry_max_sleep_s: float = 30.0
    min_request_interval_s: float = 0.0


@dataclass
class BenchmarkConfig:
    run_name: str
    seeds: list[int]
    systems: list[SystemConfig]
    judge: JudgeConfig
    output_dir: str = "bench_runs"
    cache_dir: str = ".bench_cache"
    baseline_system: str | None = None
    concurrency: int = 1
    pairwise_baselines_only: bool = True
    comparison_pairs: list[list[str]] = field(default_factory=list)
    rubric_grading: bool = False
    rubric_fallback: bool = False
    judge_min_stability: float = 0.70


@dataclass
class CompletionRecord:
    run_id: str
    system_id: str
    prompt_id: str
    seed: int
    text: str
    latency_s: float
    model_calls: int = 1
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    cache_hit: bool = False
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawOrderJudgment:
    judge_model: str
    swapped: bool
    winner: str
    mapped_winner: str
    rationale: str
    error: str | None = None


@dataclass
class PairwiseJudgment:
    run_id: str
    prompt_id: str
    seed: int
    system_a: str
    system_b: str
    final_winner: str
    confidence: float
    rationale: str
    unstable_order: bool
    raw_orders: list[RawOrderJudgment]
    category: str
    difficulty: str
    error: str | None = None
    used_rubric_fallback: bool = False
    rubric_fallback_note: str = ""
    rubric_fallback_scores: list["RubricScore"] = field(default_factory=list)


@dataclass
class RubricScore:
    run_id: str
    prompt_id: str
    seed: int
    system_id: str
    score: float | None
    task_fulfillment: int | None
    correctness: int | None
    usefulness: int | None
    structure: int | None
    constraint_handling: int | None
    insight: int | None
    rationale: str
    raw_response: str = ""
    valid: bool = True
    error: str | None = None
    source: str = "rubric"
