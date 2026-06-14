# This file improves the tournament survivors into the next generation of ideas.
from __future__ import annotations

from typing import Dict, List

from synapse.ideas import GenerationMemory, Idea
from synapse.models import ModelManager
from synapse.prompts import evolution_prompt, fresh_outsider_prompt
from synapse.tournament import summarize_tournament_feedback
from synapse.utils import strip_response_label


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
) -> List[Idea]:
    evolved: List[Idea] = []
    model_items = list(models.items())

    for index, idea in enumerate(survivors):
        label, model = model_items[index % len(model_items)]
        mutation_type = MUTATION_TYPES[(next_generation + index) % len(MUTATION_TYPES)]
        response = manager.ask(
            model,
            evolution_prompt(
                topic=topic,
                idea=idea,
                critique_summary=critique_summaries.get(idea.id, "No critique summary available."),
                tournament_summary=summarize_tournament_feedback(idea, comparisons),
                memory=memory,
                model_label=label,
                mutation_type=mutation_type,
            ),
        )

        if response.ok:
            text = strip_response_label(response.text, ["Improved idea", "Idea"])
            author_model = model
        else:
            text = idea.text
            author_model = idea.author_model

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
            )
        )

    if model_items and survivors:
        label, model = model_items[len(evolved) % len(model_items)]
        response = manager.ask(model, fresh_outsider_prompt(topic, label, next_generation, survivors))
        if response.ok:
            evolved.append(
                Idea(
                    id=f"G{next_generation}-F1",
                    text=strip_response_label(response.text, ["Idea"]),
                    author_model=model,
                    generation=next_generation,
                    origin="fresh",
                    mutation_type="fresh outsider",
                )
            )

    return evolved
