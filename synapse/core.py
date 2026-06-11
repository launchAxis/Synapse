from __future__ import annotations

from typing import List

from synapse.config import (
    SIMPLIFIED,
    FINAL_SYNTHESIS_MODEL_KEY,
    MAX_GENERATIONS,
    MODELS,
    OLLAMA_TIMEOUT_SECONDS,
    TOP_K_SURVIVORS,
)
from synapse.critique import critique_ideas, summarize_critiques
from synapse.evolution import evolve_survivors
from synapse.generation import generate_initial_ideas
from synapse.ideas import GenerationMemory, Idea
from synapse.memory import build_generation_memory
from synapse.models import ModelManager
from synapse.output import (
    print_critiques,
    print_generated_ideas,
    print_generation_summary,
    print_memory,
    print_ranking,
    print_tournament,
)
from synapse.prompts import final_prompt
from synapse.tournament import run_pairwise_tournament
from synapse.utils import section


def run_council(topic: str, simplified: bool = SIMPLIFIED) -> str:
    # This is the main Synapse pipeline: generate, critique, compare, evolve, then answer.
    # Clean up the user prompt so empty spaces do not count as a real prompt.
    topic = topic.strip()
    if not topic:
        raise ValueError("No prompt entered.")

    # Create the Ollama manager. This object handles model checks and model calls.
    manager = ModelManager(MODELS, timeout_seconds=OLLAMA_TIMEOUT_SECONDS)
    usable_models = manager.refresh_available_models()
    if not usable_models:
        raise RuntimeError("No usable Ollama models found. Pull at least one configured model and try again.")

    # Generation 0: each available model creates one starting idea.
    ideas = generate_initial_ideas(topic, usable_models, manager)
    if not ideas:
        raise RuntimeError("No valid ideas were generated. Check Ollama and your installed models.")

    # Memory stores short lessons from each generation during this run.
    memory: List[GenerationMemory] = []
    final_ranked: List[Idea] = ideas

    # Repeat the council process for a few generations.
    for generation in range(MAX_GENERATIONS):
        if not simplified:
            section(f"GENERATION {generation}")
            print_generated_ideas(ideas)

        # Every model critiques every current idea.
        critiques = critique_ideas(topic, ideas, usable_models, manager)
        if not simplified:
            print_critiques(critiques)
        critique_summaries = summarize_critiques(critiques)

        # Pairwise tournament: every idea is compared against every other idea.
        ranked, comparisons = run_pairwise_tournament(topic, ideas, usable_models, manager)
        final_ranked = ranked
        if not simplified:
            print_tournament(comparisons)
            print_ranking(ranked)

        # Summarize what this generation learned so the next generation can improve.
        generation_memory = build_generation_memory(topic, generation, ranked, manager, usable_models)
        memory.append(generation_memory)

        survivor_count = min(TOP_K_SURVIVORS, len(ranked))
        if simplified:
            print_generation_summary(
                generation=generation,
                ideas=ideas,
                critiques=critiques,
                comparisons=comparisons,
                ranked=ranked,
                memory=generation_memory,
                survivor_count=survivor_count,
            )
        else:
            print_memory(generation_memory)

        if generation == MAX_GENERATIONS - 1 or len(ranked) <= 1:
            break

        # Only the top-ranked ideas survive and get evolved.
        survivors = ranked[:survivor_count]
        ideas = evolve_survivors(
            topic=topic,
            survivors=survivors,
            critique_summaries=critique_summaries,
            comparisons=comparisons,
            memory=memory,
            models=usable_models,
            manager=manager,
            next_generation=generation + 1,
        )

    # The best-ranked idea after the final generation becomes the winner.
    winner = final_ranked[0]
    final_answer = synthesize_final_answer(topic, winner, memory, usable_models, manager)

    section("FINAL RESULT")
    print(final_answer)
    return final_answer


# Ask one model to turn the winning idea into a polished final answer.
def synthesize_final_answer(
    topic: str,
    winner: Idea,
    memory: List[GenerationMemory],
    models: dict[str, str],
    manager: ModelManager,
) -> str:
    model = models.get(FINAL_SYNTHESIS_MODEL_KEY) or next(iter(models.values()))
    response = manager.ask(model, final_prompt(topic, winner, memory))
    if response.ok:
        return response.text
    return winner.text


# Command-line version: asks the user for a prompt and output mode.
def run_cli() -> None:
    topic = input("Enter prompt: ").strip()
    mode = input("Output mode: [d]etailed or [s]implified? ").strip().lower()
    simplified = mode.startswith("s")
    try:
        run_council(topic, simplified=simplified)
    except (RuntimeError, ValueError) as exc:
        print(f"\nSynapse stopped: {exc}")
