from __future__ import annotations

from typing import Dict, Iterable, List

from synapse.ideas import Idea, Steelman
from synapse.models import ModelManager
from synapse.prompts import steelman_prompt
from synapse.utils import first_nonempty, parse_labeled_field, raw_fallback_summary


STEELMAN_LABELS = ["STRONGEST_PART", "BEST_USE_CASE", "PRESERVE_IF_EVOLVED"]


def steelman_ideas(
    topic: str,
    ideas: Iterable[Idea],
    models: Dict[str, str],
    manager: ModelManager,
    rubric: Iterable[str],
) -> List[Steelman]:
    results: List[Steelman] = []
    model_items = list(models.items())
    if not model_items:
        return results

    for index, idea in enumerate(ideas):
        usable = [(label, model) for label, model in model_items if model != idea.author_model]
        label, model = (usable or model_items)[index % len(usable or model_items)]
        role = "Steelman"
        response = manager.ask(model, steelman_prompt(topic, idea, role, rubric))
        if response.ok:
            results.append(parse_steelman(idea.id, model, role, response.text))

    return results


def parse_steelman(idea_id: str, model: str, role: str, text: str) -> Steelman:
    fallback = raw_fallback_summary(text)
    return Steelman(
        target_idea_id=idea_id,
        model=model,
        role=role,
        strongest_part=first_nonempty(parse_labeled_field(text, "STRONGEST_PART", STEELMAN_LABELS), fallback=fallback),
        best_use_case=first_nonempty(parse_labeled_field(text, "BEST_USE_CASE", STEELMAN_LABELS), fallback=fallback),
        preserve_if_evolved=first_nonempty(parse_labeled_field(text, "PRESERVE_IF_EVOLVED", STEELMAN_LABELS), fallback=fallback),
        raw_text=text,
    )
