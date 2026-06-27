# This file asks models to find weaknesses, risks, and improvements for each idea.
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from synapse.ideas import Critique, Idea
from synapse.models import ModelManager
from synapse.prompts import critique_prompt
from synapse.utils import first_nonempty, parse_labeled_field, raw_fallback_summary

CRITIQUE_LABELS = [
    "STRONGEST_PART",
    "WEAKEST_PART",
    "HIDDEN_ASSUMPTION",
    "BIGGEST_RISK",
    "MISSING_DETAIL",
    "REPAIR_SUGGESTION",
    "RUBRIC_SCORES",
]


def critique_ideas(
    topic: str,
    ideas: Iterable[Idea],
    models: Dict[str, str],
    manager: ModelManager,
    rubric: Iterable[str] = (),
    critic_role: str = "Critic",
) -> List[Critique]:
    critiques: List[Critique] = []
    model_items = list(models.items())

    for idea_index, idea in enumerate(ideas):
        idea.critiques = []
        for offset, (label, model) in enumerate(model_items):
            if len(model_items) > 1 and model == idea.author_model:
                continue
            role = critic_role if offset == 0 else f"{critic_role} {offset + 1}"
            response = manager.ask(model, critique_prompt(topic, idea, label, role, rubric))
            if not response.ok:
                continue

            critique = parse_critique(idea.id, model, response.text, role)
            idea.critiques.append(critique)
            critiques.append(critique)

        if not idea.critiques and model_items:
            label, model = model_items[idea_index % len(model_items)]
            response = manager.ask(model, critique_prompt(topic, idea, label, critic_role, rubric))
            if response.ok:
                critique = parse_critique(idea.id, model, response.text, critic_role)
                idea.critiques.append(critique)
                critiques.append(critique)

    return critiques


def parse_critique(idea_id: str, critic_model: str, text: str, critic_role: str = "Critic") -> Critique:
    raw_summary = raw_fallback_summary(text)
    strongest_part = first_nonempty(
        parse_labeled_field(text, "STRONGEST_PART", CRITIQUE_LABELS),
        fallback=raw_summary,
    )
    weakest_part = first_nonempty(
        parse_labeled_field(text, "WEAKEST_PART", CRITIQUE_LABELS),
        parse_labeled_field(text, "MAIN_WEAKNESS"),
        parse_labeled_field(text, "Main weakness"),
        fallback=raw_summary,
    )
    hidden_assumption = first_nonempty(
        parse_labeled_field(text, "HIDDEN_ASSUMPTION", CRITIQUE_LABELS),
        parse_labeled_field(text, "UNCLEAR_ASSUMPTION"),
        parse_labeled_field(text, "Unclear assumption"),
        fallback=raw_summary,
    )
    biggest_risk = first_nonempty(
        parse_labeled_field(text, "BIGGEST_RISK", CRITIQUE_LABELS),
        parse_labeled_field(text, "RISK"),
        parse_labeled_field(text, "Risk"),
        fallback=raw_summary,
    )
    missing_detail = first_nonempty(
        parse_labeled_field(text, "MISSING_DETAIL", CRITIQUE_LABELS),
        parse_labeled_field(text, "MISSING_ELEMENT"),
        parse_labeled_field(text, "Missing element"),
        fallback=raw_summary,
    )
    repair_suggestion = first_nonempty(
        parse_labeled_field(text, "REPAIR_SUGGESTION", CRITIQUE_LABELS),
        parse_labeled_field(text, "SUGGESTED_IMPROVEMENT"),
        parse_labeled_field(text, "Suggested improvement"),
        fallback=raw_summary,
    )
    return Critique(
        idea_id=idea_id,
        critic_model=critic_model,
        main_weakness=weakest_part,
        risk=biggest_risk,
        missing_element=missing_detail,
        unclear_assumption=hidden_assumption,
        suggested_improvement=repair_suggestion,
        raw_text=text,
        critic_role=critic_role,
        strongest_part=strongest_part,
        weakest_part=weakest_part,
        hidden_assumption=hidden_assumption,
        biggest_risk=biggest_risk,
        missing_detail=missing_detail,
        repair_suggestion=repair_suggestion,
        rubric_scores={"raw": parse_labeled_field(text, "RUBRIC_SCORES", CRITIQUE_LABELS)},
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
