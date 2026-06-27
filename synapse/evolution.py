# This file improves the tournament survivors into the next generation of ideas.
from __future__ import annotations

from typing import Dict, List

from synapse.generation import parse_idea_response
from synapse.ideas import GenerationMemory, Idea, Steelman
from synapse.models import ModelManager
from synapse.prompts import evolution_prompt, fresh_outsider_prompt
from synapse.tournament import summarize_tournament_feedback
from synapse.utils import parse_labeled_field, strip_response_label


MUTATION_TYPES = [
    "make more practical",
    "make more original",
    "make simpler",
    "make more ambitious",
    "fix the biggest weakness",
]


def evolve_survivors(
    topic: str,
    survivors: List[Idea],
    critique_summaries: Dict[str, str],
    comparisons,
    memory: List[GenerationMemory],
    models: Dict[str, str],
    manager: ModelManager,
    next_generation: int,
    steelmen: List[Steelman] | None = None,
    defeated_ideas: List[Idea] | None = None,
    task_type: str = "general",
    rubric=(),
) -> List[Idea]:
    evolved: List[Idea] = []
    model_items = list(models.items())
    steelman_by_id = {item.target_idea_id: item for item in (steelmen or [])}
    defeated = defeated_ideas or []

    for index, idea in enumerate(survivors):
        label, model = model_items[index % len(model_items)]
        mutation_type = MUTATION_TYPES[(next_generation + index) % len(MUTATION_TYPES)]
        borrowed = defeated[index % len(defeated)] if defeated else None
        response = manager.ask(
            model,
            evolution_prompt(
                topic=topic,
                idea=idea,
                steelman=steelman_by_id.get(idea.id),
                critique_summary=critique_summaries.get(idea.id, "No critique summary available."),
                tournament_summary=summarize_tournament_feedback(idea, comparisons),
                memory=memory,
                model_label=label,
                defeated_idea=borrowed,
                mutation_type=mutation_type,
            ),
        )

        if response.ok:
            parsed = parse_idea_response(
                text=response.text,
                idea_id=f"G{next_generation}-{idea.id}",
                model=model,
                role=idea.role or "Improver",
                generation=next_generation,
                origin="evolved",
                parent_id=idea.id,
                borrowed_from=borrowed.id if borrowed else None,
                mutation_type=mutation_type,
            )
            parsed.borrowed_element = parse_labeled_field(
                response.text,
                "BORROWED_ELEMENT",
                ["TITLE", "SUMMARY", "CONTENT", "BORROWED_ELEMENT", "DIFF_SUMMARY", "RISKS_REMAINING"],
            )
            parsed.diff_summary = parse_labeled_field(
                response.text,
                "DIFF_SUMMARY",
                ["TITLE", "SUMMARY", "CONTENT", "BORROWED_ELEMENT", "DIFF_SUMMARY", "RISKS_REMAINING"],
            )
            parsed.risks_remaining = parse_labeled_field(
                response.text,
                "RISKS_REMAINING",
                ["TITLE", "SUMMARY", "CONTENT", "BORROWED_ELEMENT", "DIFF_SUMMARY", "RISKS_REMAINING"],
            )
            evolved.append(parsed)
            continue
        else:
            text = idea.text
            author_model = model

        evolved.append(
            Idea(
                id=f"G{next_generation}-{idea.id}",
                text=text,
                author_model=author_model,
                generation=next_generation,
                parent_id=idea.id,
                parent_ids=[idea.id],
                origin="evolved",
                mutation_type=mutation_type,
                role=idea.role,
                borrowed_from=borrowed.id if borrowed else None,
                borrowed_element=borrowed.summary if borrowed else "",
            )
        )

    if model_items and survivors:
        label, model = model_items[len(evolved) % len(model_items)]
        response = manager.ask(model, fresh_outsider_prompt(topic, label, next_generation, survivors, task_type, rubric))
        if response.ok:
            evolved.append(
                parse_idea_response(
                    text=response.text,
                    idea_id=f"G{next_generation}-F1",
                    model=model,
                    role="Outsider",
                    generation=next_generation,
                    origin="fresh",
                    mutation_type="fresh outsider",
                )
            )

    return evolved
