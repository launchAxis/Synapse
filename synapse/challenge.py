from __future__ import annotations

from typing import Dict, Iterable, List

from synapse.ideas import Challenge, Idea
from synapse.models import ModelManager
from synapse.prompts import challenge_prompt
from synapse.utils import first_nonempty, parse_labeled_field, raw_fallback_summary


CHALLENGE_LABELS = ["KEY_FAILURE_MODE", "WEAKEST_ASSUMPTION", "IMPLEMENTATION_RISK", "RECOMMENDED_FIX"]


def challenge_ideas(
    topic: str,
    ideas: Iterable[Idea],
    models: Dict[str, str],
    manager: ModelManager,
    rubric: Iterable[str],
) -> List[Challenge]:
    results: List[Challenge] = []
    model_items = list(models.items())
    if not model_items:
        return results

    for index, idea in enumerate(ideas):
        label, model = model_items[index % len(model_items)]
        role = "Challenger"
        response = manager.ask(model, challenge_prompt(topic, idea, rubric, role))
        if response.ok:
            results.append(parse_challenge(idea.id, model, role, response.text))
    return results


def parse_challenge(idea_id: str, model: str, role: str, text: str) -> Challenge:
    fallback = raw_fallback_summary(text)
    return Challenge(
        target_idea_id=idea_id,
        challenger_model=model,
        challenger_role=role,
        key_failure_mode=first_nonempty(parse_labeled_field(text, "KEY_FAILURE_MODE", CHALLENGE_LABELS), fallback=fallback),
        weakest_assumption=first_nonempty(parse_labeled_field(text, "WEAKEST_ASSUMPTION", CHALLENGE_LABELS), fallback=fallback),
        implementation_risk=first_nonempty(parse_labeled_field(text, "IMPLEMENTATION_RISK", CHALLENGE_LABELS), fallback=fallback),
        recommended_fix=first_nonempty(parse_labeled_field(text, "RECOMMENDED_FIX", CHALLENGE_LABELS), fallback=fallback),
        raw_text=text,
    )
