# This file creates the first set of ideas from the available Ollama models.
from __future__ import annotations

from typing import Dict, Iterable, List

from synapse.ideas import Idea
from synapse.models import ModelManager
from synapse.prompts import generation_prompt
from synapse.utils import first_nonempty, parse_labeled_field, strip_response_label


IDEA_LABELS = ["TITLE", "SUMMARY", "CONTENT", "STRENGTHS", "RISKS", "ASSUMPTIONS"]

DEFAULT_ROLES = [
    "Creator / Visionary",
    "Pragmatist",
    "Contrarian",
    "Engineer",
    "User Advocate",
]


def generate_initial_ideas(
    topic: str,
    models: Dict[str, str],
    manager: ModelManager,
    roles: Iterable[str] | None = None,
    task_type: str = "general",
    rubric: Iterable[str] = (),
) -> List[Idea]:
    ideas: List[Idea] = []
    model_items = list(models.items())
    selected_roles = list(roles or DEFAULT_ROLES)
    if not model_items:
        return ideas

    for index, role in enumerate(selected_roles):
        label, model = model_items[index % len(model_items)]
        response = manager.ask(model, generation_prompt(topic, label, role, task_type, rubric))
        if not response.ok:
            continue

        ideas.append(parse_idea_response(
            text=response.text,
            idea_id=f"I{index + 1:03d}",
            model=model,
            role=role,
            generation=0,
            origin="generated",
        ))

    return ideas


def parse_idea_response(
    text: str,
    idea_id: str,
    model: str,
    role: str,
    generation: int,
    origin: str,
    parent_id: str | None = None,
    borrowed_from: str | None = None,
    mutation_type: str | None = None,
) -> Idea:
    title = parse_labeled_field(text, "TITLE", IDEA_LABELS)
    summary = parse_labeled_field(text, "SUMMARY", IDEA_LABELS)
    content = parse_labeled_field(text, "CONTENT", IDEA_LABELS)
    strengths = parse_labeled_field(text, "STRENGTHS", IDEA_LABELS)
    risks = parse_labeled_field(text, "RISKS", IDEA_LABELS)
    assumptions = parse_labeled_field(text, "ASSUMPTIONS", IDEA_LABELS)
    fallback = strip_response_label(text, ["Idea", "Improved idea"])
    body = first_nonempty(content, summary, fallback=fallback)
    return Idea(
        id=idea_id,
        text=body,
        author_model=model,
        generation=generation,
        parent_id=parent_id,
        parent_ids=[parent_id] if parent_id else [],
        origin=origin,
        mutation_type=mutation_type,
        role=role,
        title=title,
        summary=summary,
        strengths=strengths,
        risks=risks,
        assumptions=assumptions,
        borrowed_from=borrowed_from,
    )
