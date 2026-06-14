from __future__ import annotations

import argparse
import copy
from datetime import datetime
from typing import List

from synapse import __version__
from synapse.config import (
    FINAL_SYNTHESIS_MODEL_KEY,
    MAX_GENERATIONS,
    MODELS,
    OLLAMA_TIMEOUT_SECONDS,
    SIMPLIFIED,
    TOP_K_SURVIVORS,
)
from synapse.critique import critique_ideas, summarize_critiques
from synapse.evolution import evolve_survivors
from synapse.export import run_result_to_json, save_run, write_json_file
from synapse.generation import generate_initial_ideas
from synapse.ideas import DebugEvent, GenerationMemory, GenerationSnapshot, Idea, RunResult
from synapse.memory import build_generation_memory
from synapse.models import ModelManager
from synapse.output import (
    print_critiques,
    print_dev_summary,
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
    mode = "simplified" if simplified else "detailed"
    result = run_council_result(topic, mode=mode)
    return result.final_answer


def run_council_result(
    topic: str,
    mode: str = "detailed",
    generations: int | None = None,
    survivors: int | None = None,
    save_run_flag: bool = False,
    output_file: str | None = None,
    manager: ModelManager | None = None,
    configured_models: dict[str, str] | None = None,
) -> RunResult:
    topic = topic.strip()
    if not topic:
        raise ValueError("No prompt entered.")

    max_generations = generations if generations is not None else MAX_GENERATIONS
    survivor_limit = survivors if survivors is not None else TOP_K_SURVIVORS
    if max_generations <= 0:
        raise ValueError("generations must be greater than 0.")
    if survivor_limit <= 0:
        raise ValueError("survivors must be greater than 0.")

    quiet = mode in {"quiet", "json"}
    configured = configured_models or MODELS
    manager = manager or ModelManager(
        configured,
        timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        verbose=not quiet,
    )

    events: List[DebugEvent] = []
    add_event(events, "CONFIG", f"mode={mode}, generations={max_generations}, survivors={survivor_limit}")

    usable_models = manager.refresh_available_models()
    missing_models = dict(getattr(manager, "missing_models", {}))
    add_event(
        events,
        "MODEL_CHECK",
        f"{len(usable_models)} usable model(s), {len(missing_models)} missing model(s)",
    )
    for key, model in missing_models.items():
        add_event(events, "MODEL_CHECK", f"missing configured model {key}: {model}", model=model)

    if not usable_models:
        add_event(events, "ERROR", "no usable Ollama models found")
        raise RuntimeError("No usable Ollama models found. Pull at least one configured model and try again.")

    if not quiet:
        print(f"Synapse is using {len(usable_models)} model(s).")

    ideas = generate_initial_ideas(topic, usable_models, manager)
    add_event(events, "GENERATION", f"created {len(ideas)} initial idea(s)", generation=0)
    if not ideas:
        add_event(events, "ERROR", "no valid ideas were generated")
        raise RuntimeError("No valid ideas were generated. Check Ollama and your installed models.")

    memory: List[GenerationMemory] = []
    final_ranked: List[Idea] = ideas
    snapshots: List[GenerationSnapshot] = []

    for generation in range(max_generations):
        if mode == "detailed":
            section(f"GENERATION {generation}")
            print_generated_ideas(ideas)

        critiques = critique_ideas(topic, ideas, usable_models, manager)
        add_event(events, "CRITIQUE", f"recorded {len(critiques)} critique(s)", generation=generation)
        for critique in critiques[:5]:
            add_event(
                events,
                "CRITIQUE",
                f"weakness: {critique.main_weakness}",
                model=critique.critic_model,
                idea_id=critique.idea_id,
                generation=generation,
            )
        if mode == "detailed":
            print_critiques(critiques)
        critique_summaries = summarize_critiques(critiques)

        def record_tournament_warning(message: str, model: str, idea_a_id: str, idea_b_id: str) -> None:
            add_event(
                events,
                "TOURNAMENT",
                f"warning: {message}",
                model=model,
                idea_id=f"{idea_a_id} vs {idea_b_id}",
                generation=generation,
            )

        ranked, comparisons = run_pairwise_tournament(
            topic,
            ideas,
            usable_models,
            manager,
            warning_handler=record_tournament_warning,
            print_warnings=mode in {"detailed", "dev", "simplified"},
        )
        final_ranked = ranked
        add_event(events, "TOURNAMENT", f"recorded {len(comparisons)} valid comparison(s)", generation=generation)
        for item in comparisons[:6]:
            add_event(
                events,
                "TOURNAMENT",
                f"{item.winner_id} beat {item.loser_id}: {item.reason}",
                model=item.judge_model,
                idea_id=item.winner_id,
                generation=generation,
            )
        if mode == "detailed":
            print_tournament(comparisons)
            print_ranking(ranked)

        generation_memory = build_generation_memory(topic, generation, ranked, manager, usable_models)
        memory.append(generation_memory)
        add_event(events, "GENERATION", "memory summary created", generation=generation)

        survivor_count = min(survivor_limit, len(ranked))
        survivor_ids = [idea.id for idea in ranked[:survivor_count]]
        if mode in {"simplified", "dev"}:
            print_generation_summary(
                generation=generation,
                ideas=ideas,
                critiques=critiques,
                comparisons=comparisons,
                ranked=ranked,
                memory=generation_memory,
                survivor_count=survivor_count,
            )
        elif mode == "detailed":
            print_memory(generation_memory)

        snapshots.append(
            GenerationSnapshot(
                generation=generation,
                ideas=copy.deepcopy(ideas),
                critiques=copy.deepcopy(critiques),
                comparisons=copy.deepcopy(comparisons),
                ranked=copy.deepcopy(ranked),
                memory=copy.deepcopy(generation_memory),
                survivor_ids=survivor_ids,
            )
        )

        if generation == max_generations - 1 or len(ranked) <= 1:
            break

        survivors_for_evolution = ranked[:survivor_count]
        ideas = evolve_survivors(
            topic=topic,
            survivors=survivors_for_evolution,
            critique_summaries=critique_summaries,
            comparisons=comparisons,
            memory=memory,
            models=usable_models,
            manager=manager,
            next_generation=generation + 1,
        )
        add_event(
            events,
            "EVOLUTION",
            f"created {len(ideas)} next-generation idea(s): {', '.join(idea.id for idea in ideas)}",
            generation=generation + 1,
        )

    winner = final_ranked[0]
    final_answer = synthesize_final_answer(topic, winner, memory, usable_models, manager)
    add_event(events, "SYNTHESIS", f"final answer synthesized from idea {winner.id}", idea_id=winner.id)

    result = RunResult(
        version=__version__,
        timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        topic=topic,
        config={
            "models": configured,
            "generations": max_generations,
            "survivors": survivor_limit,
            "mode": mode,
            "timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
        },
        usable_models=dict(usable_models),
        missing_models=missing_models,
        generations=snapshots,
        events=events,
        final_answer=final_answer,
    )

    if save_run_flag:
        add_event(result.events, "EXPORT", "saving run files under runs/")
        run_dir = save_run(result)
        result.events[-1].message = f"saved run to {run_dir}"
        save_run(result, base_dir=run_dir.parent)

    if output_file:
        add_event(result.events, "EXPORT", f"wrote JSON output to {output_file}")
        write_json_file(result, output_file)

    if mode == "json":
        print(run_result_to_json(result))
    elif mode == "dev":
        section("FINAL RESULT")
        print(final_answer)
        print_dev_summary(result)
    elif mode == "quiet":
        print(final_answer)
    else:
        section("FINAL RESULT")
        print(final_answer)

    return result


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


def add_event(
    events: List[DebugEvent],
    phase: str,
    message: str,
    model: str | None = None,
    idea_id: str | None = None,
    generation: int | None = None,
) -> None:
    events.append(
        DebugEvent(
            phase=phase,
            message=message,
            model=model,
            idea_id=idea_id,
            generation=generation,
        )
    )


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Synapse: local multi-agent idea evolution")
    parser.add_argument("topic", nargs="?", help="Prompt for the council")
    parser.add_argument("--prompt", help="Prompt for the council")
    parser.add_argument(
        "--mode",
        choices=["detailed", "simplified", "quiet", "dev", "json"],
        help="Output mode",
    )
    parser.add_argument("--save-run", action="store_true", help="Save run files under runs/")
    parser.add_argument("--output-file", help="Write full JSON result to a file")
    parser.add_argument("--generations", type=int, help="Override generation count")
    parser.add_argument("--survivors", type=int, help="Override survivors per generation")
    parser.add_argument("--version", action="store_true", help="Print the Synapse version and exit")
    parser.add_argument("--models", action="store_true", help="List configured Ollama model availability and exit")
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    if args.models:
        manager = ModelManager(MODELS, timeout_seconds=OLLAMA_TIMEOUT_SECONDS)
        usable = manager.refresh_available_models()
        print("Configured models:")
        for key, model in MODELS.items():
            status = "usable" if key in usable else "missing"
            print(f"- {key}: {model} ({status})")
        return

    topic = args.prompt or args.topic or input("Enter prompt: ").strip()
    mode = args.mode
    if mode is None:
        selected = input("Output mode: [d]etailed, [s]implified, [q]uiet, de[v], or [j]son? ").strip().lower()
        if selected.startswith("s"):
            mode = "simplified"
        elif selected.startswith("q"):
            mode = "quiet"
        elif selected.startswith("v"):
            mode = "dev"
        elif selected.startswith("j"):
            mode = "json"
        else:
            mode = "detailed"

    try:
        run_council_result(
            topic,
            mode=mode,
            generations=args.generations,
            survivors=args.survivors,
            save_run_flag=args.save_run,
            output_file=args.output_file,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"\nSynapse stopped: {exc}")
