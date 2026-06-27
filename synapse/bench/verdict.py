from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt

from synapse.bench.schema import CompletionRecord, PairwiseJudgment, RubricScore, SystemConfig
from synapse.bench.stats import wilson_interval, win_rate


MIN_VALID_RUBRIC_SCORES = 3
RUBRIC_LEAD_THRESHOLD = 5.0


@dataclass
class RubricSummary:
    system_id: str
    valid_scores: int
    invalid_scores: int
    mean_score: float | None
    std_dev: float | None


@dataclass
class ComparisonVerdict:
    system_id: str
    baseline_id: str
    verdict: str
    reason: str
    evidence: str
    rubric_score_delta: float | None
    system_mean_rubric: float | None
    baseline_mean_rubric: float | None
    valid_rubric_scores: dict[str, int]
    judgments: int
    win_rate: float | None
    wilson_low: float | None
    wilson_high: float | None
    unstable_order_rate: float | None
    completion_errors: dict[str, int]


@dataclass
class BenchmarkVerdict:
    verdict: str
    reason: str
    comparisons: list[ComparisonVerdict]
    rubric_summaries: list[RubricSummary]
    limitations: list[str]


def build_benchmark_verdict(
    systems: list[SystemConfig],
    completions: list[CompletionRecord],
    judgments: list[PairwiseJudgment],
    rubric_scores: list[RubricScore],
    judge_min_stability: float = 0.70,
) -> BenchmarkVerdict:
    rubric_summaries = summarize_rubrics(systems, rubric_scores)
    comparisons = [
        comparison_verdict(pair, items, completions, rubric_scores, judge_min_stability)
        for pair, items in grouped_judgments(judgments).items()
    ]
    limitations = [
        "Rubric scores are model-judged diagnostics, not human proof.",
        "Pairwise win rates remain diagnostic when order instability is high.",
        "Small prompt counts can only support cautious release decisions.",
    ]

    if not completions or all(item.error for item in completions):
        verdict = "invalid"
        reason = "No successful completions were available."
    elif not comparisons:
        verdict = "invalid"
        reason = "No system comparisons were available."
    elif all(item.verdict == "invalid" for item in comparisons):
        verdict = "invalid"
        reason = "All comparisons were invalid."
    elif any(item.verdict in {"inconclusive", "invalid"} for item in comparisons):
        verdict = "inconclusive"
        reason = "At least one comparison lacked enough reliable evidence."
    elif any(item.verdict == "mixed" for item in comparisons):
        verdict = "mixed"
        reason = "At least one comparison had close or conflicting evidence."
    else:
        verdict = "credible"
        reason = "All comparisons had enough evidence for a directional verdict."

    return BenchmarkVerdict(
        verdict=verdict,
        reason=reason,
        comparisons=sorted(comparisons, key=lambda item: (item.system_id, item.baseline_id)),
        rubric_summaries=rubric_summaries,
        limitations=limitations,
    )


def benchmark_verdict_to_dict(verdict: BenchmarkVerdict) -> dict[str, object]:
    return asdict(verdict)


def summarize_rubrics(systems: list[SystemConfig], rubric_scores: list[RubricScore]) -> list[RubricSummary]:
    summaries = []
    for system in systems:
        valid = [
            item.score
            for item in rubric_scores
            if item.system_id == system.id and item.valid and item.score is not None
        ]
        invalid = [
            item
            for item in rubric_scores
            if item.system_id == system.id and (not item.valid or item.score is None)
        ]
        mean = sum(valid) / len(valid) if valid else None
        variance = sum((score - mean) ** 2 for score in valid) / len(valid) if valid and mean is not None else None
        summaries.append(
            RubricSummary(
                system_id=system.id,
                valid_scores=len(valid),
                invalid_scores=len(invalid),
                mean_score=round(mean, 2) if mean is not None else None,
                std_dev=round(sqrt(variance), 2) if variance is not None else None,
            )
        )
    return summaries


def comparison_verdict(
    pair: tuple[str, str],
    judgments: list[PairwiseJudgment],
    completions: list[CompletionRecord],
    rubric_scores: list[RubricScore],
    judge_min_stability: float,
) -> ComparisonVerdict:
    system_id, baseline_id = pair
    system_errors = completion_errors(completions, system_id)
    baseline_errors = completion_errors(completions, baseline_id)
    system_scores = valid_scores(rubric_scores, system_id)
    baseline_scores = valid_scores(rubric_scores, baseline_id)
    system_mean = mean(system_scores)
    baseline_mean = mean(baseline_scores)
    rubric_delta = (
        round(system_mean - baseline_mean, 2)
        if system_mean is not None and baseline_mean is not None
        else None
    )

    wins = sum(1 for item in judgments if item.final_winner == system_id)
    losses = sum(1 for item in judgments if item.final_winner == baseline_id)
    ties = sum(1 for item in judgments if item.final_winner == "tie")
    rate = win_rate(wins, losses, ties) if judgments else None
    low, high = wilson_interval(wins + 0.5 * ties, len(judgments)) if judgments else (None, None)
    unstable = sum(1 for item in judgments if item.unstable_order) / len(judgments) if judgments else None
    pairwise_reliable = unstable is not None and unstable <= (1 - judge_min_stability)

    evidence = "rubric" if len(system_scores) >= MIN_VALID_RUBRIC_SCORES and len(baseline_scores) >= MIN_VALID_RUBRIC_SCORES else "pairwise"
    if not judgments and evidence != "rubric":
        verdict = "invalid"
        reason = "No pairwise judgments or valid rubric scores were available."
    elif system_errors == len([item for item in completions if item.system_id == system_id]) and system_errors:
        verdict = "invalid"
        reason = f"`{system_id}` had no successful completions."
    elif baseline_errors == len([item for item in completions if item.system_id == baseline_id]) and baseline_errors:
        verdict = "invalid"
        reason = f"`{baseline_id}` had no successful completions."
    elif evidence == "rubric":
        verdict, reason = rubric_verdict(rubric_delta, rate, low, high, pairwise_reliable)
    elif not pairwise_reliable:
        verdict = "inconclusive"
        reason = "Pairwise judging was order-unstable and rubric scores were insufficient."
    elif low is not None and low > 0.5:
        verdict = "credible_win"
        reason = "Stable pairwise evidence favored the system."
    elif high is not None and high < 0.5:
        verdict = "credible_loss"
        reason = "Stable pairwise evidence favored the baseline."
    else:
        verdict = "mixed"
        reason = "Stable pairwise evidence was too close for a directional claim."

    return ComparisonVerdict(
        system_id=system_id,
        baseline_id=baseline_id,
        verdict=verdict,
        reason=reason,
        evidence=evidence,
        rubric_score_delta=rubric_delta,
        system_mean_rubric=round(system_mean, 2) if system_mean is not None else None,
        baseline_mean_rubric=round(baseline_mean, 2) if baseline_mean is not None else None,
        valid_rubric_scores={system_id: len(system_scores), baseline_id: len(baseline_scores)},
        judgments=len(judgments),
        win_rate=round(rate, 3) if rate is not None else None,
        wilson_low=round(low, 3) if low is not None else None,
        wilson_high=round(high, 3) if high is not None else None,
        unstable_order_rate=round(unstable, 3) if unstable is not None else None,
        completion_errors={system_id: system_errors, baseline_id: baseline_errors},
    )


def rubric_verdict(
    rubric_delta: float | None,
    win_rate_value: float | None,
    wilson_low: float | None,
    wilson_high: float | None,
    pairwise_reliable: bool,
) -> tuple[str, str]:
    if rubric_delta is None:
        return "inconclusive", "Rubric scores could not be compared."
    if abs(rubric_delta) < RUBRIC_LEAD_THRESHOLD:
        return "mixed", "Rubric scores were too close for a directional claim."
    if pairwise_reliable and win_rate_value is not None:
        if rubric_delta > 0 and wilson_high is not None and wilson_high < 0.5:
            return "mixed", "Rubric and stable pairwise evidence disagreed."
        if rubric_delta < 0 and wilson_low is not None and wilson_low > 0.5:
            return "mixed", "Rubric and stable pairwise evidence disagreed."
    if rubric_delta > 0:
        return "credible_win", "Valid rubric scores favored the system."
    return "credible_loss", "Valid rubric scores favored the baseline."


def grouped_judgments(judgments: list[PairwiseJudgment]) -> dict[tuple[str, str], list[PairwiseJudgment]]:
    grouped: dict[tuple[str, str], list[PairwiseJudgment]] = {}
    for item in judgments:
        grouped.setdefault((item.system_a, item.system_b), []).append(item)
    return grouped


def valid_scores(rubric_scores: list[RubricScore], system_id: str) -> list[float]:
    return [
        item.score
        for item in rubric_scores
        if item.system_id == system_id and item.valid and item.score is not None
    ]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def completion_errors(completions: list[CompletionRecord], system_id: str) -> int:
    return sum(1 for item in completions if item.system_id == system_id and item.error)
