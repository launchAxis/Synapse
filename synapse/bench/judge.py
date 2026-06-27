from __future__ import annotations

import random
import re

from synapse.bench.ollama_client import OllamaBenchClient, bench_client_from_judge_config
from synapse.bench.schema import CompletionRecord, JudgeConfig, PairwiseJudgment, PromptCase, RawOrderJudgment, RubricScore
from synapse.utils import dedent


def judge_pair(
    run_id: str,
    case: PromptCase,
    seed: int,
    left: CompletionRecord,
    right: CompletionRecord,
    judge_config: JudgeConfig,
    client: OllamaBenchClient | None = None,
    use_rubric_fallback: bool = False,
) -> PairwiseJudgment:
    client = client or bench_client_from_judge_config(judge_config)
    rng = random.Random(f"{case.id}:{seed}:{left.system_id}:{right.system_id}")
    orders: list[RawOrderJudgment] = []
    per_judge_votes = []
    for judge_index, model in enumerate(judge_models(judge_config)):
        first_left = rng.choice([True, False])
        judge_orders = [
            make_order(case, seed + judge_index * 100, left, right, first_left, False, model, judge_config, client),
            make_order(case, seed + judge_index * 100, left, right, not first_left, True, model, judge_config, client),
        ]
        orders.extend(judge_orders)
        mapped = [item.mapped_winner for item in judge_orders]
        per_judge_votes.append(mapped[0] if mapped[0] == mapped[1] else "tie")

    unstable = has_order_instability(orders)
    final = "tie" if unstable else majority_vote(per_judge_votes)
    confidence = 0.5 if unstable else vote_confidence(per_judge_votes, final)
    used_rubric_fallback = False
    rubric_fallback_note = ""
    fallback_scores = []
    if unstable and use_rubric_fallback:
        fallback_winner, fallback_note, fallback_scores = rubric_fallback_winner(
            run_id, case, seed, left, right, judge_config, client
        )
        rubric_fallback_note = fallback_note
        if fallback_winner is not None:
            used_rubric_fallback = True
            rubric_fallback_note = f"No pairwise win awarded; {fallback_note}"
    errors = [item.error for item in orders if item.error]
    rationale = orders[0].rationale if orders else "No judge orders produced."
    if unstable:
        rationale = f"Order-unstable comparison; no pairwise win awarded. {rationale}"
    return PairwiseJudgment(
        run_id=run_id,
        prompt_id=case.id,
        seed=seed,
        system_a=left.system_id,
        system_b=right.system_id,
        final_winner=final,
        confidence=confidence,
        rationale=rationale,
        unstable_order=unstable,
        raw_orders=orders,
        category=case.category,
        difficulty=case.difficulty,
        error="; ".join(errors) if errors else None,
        used_rubric_fallback=used_rubric_fallback,
        rubric_fallback_note=rubric_fallback_note,
        rubric_fallback_scores=fallback_scores,
    )


def make_order(
    case: PromptCase,
    seed: int,
    left: CompletionRecord,
    right: CompletionRecord,
    left_is_a: bool,
    swapped: bool,
    judge_model: str,
    judge_config: JudgeConfig,
    client: OllamaBenchClient,
) -> RawOrderJudgment:
    answer_a = left.text if left_is_a else right.text
    answer_b = right.text if left_is_a else left.text
    prompt = judge_prompt(case.prompt, answer_a, answer_b)
    try:
        response, _latency, _metadata = client.chat(
            judge_model,
            prompt,
            options={"temperature": judge_config.temperature, "seed": seed + (1 if swapped else 0)},
        )
        winner, rationale = parse_judge_response(response)
        error = None
    except Exception as exc:
        winner, rationale = "tie", f"Judge failed: {exc}"
        error = str(exc)

    if winner == "A":
        mapped = left.system_id if left_is_a else right.system_id
    elif winner == "B":
        mapped = right.system_id if left_is_a else left.system_id
    else:
        mapped = "tie"
    return RawOrderJudgment(judge_model=judge_model, swapped=swapped, winner=winner, mapped_winner=mapped, rationale=rationale, error=error)


def judge_prompt(user_prompt: str, answer_a: str, answer_b: str) -> str:
    return dedent(f"""
    You are a blind benchmark judge. Compare Answer A and Answer B for the user prompt.
    Do not choose Answer A or Answer B by default. Answer order is randomized and may be swapped.
    Your winner must reflect a material quality difference, not answer position, style, length, or verbosity.
    If the answers are close, have different but comparable tradeoffs, or the difference is minor, choose tie.
    Prefer task fulfillment, correctness, usefulness, structure, constraint handling, and insight.

    User prompt:
    {user_prompt}

    Answer A:
    {answer_a}

    Answer B:
    {answer_b}

    Respond with exactly these labels:
    A_STRENGTHS:
    A_WEAKNESSES:
    B_STRENGTHS:
    B_WEAKNESSES:
    FINAL_WINNER: A, B, or tie
    REASON: one concise reason
    """)


def parse_judge_response(text: str) -> tuple[str, str]:
    cleaned = text.replace("**", "")
    match = re.search(r"(?:FINAL_WINNER|WINNER)\s*:\s*(A|B|tie)", cleaned, flags=re.I)
    reason_match = re.search(r"REASON\s*:\s*(.*)", cleaned, flags=re.I | re.S)
    winner = match.group(1).lower() if match else "tie"
    if winner in {"a", "b"}:
        winner = winner.upper()
    reason = reason_match.group(1).strip() if reason_match else cleaned.strip()
    return winner, reason or "No reason provided."


def judge_models(judge_config: JudgeConfig) -> list[str]:
    return judge_config.models or [judge_config.model]


def has_order_instability(orders: list[RawOrderJudgment]) -> bool:
    by_model: dict[str, list[RawOrderJudgment]] = {}
    for order in orders:
        by_model.setdefault(order.judge_model, []).append(order)
    return any(len(items) >= 2 and items[0].mapped_winner != items[1].mapped_winner for items in by_model.values())


def majority_vote(votes: list[str]) -> str:
    counts = {vote: votes.count(vote) for vote in set(votes)}
    if not counts:
        return "tie"
    top_count = max(counts.values())
    winners = [vote for vote, count in counts.items() if count == top_count]
    if len(winners) != 1:
        return "tie"
    return winners[0]


def vote_confidence(votes: list[str], winner: str) -> float:
    if not votes or winner == "tie":
        return 0.5
    return votes.count(winner) / len(votes)


def rubric_fallback_winner(
    run_id: str,
    case: PromptCase,
    seed: int,
    left: CompletionRecord,
    right: CompletionRecord,
    judge_config: JudgeConfig,
    client: OllamaBenchClient,
) -> tuple[str | None, str, list[RubricScore]]:
    left_score = grade_completion(run_id, case, seed, left, judge_config, client, source="rubric_fallback")
    right_score = grade_completion(run_id, case, seed + 1, right, judge_config, client, source="rubric_fallback")
    scores = [left_score, right_score]
    if not left_score.valid or not right_score.valid or left_score.score is None or right_score.score is None:
        return None, "Diagnostic rubric fallback invalid: one or both rubric scores could not be parsed.", scores
    if abs(left_score.score - right_score.score) < 1.0:
        return "tie", f"Diagnostic rubric fallback: scores too close ({left_score.score} vs {right_score.score}).", scores
    if left_score.score > right_score.score:
        return left.system_id, f"Diagnostic rubric fallback: {left.system_id} scored {left_score.score} vs {right.system_id} {right_score.score}.", scores
    return right.system_id, f"Diagnostic rubric fallback: {right.system_id} scored {right_score.score} vs {left.system_id} {left_score.score}.", scores


def grade_completion(
    run_id: str,
    case: PromptCase,
    seed: int,
    completion: CompletionRecord,
    judge_config: JudgeConfig,
    client: OllamaBenchClient | None = None,
    source: str = "rubric",
) -> RubricScore:
    client = client or bench_client_from_judge_config(judge_config)
    response = ""
    try:
        response, _latency, _metadata = client.chat(
            judge_config.model,
            rubric_prompt(case.prompt, completion.text),
            options={"temperature": judge_config.temperature, "seed": seed},
        )
        values = parse_rubric_response(response)
    except Exception as exc:
        values = {"RATIONALE": f"Rubric judge failed: {exc}", "ERROR": str(exc)}

    valid = all(label in values for label in RUBRIC_SCORE_LABELS)
    weighted = None
    error = values.get("ERROR")
    if valid:
        weighted = (
            values["TASK_FULFILLMENT"] * 0.30
            + values["CORRECTNESS"] * 0.20
            + values["USEFULNESS"] * 0.20
            + values["STRUCTURE"] * 0.15
            + values["CONSTRAINT_HANDLING"] * 0.10
            + values["INSIGHT"] * 0.05
        ) * 10
    elif not error:
        error = "Missing or unparseable rubric labels."
    return RubricScore(
        run_id=run_id,
        prompt_id=case.id,
        seed=seed,
        system_id=completion.system_id,
        score=round(weighted, 2) if weighted is not None else None,
        task_fulfillment=values.get("TASK_FULFILLMENT"),
        correctness=values.get("CORRECTNESS"),
        usefulness=values.get("USEFULNESS"),
        structure=values.get("STRUCTURE"),
        constraint_handling=values.get("CONSTRAINT_HANDLING"),
        insight=values.get("INSIGHT"),
        rationale=str(values.get("RATIONALE", "")),
        raw_response=response,
        valid=valid,
        error=str(error) if error else None,
        source=source,
    )


def rubric_prompt(user_prompt: str, answer: str) -> str:
    return dedent(f"""
    Grade one answer for the user prompt. Use only integers from 0 to 10.

    Criteria:
    TASK_FULFILLMENT: Does the answer satisfy the user's actual request?
    CORRECTNESS: Are claims, reasoning, and instructions sound?
    USEFULNESS: Would the answer help the user make progress?
    STRUCTURE: Is the answer organized and easy to follow?
    CONSTRAINT_HANDLING: Does it respect stated constraints and tradeoffs?
    INSIGHT: Does it add non-obvious, high-value thinking?

    User prompt:
    {user_prompt}

    Answer:
    {answer}

    Respond with exactly these lines and no extra text:
    TASK_FULFILLMENT: <0-10 integer>
    CORRECTNESS: <0-10 integer>
    USEFULNESS: <0-10 integer>
    STRUCTURE: <0-10 integer>
    CONSTRAINT_HANDLING: <0-10 integer>
    INSIGHT: <0-10 integer>
    RATIONALE: <one sentence>
    """)


RUBRIC_SCORE_LABELS = ["TASK_FULFILLMENT", "CORRECTNESS", "USEFULNESS", "STRUCTURE", "CONSTRAINT_HANDLING", "INSIGHT"]


def parse_rubric_response(text: str) -> dict[str, int | str]:
    values: dict[str, int | str] = {}
    missing = []
    for label in RUBRIC_SCORE_LABELS:
        match = re.search(rf"{label}\s*:\s*(\d+)", text, flags=re.I)
        if not match:
            missing.append(label)
            continue
        score = int(match.group(1))
        values[label] = max(0, min(10, score))
    rationale_match = re.search(r"RATIONALE\s*:\s*(.*)", text, flags=re.I | re.S)
    values["RATIONALE"] = rationale_match.group(1).strip() if rationale_match else text.strip()
    if missing:
        values["ERROR"] = "Missing rubric labels: " + ", ".join(missing)
    return values
