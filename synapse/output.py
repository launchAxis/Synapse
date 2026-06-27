# This file controls what Synapse prints to the terminal.
from __future__ import annotations

from typing import Iterable, List

from synapse.ideas import Comparison, Critique, GenerationMemory, Idea, RunResult
from synapse.utils import compact, section


def print_generated_ideas(ideas: Iterable[Idea]) -> None:
    section("Generated Ideas")
    for idea in ideas:
        parent = f" parent={idea.parent_id}" if idea.parent_id else ""
        print(f"[{idea.id}] {idea.author_model} generation={idea.generation}{parent}")
        print(compact(idea.text, 500))
        print()


def print_critiques(critiques: Iterable[Critique]) -> None:
    section("Structured Critiques")
    for critique in critiques:
        print(f"Idea {critique.idea_id} by {critique.critic_model}")
        print(f"Main weakness: {compact(critique.main_weakness, 180)}")
        print(f"Risk: {compact(critique.risk, 180)}")
        print(f"Missing element: {compact(critique.missing_element, 180)}")
        print(f"Unclear assumption: {compact(critique.unclear_assumption, 180)}")
        print(f"Suggested improvement: {compact(critique.suggested_improvement, 220)}")
        print()


def print_tournament(comparisons: Iterable[Comparison]) -> None:
    section("Tournament Results")
    any_results = False
    for item in comparisons:
        if not item.valid:
            print(f"Invalid comparison {item.idea_a_id} vs {item.idea_b_id} ({item.judge_model})")
            print(f"Reason: {compact(item.reason, 240)}")
            continue
        if not item.stable:
            any_results = True
            print(f"Unstable comparison {item.idea_a_id} vs {item.idea_b_id} ({item.judge_model})")
            print(f"First pass winner: {item.first_winner_id or 'none'}")
            print(f"Second pass winner: {item.second_winner_id or 'none'}")
            print("No win awarded.")
            continue
        any_results = True
        print(f"{item.winner_id} beat {item.loser_id} ({item.judge_model})")
        print(f"Reason: {compact(item.reason, 240)}")
    if not any_results:
        print("No successful comparisons were recorded.")


def print_ranking(ranked: List[Idea]) -> None:
    section("Ranking")
    for index, idea in enumerate(ranked, start=1):
        win_word = "win" if idea.wins == 1 else "wins"
        loss_word = "loss" if idea.losses == 1 else "losses"
        print(f"{index}. Idea {idea.id} - {idea.wins} {win_word} / {idea.losses} {loss_word}")


def print_memory(memory: GenerationMemory) -> None:
    section("Generation Memory")
    print(memory.summary)



def print_generation_summary(
    generation: int,
    ideas: List[Idea],
    critiques: List[Critique],
    comparisons: List[Comparison],
    ranked: List[Idea],
    memory: GenerationMemory,
    survivor_count: int,
) -> None:
    section(f"GENERATION {generation} SUMMARY")

    print("Ideas:")
    for idea in ideas:
        parent = f", parent {idea.parent_id}" if idea.parent_id else ""
        print(f"- {idea.id} ({idea.author_model}{parent}): {compact(idea.text, 160)}")

    print("\nCritique highlights:")
    for idea in ideas:
        idea_critiques = [item for item in critiques if item.idea_id == idea.id]
        if not idea_critiques:
            print(f"- {idea.id}: no critique recorded")
            continue
        first = idea_critiques[0]
        print(
            f"- {idea.id}: weakness: {compact(first.main_weakness, 110)}; "
            f"improve: {compact(first.suggested_improvement, 110)}"
        )

    print("\nTournament:")
    if comparisons:
        stable_count = sum(1 for item in comparisons if item.valid and item.stable)
        unstable_count = sum(1 for item in comparisons if item.valid and not item.stable)
        invalid_count = sum(1 for item in comparisons if not item.valid)
        print(f"- {stable_count} stable, {unstable_count} unstable, {invalid_count} invalid comparisons recorded")
        for item in comparisons[:5]:
            if not item.valid:
                print(f"- invalid {item.idea_a_id} vs {item.idea_b_id}: {compact(item.reason, 120)}")
            elif not item.stable:
                print(f"- unstable {item.idea_a_id} vs {item.idea_b_id}: no win awarded")
            else:
                print(f"- {item.winner_id} beat {item.loser_id}: {compact(item.reason, 120)}")
        if len(comparisons) > 5:
            print(f"- ...and {len(comparisons) - 5} more comparisons")
    else:
        print("- no valid comparisons recorded")

    print("\nRanking / scores:")
    for index, idea in enumerate(ranked, start=1):
        print(f"{index}. {idea.id}: {idea.wins} wins / {idea.losses} losses")

    if ranked:
        print(f"\nGeneration winner: {ranked[0].id}")
        survivors = ranked[:survivor_count]
        print("Survivors: " + ", ".join(idea.id for idea in survivors))

    print("\nMemory:")
    print(compact(memory.summary, 420))


def print_dev_summary(result: RunResult) -> None:
    section("DEV MODE: DEBUG EVENTS")
    for event in result.events[-30:]:
        prefix = f"[{event.phase}]"
        details = []
        if event.generation is not None:
            details.append(f"generation={event.generation}")
        if event.model:
            details.append(f"model={event.model}")
        if event.idea_id:
            details.append(f"idea={event.idea_id}")
        detail_text = f" ({', '.join(details)})" if details else ""
        print(f"{prefix}{detail_text} {compact(event.message, 180)}")

    section("DEV MODE: MODEL NOTES")
    notes_printed = 0
    for snapshot in result.generations[-2:]:
        for critique in snapshot.critiques[:4]:
            print(
                f"Critique {critique.idea_id} by {critique.critic_model}: "
                f"{compact(critique.suggested_improvement, 180)}"
            )
            notes_printed += 1
        for comparison in snapshot.comparisons[:4]:
            if not comparison.valid:
                print(f"Judge {comparison.judge_model}: invalid comparison because {compact(comparison.reason, 180)}")
            elif not comparison.stable:
                print(
                    f"Judge {comparison.judge_model}: unstable {comparison.idea_a_id} vs "
                    f"{comparison.idea_b_id}; no win awarded"
                )
            else:
                print(
                    f"Judge {comparison.judge_model}: {comparison.winner_id} over "
                    f"{comparison.loser_id} because {compact(comparison.reason, 180)}"
                )
            notes_printed += 1

    if notes_printed == 0:
        print("No model notes were recorded.")
