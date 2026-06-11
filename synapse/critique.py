# This file asks models to find weaknesses, risks, and improvements for each idea.
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from synapse.ideas import Critique, Idea
from synapse.models import ModelManager
from synapse.prompts import critique_prompt
from synapse.utils import first_nonempty, parse_labeled_field, raw_fallback_summary


def critique_ideas(
    topic: str,
    ideas: Iterable[Idea],
    models: Dict[str, str],
    manager: ModelManager,
) -> List[Critique]:
    critiques: List[Critique] = []

    for idea in ideas:
        idea.critiques = []
        for label, model in models.items():
            response = manager.ask(model, critique_prompt(topic, idea, label))
            if not response.ok:
                continue

            critique = parse_critique(idea.id, model, response.text)
            idea.critiques.append(critique)
            critiques.append(critique)

    return critiques


def parse_critique(idea_id: str, critic_model: str, text: str) -> Critique:
    raw_summary = raw_fallback_summary(text)
    return Critique(
        idea_id=idea_id,
        critic_model=critic_model,
        main_weakness=first_nonempty(
            parse_labeled_field(text, "MAIN_WEAKNESS"),
            parse_labeled_field(text, "Main weakness"),
            fallback=raw_summary,
        ),
        risk=first_nonempty(
            parse_labeled_field(text, "RISK"),
            parse_labeled_field(text, "Risk"),
            fallback=raw_summary,
        ),
        missing_element=first_nonempty(
            parse_labeled_field(text, "MISSING_ELEMENT"),
            parse_labeled_field(text, "Missing element"),
            fallback=raw_summary,
        ),
        unclear_assumption=first_nonempty(
            parse_labeled_field(text, "UNCLEAR_ASSUMPTION"),
            parse_labeled_field(text, "Unclear assumption"),
            fallback=raw_summary,
        ),
        suggested_improvement=first_nonempty(
            parse_labeled_field(text, "SUGGESTED_IMPROVEMENT"),
            parse_labeled_field(text, "Suggested improvement"),
            fallback=raw_summary,
        ),
        raw_text=text,
    )


def summarize_critiques(critiques: Iterable[Critique]) -> Dict[str, str]:
    grouped: dict[str, list[Critique]] = defaultdict(list)
    for critique in critiques:
        grouped[critique.idea_id].append(critique)

    summaries: Dict[str, str] = {}
    for idea_id, items in grouped.items():
        lines = []
        for item in items[:3]:
            lines.append(
                f"{item.critic_model}: weakness={item.main_weakness}; "
                f"risk={item.risk}; improvement={item.suggested_improvement}"
            )
        summaries[idea_id] = "\n".join(lines)

    return summaries
