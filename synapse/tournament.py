# This file runs head-to-head idea battles and records wins and losses.
from __future__ import annotations

import itertools
import re
from typing import Callable, Dict, Iterable, List

from synapse.ideas import Comparison, Idea
from synapse.models import ModelManager
from synapse.prompts import comparison_prompt, strict_comparison_retry_prompt


def run_pairwise_tournament(
    topic: str,
    ideas: List[Idea],
    judge_models: Dict[str, str],
    manager: ModelManager,
    warning_handler: Callable[[str, str, str, str], None] | None = None,
    print_warnings: bool = True,
) -> tuple[List[Idea], List[Comparison]]:
    for idea in ideas:
        idea.reset_record()

    comparisons: List[Comparison] = []
    idea_by_id = {idea.id: idea for idea in ideas}

    for idea_a, idea_b in itertools.combinations(ideas, 2):
        for label, model in judge_models.items():
            response = manager.ask(model, comparison_prompt(topic, idea_a, idea_b, label))
            if not response.ok:
                continue

            winner_side, reason = parse_judgment(response.text)
            if winner_side is None:
                retry = manager.ask(
                    model,
                    strict_comparison_retry_prompt(topic, idea_a, idea_b, label, response.text),
                )
                if retry.ok:
                    winner_side, reason = parse_judgment(retry.text)

            if winner_side is None:
                message = (
                    f"invalid tournament judgment from {model} for "
                    f"{idea_a.id} vs {idea_b.id}. Comparison skipped."
                )
                if warning_handler:
                    warning_handler(message, model, idea_a.id, idea_b.id)
                if print_warnings:
                    print(f"Warning: {message}")
                continue

            if winner_side == "B":
                winner = idea_b
                loser = idea_a
            else:
                winner = idea_a
                loser = idea_b

            winner.wins += 1
            loser.losses += 1

            comparisons.append(
                Comparison(
                    idea_a_id=idea_a.id,
                    idea_b_id=idea_b.id,
                    winner_id=winner.id,
                    loser_id=loser.id,
                    judge_model=model,
                    reason=reason,
                )
            )

    ranked = rank_ideas(idea_by_id.values())
    return ranked, comparisons


def parse_judgment(text: str) -> tuple[str | None, str]:
    winner_match = None
    for line in text.splitlines():
        cleaned = line.replace("**", "").strip()
        winner_match = re.fullmatch(r"WINNER\s*:\s*([AB])", cleaned, flags=re.I)
        if winner_match:
            break

    reason_text = re.sub(r"\*\*", "", text)
    reason_match = re.search(r"reason\s*:\s*(.*)", reason_text, flags=re.I | re.DOTALL)

    if not winner_match:
        return None, text.strip() or "No parseable reason provided."

    winner = winner_match.group(1).upper()
    reason = reason_match.group(1).strip() if reason_match else text.strip()
    return winner, reason or "No reason provided."


def rank_ideas(ideas: Iterable[Idea]) -> List[Idea]:
    return sorted(ideas, key=lambda item: (-item.wins, item.losses, item.id))


def summarize_tournament_feedback(idea: Idea, comparisons: Iterable[Comparison]) -> str:
    related = [
        item for item in comparisons
        if item.winner_id == idea.id or item.loser_id == idea.id
    ]
    if not related:
        return "No tournament feedback was recorded."

    lines = []
    for item in related[:5]:
        result = "won" if item.winner_id == idea.id else "lost"
        opponent = item.loser_id if result == "won" else item.winner_id
        lines.append(f"{result} against {opponent}: {item.reason}")
    return "\n".join(lines)
