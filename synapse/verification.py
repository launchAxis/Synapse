from __future__ import annotations

from typing import Dict, Iterable, List

from synapse.ideas import Challenge, Idea, Verification
from synapse.models import ModelManager
from synapse.prompts import verification_prompt
from synapse.utils import first_nonempty, parse_labeled_field, raw_fallback_summary


VERIFICATION_LABELS = [
    "VERDICT",
    "UNMET_REQUIREMENTS",
    "UNSUPPORTED_CLAIMS",
    "LOGICAL_GAPS",
    "MAJOR_RISKS",
    "REQUIRED_FIXES",
    "REASONING",
]


def verify_ideas(
    topic: str,
    ideas: Iterable[Idea],
    challenges: Iterable[Challenge],
    models: Dict[str, str],
    manager: ModelManager,
    rubric: Iterable[str],
) -> List[Verification]:
    results: List[Verification] = []
    model_items = list(models.items())
    if not model_items:
        return results

    challenge_list = list(challenges)
    for index, idea in enumerate(ideas):
        label, model = model_items[index % len(model_items)]
        role = "Verifier"
        relevant = [item for item in challenge_list if item.target_idea_id == idea.id]
        response = manager.ask(model, verification_prompt(topic, idea, relevant, rubric, role))
        if response.ok:
            results.append(parse_verification(idea.id, model, role, response.text))
    return results


def parse_verification(idea_id: str, model: str, role: str, text: str) -> Verification:
    fallback = raw_fallback_summary(text)
    verdict = first_nonempty(parse_labeled_field(text, "VERDICT", VERIFICATION_LABELS), fallback="partial_pass").lower()
    if verdict not in {"pass", "partial_pass", "fail"}:
        verdict = "partial_pass"
    return Verification(
        target_idea_id=idea_id,
        verifier_model=model,
        verifier_role=role,
        verdict=verdict,
        unmet_requirements=first_nonempty(parse_labeled_field(text, "UNMET_REQUIREMENTS", VERIFICATION_LABELS), fallback=fallback),
        unsupported_claims=first_nonempty(parse_labeled_field(text, "UNSUPPORTED_CLAIMS", VERIFICATION_LABELS), fallback=fallback),
        logical_gaps=first_nonempty(parse_labeled_field(text, "LOGICAL_GAPS", VERIFICATION_LABELS), fallback=fallback),
        major_risks=first_nonempty(parse_labeled_field(text, "MAJOR_RISKS", VERIFICATION_LABELS), fallback=fallback),
        required_fixes=first_nonempty(parse_labeled_field(text, "REQUIRED_FIXES", VERIFICATION_LABELS), fallback=fallback),
        reasoning=first_nonempty(parse_labeled_field(text, "REASONING", VERIFICATION_LABELS), fallback=fallback),
        raw_text=text,
    )
