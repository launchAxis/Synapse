# This file stores short lessons learned from each generation during one run.
from __future__ import annotations

from typing import List

from synapse.ideas import GenerationMemory, Idea
from synapse.models import ModelManager
from synapse.prompts import memory_prompt


def build_generation_memory(
    topic: str,
    generation: int,
    ranked_ideas: list[Idea],
    manager: ModelManager,
    models: dict[str, str],
) -> GenerationMemory:
    if not ranked_ideas:
        return GenerationMemory(generation=generation, summary="No ideas survived this generation.")

    first_model = next(iter(models.values()))
    response = manager.ask(first_model, memory_prompt(topic, ranked_ideas, generation))
    if response.ok:
        summary = response.text
    else:
        winner = ranked_ideas[0]
        summary = (
            f"Winner was {winner.id} with {winner.wins} wins and {winner.losses} losses. "
            "Next generation should preserve its useful mechanism and fix repeated critique issues."
        )

    return GenerationMemory(generation=generation, summary=summary)


def memory_text(memory: List[GenerationMemory]) -> str:
    if not memory:
        return "No generation memory yet."
    return "\n".join(f"Generation {item.generation}: {item.summary}" for item in memory)
