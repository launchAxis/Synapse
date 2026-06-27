from __future__ import annotations

import argparse
import copy
from datetime import datetime
import time
from typing import Callable, List

from synapse import __version__
from synapse.config import (
    FINAL_SYNTHESIS_MODEL_KEY,
    MODELS,
    OLLAMA_TIMEOUT_SECONDS,
    SIMPLIFIED,
)
from synapse.challenge import challenge_ideas
from synapse.critique import critique_ideas, summarize_critiques
from synapse.evolution import evolve_survivors
from synapse.export import run_result_to_json, save_process_logs, save_run, write_json_file
from synapse.generation import DEFAULT_ROLES, generate_initial_ideas
from synapse.ideas import (
    Challenge,
    ConversationEvent,
    DebugEvent,
    GenerationMemory,
    GenerationSnapshot,
    Idea,
    RunResult,
    Steelman,
    Verification,
)
from synapse.memory import build_generation_memory
from synapse.model_presets import MODEL_PRESETS, phase_models, resolve_model_plan
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
from synapse.router import route_task
from synapse.steelman import steelman_ideas
from synapse.tournament import run_pairwise_tournament
from synapse.utils import section
from synapse.verification import verify_ideas


MODE_PRESETS = {
    "quick": {"generations": 2, "survivors": 2, "roles": DEFAULT_ROLES[:3], "finalists": 2},
    "balanced": {"generations": 2, "survivors": 2, "roles": DEFAULT_ROLES, "finalists": 2},
    "deep": {"generations": 3, "survivors": 3, "roles": DEFAULT_ROLES, "finalists": 3},
    "dev": {"generations": 3, "survivors": 3, "roles": DEFAULT_ROLES, "finalists": 3},
}


def run_council(topic: str, simplified: bool = SIMPLIFIED) -> str:
    mode = "quick" if simplified else "balanced"
    result = run_council_result(topic, mode=mode)
    return result.final_answer


def run_council_result(
    topic: str,
    mode: str = "balanced",
    generations: int | None = None,
    survivors: int | None = None,
    save_run_flag: bool = False,
    output_file: str | None = None,
    manager: ModelManager | None = None,
    configured_models: dict[str, str] | None = None,
    model_preset: str = "local",
    event_sink: Callable[[DebugEvent], None] | None = None,
) -> RunResult:
    topic = topic.strip()
    if not topic:
        raise ValueError("No prompt entered.")

    requested_mode = mode
    preset_name = normalize_process_mode(mode)
    preset = MODE_PRESETS[preset_name]
    max_generations = generations if generations is not None else preset["generations"]
    survivor_limit = survivors if survivors is not None else preset["survivors"]
    if max_generations <= 0:
        raise ValueError("generations must be greater than 0.")
    if survivor_limit <= 0:
        raise ValueError("survivors must be greater than 0.")

    quiet = mode in {"quiet", "json"}
    model_plan = resolve_model_plan(model_preset, configured_models or MODELS)
    configured = model_plan.configured_models
    manager = manager or ModelManager(
        configured,
        timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        verbose=not quiet,
    )

    events: List[DebugEvent] = []
    conversation: List[ConversationEvent] = []
    started_at = time.perf_counter()

    def emit_event(
        phase: str,
        message: str,
        model: str | None = None,
        idea_id: str | None = None,
        generation: int | None = None,
    ) -> None:
        add_event(
            events,
            phase,
            message,
            model=model,
            idea_id=idea_id,
            generation=generation,
            started_at=started_at,
            event_sink=event_sink,
        )

    emit_event(
        "CONFIG",
        f"mode={requested_mode}, process={preset_name}, model_preset={model_plan.preset}, generations={max_generations}, survivors={survivor_limit}",
    )

    usable_models = manager.refresh_available_models()
    missing_models = dict(getattr(manager, "missing_models", {}))
    council_models, judge_models, synthesis_model = phase_models(usable_models, model_plan)
    emit_event(
        "MODEL_CHECK",
        f"{len(usable_models)} usable model(s), {len(missing_models)} missing model(s)",
    )
    for key, model in missing_models.items():
        emit_event("MODEL_CHECK", f"missing configured model {key}: {model}", model=model)

    if not council_models:
        emit_event("ERROR", "no usable council models found")
        raise RuntimeError("No usable council models found. Pull at least one configured Ollama model or choose an available provider ref.")

    if not quiet:
        print(f"Synapse is using {len(usable_models)} model(s).")

    routing = route_task(topic)
    emit_event("ROUTER", f"task_type={routing.task_type}; rubric={', '.join(routing.rubric)}")
    add_conversation(conversation, "Router", "router", routing.reason)

    ideas = generate_initial_ideas(
        topic,
        council_models,
        manager,
        roles=preset["roles"],
        task_type=routing.task_type,
        rubric=routing.rubric,
    )
    emit_event("GENERATION", f"created {len(ideas)} initial idea(s)", generation=0)
    for idea in ideas:
        add_conversation(conversation, idea.role or idea.id, "generation", idea.summary or idea.text, target=idea.id, model=idea.author_model, generation=0)
    if not ideas:
        emit_event("ERROR", "no valid ideas were generated")
        raise RuntimeError("No valid ideas were generated. Check Ollama and your installed models.")

    memory: List[GenerationMemory] = []
    final_ranked: List[Idea] = ideas
    snapshots: List[GenerationSnapshot] = []

    for generation in range(max_generations):
        if mode == "detailed":
            section(f"GENERATION {generation}")
            print_generated_ideas(ideas)

        steelmen = steelman_ideas(topic, ideas, council_models, manager, routing.rubric)
        emit_event("STEELMAN", f"recorded {len(steelmen)} steelman note(s)", generation=generation)
        for steelman in steelmen:
            add_conversation(
                conversation,
                steelman.role,
                "steelman",
                steelman.preserve_if_evolved,
                target=steelman.target_idea_id,
                model=steelman.model,
                generation=generation,
            )

        critiques = critique_ideas(topic, ideas, council_models, manager, rubric=routing.rubric)
        emit_event("CRITIQUE", f"recorded {len(critiques)} critique(s)", generation=generation)
        for critique in critiques[:5]:
            emit_event(
                "CRITIQUE",
                f"weakness: {critique.main_weakness}",
                model=critique.critic_model,
                idea_id=critique.idea_id,
                generation=generation,
            )
            add_conversation(
                conversation,
                critique.critic_role,
                "critique",
                critique.repair_suggestion,
                target=critique.idea_id,
                model=critique.critic_model,
                generation=generation,
            )
        if mode == "detailed":
            print_critiques(critiques)
        critique_summaries = summarize_critiques(critiques)

        ranked, comparisons = run_pairwise_tournament(
            topic,
            ideas,
            judge_models,
            manager,
            rubric=routing.rubric,
            verbose=not quiet,
        )
        final_ranked = ranked
        stable_comparisons = [item for item in comparisons if item.valid and item.stable]
        unstable_comparisons = [item for item in comparisons if item.valid and not item.stable]
        invalid_comparisons = [item for item in comparisons if not item.valid]
        emit_event(
            "TOURNAMENT",
            f"recorded {len(stable_comparisons)} stable, {len(unstable_comparisons)} unstable, {len(invalid_comparisons)} invalid comparison(s)",
            generation=generation,
        )
        for item in comparisons[:6]:
            if not item.valid:
                emit_event(
                    "TOURNAMENT",
                    f"warning: invalid judgment for {item.idea_a_id} vs {item.idea_b_id}: {item.reason}",
                    model=item.judge_model,
                    generation=generation,
                )
                continue
            if not item.stable:
                emit_event(
                    "TOURNAMENT",
                    f"unstable judgment for {item.idea_a_id} vs {item.idea_b_id}: first={item.first_winner_id or 'none'}, second={item.second_winner_id or 'none'}; no win awarded",
                    model=item.judge_model,
                    generation=generation,
                )
                add_conversation(
                    conversation,
                    item.judge_role,
                    "tournament",
                    f"unstable comparison for {item.idea_a_id} vs {item.idea_b_id}; no win awarded",
                    target=item.comparison_id,
                    model=item.judge_model,
                    generation=generation,
                )
                continue
            emit_event(
                "TOURNAMENT",
                f"{item.winner_id} beat {item.loser_id}: {item.reason}",
                model=item.judge_model,
                idea_id=item.winner_id,
                generation=generation,
            )
            add_conversation(
                conversation,
                item.judge_role,
                "tournament",
                f"{item.winner_id} over {item.loser_id}: {item.reason}",
                target=item.comparison_id,
                model=item.judge_model,
                generation=generation,
            )
        if mode == "detailed":
            print_tournament(comparisons)
            print_ranking(ranked)

        generation_memory = build_generation_memory(topic, generation, ranked, manager, council_models)
        memory.append(generation_memory)
        emit_event("GENERATION", "memory summary created", generation=generation)

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
                steelmen=copy.deepcopy(steelmen),
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
        defeated_for_borrowing = ranked[survivor_count:] or ranked[survivor_count - 1:]
        ideas = evolve_survivors(
            topic=topic,
            survivors=survivors_for_evolution,
            critique_summaries=critique_summaries,
            comparisons=comparisons,
            memory=memory,
            models=council_models,
            manager=manager,
            next_generation=generation + 1,
            steelmen=steelmen,
            defeated_ideas=defeated_for_borrowing,
            task_type=routing.task_type,
            rubric=routing.rubric,
        )
        emit_event(
            "EVOLUTION",
            f"created {len(ideas)} next-generation idea(s): {', '.join(idea.id for idea in ideas)}",
            generation=generation + 1,
        )
        for idea in ideas:
            add_conversation(
                conversation,
                idea.role or "Improver",
                "evolution" if idea.origin == "evolved" else "outsider",
                idea.diff_summary or idea.summary or idea.text,
                target=idea.id,
                model=idea.author_model,
                generation=generation + 1,
            )

    finalists = final_ranked[: min(preset["finalists"], len(final_ranked))]
    challenges = challenge_ideas(topic, finalists, council_models, manager, routing.rubric)
    emit_event("CHALLENGE", f"recorded {len(challenges)} challenge note(s)")
    for challenge in challenges:
        add_conversation(
            conversation,
            challenge.challenger_role,
            "challenge",
            challenge.recommended_fix,
            target=challenge.target_idea_id,
            model=challenge.challenger_model,
        )

    verifications = verify_ideas(topic, finalists, challenges, council_models, manager, routing.rubric)
    emit_event("VERIFY", f"recorded {len(verifications)} verification result(s)")
    for verification in verifications:
        add_conversation(
            conversation,
            verification.verifier_role,
            "verification",
            f"{verification.verdict}: {verification.required_fixes}",
            target=verification.target_idea_id,
            model=verification.verifier_model,
        )

    winner = choose_verified_winner(final_ranked, verifications)
    final_answer = synthesize_final_answer(
        topic,
        winner,
        memory,
        council_models,
        manager,
        challenges,
        verifications,
        final_ranked,
        synthesis_model=synthesis_model,
    )
    emit_event("SYNTHESIS", f"final answer synthesized from idea {winner.id}", idea_id=winner.id)
    add_conversation(conversation, "Synthesizer", "synthesis", final_answer, target=winner.id)

    result = RunResult(
        version=__version__,
        timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        topic=topic,
        config={
            "models": configured,
            "generations": max_generations,
            "survivors": survivor_limit,
            "mode": requested_mode,
            "process_mode": preset_name,
            "model_preset": model_plan.preset,
            "roles": preset["roles"],
            "timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "phase_models": {
                "council": council_models,
                "judge": judge_models,
                "synthesis": synthesis_model,
            },
        },
        usable_models=dict(usable_models),
        missing_models=missing_models,
        routing=routing,
        generations=snapshots,
        challenges=challenges,
        verifications=verifications,
        conversation=conversation,
        events=events,
        final_answer=final_answer,
    )

    emit_event("LOG", "saving process logs under logs/")
    run_dir = save_process_logs(result)
    result.events[-1].message = f"saved process logs to {run_dir}"
    if event_sink is not None:
        event_sink(result.events[-1])

    if save_run_flag:
        emit_event("EXPORT", "saving run files under runs/")
        run_dir = save_run(result)
        result.events[-1].message = f"saved run to {run_dir}"
        if event_sink is not None:
            event_sink(result.events[-1])

    if output_file:
        emit_event("EXPORT", f"wrote JSON output to {output_file}")
        write_json_file(result, output_file)

    if mode == "json":
        print(run_result_to_json(result))
    elif mode == "dev":
        section("FINAL RESULT")
        print(final_answer)
        print_dev_summary(result)
        print(f"\nLogs: {result.run_directory}")
    elif mode != "quiet":
        section("FINAL RESULT")
        print(final_answer)

    return result


def synthesize_final_answer(
    topic: str,
    winner: Idea,
    memory: List[GenerationMemory],
    models: dict[str, str],
    manager: ModelManager,
    challenges: List[Challenge] | None = None,
    verifications: List[Verification] | None = None,
    ranked: List[Idea] | None = None,
    synthesis_model: str | None = None,
) -> str:
    model = synthesis_model or models.get(FINAL_SYNTHESIS_MODEL_KEY) or next(iter(models.values()))
    ranked = ranked or [winner]
    borrowed = [idea.borrowed_element for idea in ranked if idea.borrowed_element]
    outsiders = [idea for idea in ranked if idea.origin == "fresh"]
    response = manager.ask(
        model,
        final_prompt(topic, winner, memory, borrowed, outsiders, challenges or [], verifications or []),
    )
    if response.ok:
        return response.text
    return winner.text


def normalize_process_mode(mode: str) -> str:
    if mode in MODE_PRESETS:
        return mode
    if mode in {"quiet", "json", "detailed"}:
        return "balanced"
    if mode == "simplified":
        return "quick"
    return "balanced"


def choose_verified_winner(ranked: List[Idea], verifications: List[Verification]) -> Idea:
    verdict_rank = {"pass": 0, "partial_pass": 1, "fail": 2}
    verification_by_id = {item.target_idea_id: item for item in verifications}
    return sorted(
        ranked,
        key=lambda idea: (
            verdict_rank.get(verification_by_id.get(idea.id, Verification("", "", "", "partial_pass", "", "", "", "", "", "", "")).verdict, 1),
            -idea.wins,
            idea.losses,
            idea.id,
        ),
    )[0]


def add_event(
    events: List[DebugEvent],
    phase: str,
    message: str,
    model: str | None = None,
    idea_id: str | None = None,
    generation: int | None = None,
    started_at: float | None = None,
    event_sink: Callable[[DebugEvent], None] | None = None,
) -> None:
    event = DebugEvent(
        phase=phase,
        message=message,
        model=model,
        idea_id=idea_id,
        generation=generation,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        elapsed_s=round(time.perf_counter() - started_at, 3) if started_at is not None else None,
        index=len(events) + 1,
    )
    events.append(event)
    if event_sink is not None:
        event_sink(event)


def add_conversation(
    conversation: List[ConversationEvent],
    speaker: str,
    round_name: str,
    message: str,
    target: str | None = None,
    model: str | None = None,
    generation: int | None = None,
) -> None:
    conversation.append(
        ConversationEvent(
            speaker=speaker,
            round=round_name,
            target=target,
            message=message,
            model=model,
            generation=generation,
        )
    )


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Synapse: local multi-agent idea evolution")
    parser.add_argument("topic", nargs="?", help="Prompt for the council")
    parser.add_argument("--prompt", help="Prompt for the council")
    parser.add_argument("--api", action="store_true", help="Start the local HTTP API server")
    parser.add_argument("--host", default="127.0.0.1", help="API host when using --api")
    parser.add_argument("--port", type=int, default=8765, help="API port when using --api")
    parser.add_argument("--tui", action="store_true", help="Start the Synapse Council terminal UI")
    parser.add_argument("--no-color", action="store_true", help="Disable terminal UI color")
    parser.add_argument("--unicode-logo", action="store_true", help="Use the Unicode Synapse node logo in the terminal UI")
    parser.add_argument(
        "--mode",
        choices=["quick", "balanced", "deep", "dev", "detailed", "simplified", "quiet", "json"],
        help="Output mode",
    )
    parser.add_argument("--save-run", action="store_true", help="Save run files under runs/")
    parser.add_argument("--output-file", help="Write full JSON result to a file")
    parser.add_argument("--generations", type=int, help="Override generation count")
    parser.add_argument("--survivors", type=int, help="Override survivors per generation")
    parser.add_argument(
        "--model-preset",
        choices=sorted(MODEL_PRESETS),
        default="local",
        help="Model preset: local, hybrid, or strong",
    )
    parser.add_argument("--version", action="store_true", help="Print the Synapse version and exit")
    parser.add_argument("--models", action="store_true", help="List configured Ollama model availability and exit")
    args = parser.parse_args()

    if args.api:
        from synapse.api import serve_api

        serve_api(args.host, args.port)
        return

    if args.tui:
        from synapse.tui import run_tui

        run_tui(color=not args.no_color, unicode_logo=args.unicode_logo)
        return

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
        selected = input("Mode: [b]alanced, [q]uick, [d]eep, de[v], [j]son, or quie[t]? ").strip().lower()
        if selected.startswith("q"):
            mode = "quick"
        elif selected.startswith("d"):
            mode = "deep"
        elif selected.startswith("v"):
            mode = "dev"
        elif selected.startswith("j"):
            mode = "json"
        elif selected.startswith("t"):
            mode = "quiet"
        else:
            mode = "balanced"

    try:
        run_council_result(
            topic,
            mode=mode,
            generations=args.generations,
            survivors=args.survivors,
            save_run_flag=args.save_run,
            output_file=args.output_file,
            model_preset=args.model_preset,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"\nSynapse stopped: {exc}")
