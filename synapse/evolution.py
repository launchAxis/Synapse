# This file improves the tournament survivors into the next generation of ideas.
from __future__ import annotations

from typing import Dict, List

from synapse.ideas import GenerationMemory, Idea
from synapse.models import ModelManager
from synapse.prompts import evolution_prompt
from synapse.tournament import summarize_tournament_feedback


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
        response = manager.ask(
            model,
            evolution_prompt(
                topic=topic,
                idea=idea,
                critique_summary=critique_summaries.get(idea.id, "No critique summary available."),
                tournament_summary=summarize_tournament_feedback(idea, comparisons),
                memory=memory,
                model_label=label,
            ),
        )

        if response.ok:
            text = response.text
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
            )
        )

    return evolved
