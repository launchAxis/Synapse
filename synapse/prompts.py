# This file stores the instructions sent to the AI models.
from __future__ import annotations

from typing import Iterable

from synapse.ideas import Idea, GenerationMemory
from synapse.utils import dedent


def memory_block(memory: Iterable[GenerationMemory]) -> str:
    lines = [item.summary for item in memory]
    if not lines:
        return "No generation memory yet."
    return "\n".join(f"- {line}" for line in lines[-3:])


def generation_prompt(topic: str, model_label: str) -> str:
    return dedent(f"""
    You are council member {model_label} in Synapse, a local AI council.

    Generate one strong, concrete idea for this prompt:
    {topic}

    Requirements:
    - Be specific.
    - Include the mechanism that makes the idea work.
    - Avoid generic answers.
    - Keep it concise enough for other models to critique.

    Output:
    Idea:
    <your idea>
    """)


def fresh_outsider_prompt(topic: str, model_label: str, generation: int, existing_ideas: Iterable[Idea]) -> str:
    idea_list = "\n".join(f"- {idea.id}: {idea.text[:220]}" for idea in existing_ideas)
    return dedent(f"""
    You are council member {model_label} in Synapse.

    Create one fresh outsider idea for generation {generation}. It should answer the same user prompt, but it
    should not be a small edit of the current survivors.

    User prompt:
    {topic}

    Current survivor direction:
    {idea_list or "No survivor ideas available."}

    Requirements:
    - Keep the idea useful and relevant.
    - Try a meaningfully different mechanism or angle.
    - Be concrete enough for other models to critique.

    Output:
    Idea:
    <fresh outsider idea>
    """)


def critique_prompt(topic: str, idea: Idea, critic_label: str) -> str:
    return dedent(f"""
    You are council critic {critic_label}. Give a structured critique that can help improve the idea.

    User prompt:
    {topic}

    Idea {idea.id}:
    {idea.text}

    Use this exact structure and these exact uppercase labels:
    MAIN_WEAKNESS:
    RISK:
    MISSING_ELEMENT:
    UNCLEAR_ASSUMPTION:
    SUGGESTED_IMPROVEMENT:

    Be specific. Avoid vague praise. Keep each field to 1-2 sentences.
    Do not use Markdown headings, bullet lists, or extra sections.
    """)


def comparison_prompt(topic: str, idea_a: Idea, idea_b: Idea, judge_label: str) -> str:
    return dedent(f"""
    You are council judge {judge_label}. Choose which idea is stronger for the user's prompt.

    User prompt:
    {topic}

    Idea A ({idea_a.id}):
    {idea_a.text}

    Idea B ({idea_b.id}):
    {idea_b.text}

    Compare them directly. Prefer the idea that is clearer, more useful, more original, and easier to improve.

    Respond with this exact structure and no extra text:
    WINNER: A
    REASON: <brief reason>

    The WINNER line must contain only A or B after the colon.
    """)


def strict_comparison_retry_prompt(topic: str, idea_a: Idea, idea_b: Idea, judge_label: str, previous_response: str) -> str:
    return dedent(f"""
    Your previous judgment could not be parsed clearly.

    Choose the stronger idea for the user's prompt using only this exact format:
    WINNER: A
    REASON: <one sentence>

    Valid winners are only A or B.

    User prompt:
    {topic}

    Idea A ({idea_a.id}):
    {idea_a.text}

    Idea B ({idea_b.id}):
    {idea_b.text}

    Previous unclear response:
    {previous_response}
    """)


def evolution_prompt(
    topic: str,
    idea: Idea,
    critique_summary: str,
    tournament_summary: str,
    memory: Iterable[GenerationMemory],
    model_label: str,
    mutation_type: str = "fix_weakness",
) -> str:
    return dedent(f"""
    You are council improver {model_label}. Evolve this surviving idea into a stronger next-generation version.

    User prompt:
    {topic}

    Previous idea {idea.id}:
    {idea.text}

    Critiques received:
    {critique_summary}

    Tournament feedback:
    {tournament_summary}

    Generation memory:
    {memory_block(memory)}

    Mutation direction:
    {mutation_type}

    Improve the idea according to the mutation direction while preserving its strongest parts.
    Preserve what made this surviving idea distinct.
    Do not simply rename it into the current winner or copy another survivor.
    If multiple survivors remain, maintain this as a meaningful alternative approach.

    Output:
    Improved idea:
    <next-generation idea>
    """)


def memory_prompt(topic: str, ranked_ideas: list[Idea], generation: int) -> str:
    ranking = "\n".join(
        f"{index + 1}. {idea.id}: {idea.wins} wins / {idea.losses} losses - {idea.text[:240]}"
        for index, idea in enumerate(ranked_ideas)
    )
    return dedent(f"""
    Generation {generation} memory for prompt:
    {topic}

    Ranking:
    {ranking}

    Write exactly 3 short bullets:
    - strongest features from winning ideas
    - repeated weaknesses or mistakes
    - what the next generation should improve

    Keep the whole memory under 140 words.
    """)


def final_prompt(topic: str, idea: Idea, memory: Iterable[GenerationMemory]) -> str:
    return dedent(f"""
    You are the final synthesizer in Synapse.

    Turn the strongest evolved idea into the best direct answer to the user's prompt.
    Do not assume the topic is about education, students, teachers, offline tools, privacy, or low-cost
    devices unless the original user prompt asks for those things.

    User prompt:
    {topic}

    Winning evolved idea:
    {idea.text}

    Generation memory:
    {memory_block(memory)}

    Write a complete, topic-appropriate final answer with these anchors:
    1. Clear title or name
    2. Core concept
    3. How it works
    4. Why it is strong
    5. Key features or components
    6. Possible weaknesses or risks
    7. Practical next steps or implementation roadmap
    8. Polished final version

    Do not mainly summarize the tournament memory. Use it only to strengthen the final proposal.
    Do not wrap the answer in a markdown code block.
    """)
