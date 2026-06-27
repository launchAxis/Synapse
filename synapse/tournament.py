# This file runs head-to-head idea battles and records wins and losses.
from __future__ import annotations

import itertools
import re
from typing import Dict, Iterable, List

from synapse.ideas import Comparison, Idea
from synapse.models import ModelManager
from synapse.prompts import comparison_prompt, strict_comparison_retry_prompt


def run_pairwise_tournament(
    topic: str,
    ideas: List[Idea],
    judge_models: Dict[str, str],
    manager: ModelManager,
    rubric: Iterable[str] = (),
    verbose: bool = True,
) -> tuple[List[Idea], List[Comparison]]:
    for idea in ideas:
        idea.reset_record()

    comparisons: List[Comparison] = []
    idea_by_id = {idea.id: idea for idea in ideas}

    comparison_number = 0
    for left, right in itertools.combinations(ideas, 2):
        judge_items = eligible_judges(left, right, judge_models)
        for label, model in judge_items:
            comparison_number += 1
            comparison_id = f"C{comparison_number:04d}"
            first = judge_once(topic, left, right, label, model, manager, rubric, swapped=False)
            second = judge_once(topic, right, left, label, model, manager, rubric, swapped=True)

            if not first["valid"] or not second["valid"]:
                reason = first["reason"] if not first["valid"] else second["reason"]
                if verbose:
                    print(
                        f"Warning: invalid tournament judgment from {model} for "
                        f"{left.id} vs {right.id}. Comparison marked invalid."
                    )
                comparisons.append(
                    Comparison(
                        comparison_id=comparison_id,
                        idea_a_id=left.id,
                        idea_b_id=right.id,
                        winner_id="",
                        loser_id="",
                        judge_model=model,
                        judge_role="Judge",
                        reason=reason,
                        valid=False,
                        stable=False,
                        first_winner_id=str(first["winner_id"]),
                        second_winner_id=str(second["winner_id"]),
                        second_reason=str(second["reason"]),
                    )
                )
                continue

            first_winner = str(first["winner_id"])
            second_winner = str(second["winner_id"])
            stable = bool(first_winner and first_winner == second_winner)

            if not stable:
                comparisons.append(
                    Comparison(
                        comparison_id=comparison_id,
                        idea_a_id=left.id,
                        idea_b_id=right.id,
                        winner_id="",
                        loser_id="",
                        judge_model=model,
                        judge_role="Judge",
                        reason=str(first["reason"]),
                        valid=True,
                        stable=False,
                        first_winner_id=first_winner,
                        second_winner_id=second_winner,
                        second_reason=str(second["reason"]),
                    )
                )
                continue

            winner = idea_by_id[first_winner]
            loser = right if winner.id == left.id else left

            winner.wins += 1
            loser.losses += 1

            comparisons.append(
                Comparison(
                    comparison_id=comparison_id,
                    idea_a_id=left.id,
                    idea_b_id=right.id,
                    winner_id=winner.id,
                    loser_id=loser.id,
                    judge_model=model,
                    judge_role="Judge",
                    reason=str(first["reason"]),
                    valid=True,
                    stable=True,
                    first_winner_id=first_winner,
                    second_winner_id=second_winner,
                    second_reason=str(second["reason"]),
                )
            )

    ranked = rank_ideas(idea_by_id.values())
    return ranked, comparisons


def judge_once(
    topic: str,
    idea_a: Idea,
    idea_b: Idea,
    judge_label: str,
    model: str,
    manager: ModelManager,
    rubric: Iterable[str],
    swapped: bool,
) -> dict[str, object]:
    response = manager.ask(model, comparison_prompt(topic, idea_a, idea_b, judge_label, rubric, swapped=swapped))
    if not response.ok:
        return {"valid": False, "winner_id": "", "reason": response.error or "Judge call failed."}

    winner_side, reason = parse_judgment(response.text)
    if winner_side is None:
        retry = manager.ask(
            model,
            strict_comparison_retry_prompt(topic, idea_a, idea_b, judge_label, response.text, rubric),
        )
        if retry.ok:
            winner_side, reason = parse_judgment(retry.text)

    if winner_side is None:
        return {"valid": False, "winner_id": "", "reason": reason}

    winner = idea_b if winner_side == "B" else idea_a
    return {"valid": True, "winner_id": winner.id, "reason": reason}


def parse_judgment(text: str) -> tuple[str | None, str]:
    winner_match = None
    for line in text.splitlines():
        cleaned = line.replace("**", "").strip()
        winner_match = re.fullmatch(r"WINNER\s*:\s*(?:Idea\s*)?([AB])", cleaned, flags=re.I)
        if winner_match:
            break

    reason_text = re.sub(r"\*\*", "", text)
    reason_match = re.search(r"reason\s*:\s*(.*)", reason_text, flags=re.I | re.DOTALL)

    if not winner_match:
        return None, text.strip() or "No parseable reason provided."

    winner = winner_match.group(1).upper()
    reason = reason_match.group(1).strip() if reason_match else text.strip()
    return winner, reason or "No reason provided."


def eligible_judges(idea_a: Idea, idea_b: Idea, judge_models: Dict[str, str]) -> list[tuple[str, str]]:
    all_judges = list(judge_models.items())
    alternatives = [
        (label, model)
        for label, model in all_judges
        if model not in {idea_a.author_model, idea_b.author_model}
    ]
    return alternatives or all_judges


def rank_ideas(ideas: Iterable[Idea]) -> List[Idea]:
    return sorted(ideas, key=lambda item: (-item.wins, item.losses, item.id))


def summarize_tournament_feedback(idea: Idea, comparisons: Iterable[Comparison]) -> str:
    related = [
        item for item in comparisons
        if item.valid and item.stable and (item.winner_id == idea.id or item.loser_id == idea.id)
    ]
    if not related:
        return "No tournament feedback was recorded."

    lines = []
    for item in related[:5]:
        result = "won" if item.winner_id == idea.id else "lost"
        opponent = item.loser_id if result == "won" else item.winner_id
        lines.append(f"{result} against {opponent}: {item.reason}")
    return "\n".join(lines)
