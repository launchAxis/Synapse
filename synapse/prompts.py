# This file stores the instructions sent to the AI models.
from __future__ import annotations

from typing import Iterable

from synapse.ideas import Challenge, Idea, GenerationMemory, Steelman, Verification
from synapse.utils import dedent


def memory_block(memory: Iterable[GenerationMemory]) -> str:
    lines = [item.summary for item in memory]
    if not lines:
        return "No generation memory yet."
    return "\n".join(f"- {line}" for line in lines[-3:])


def generation_prompt(topic: str, model_label: str, role: str = "Creator", task_type: str = "general", rubric: Iterable[str] = ()) -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    You are the {role} in Synapse, a local AI council. Generate independently.
    Do not assume what other agents will say.

    Task type: {task_type}
    Rubric: {rubric_text}

    Generate one strong, concrete idea for this prompt:
    {topic}

    Requirements:
    - Be specific.
    - Include the mechanism that makes the idea work.
    - Avoid generic answers.
    - Keep it concise enough for other models to critique.

    Use this exact structure:
    TITLE:
    SUMMARY:
    CONTENT:
    STRENGTHS:
    RISKS:
    ASSUMPTIONS:
    """)


def steelman_prompt(topic: str, idea: Idea, role: str, rubric: Iterable[str]) -> str:
    rubric_text = ", ".join(rubric)
    return dedent(f"""
    You are the {role} in Synapse. Before critique, steelman this idea.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

    Idea {idea.id}:
    {idea.text}

    Identify what is most worth preserving. Use this exact structure:
    STRONGEST_PART:
    BEST_USE_CASE:
    PRESERVE_IF_EVOLVED:
    """)


def fresh_outsider_prompt(topic: str, model_label: str, generation: int, existing_ideas: Iterable[Idea], task_type: str = "general", rubric: Iterable[str] = ()) -> str:
    idea_list = "\n".join(f"- {idea.id}: {idea.text[:220]}" for idea in existing_ideas)
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    You are the Outsider in Synapse, using model slot {model_label}.

    Generate a new idea that deliberately avoids the assumptions of the current leading ideas.
    It should answer the same user prompt, but it should not be a small edit of the current survivors.

    User prompt:
    {topic}

    Task type: {task_type}
    Rubric: {rubric_text}

    Current survivor direction:
    {idea_list or "No survivor ideas available."}

    Requirements:
    - Keep the idea useful and relevant.
    - Try a meaningfully different mechanism or angle.
    - Be concrete enough for other models to critique.

    Use this exact structure:
    TITLE:
    SUMMARY:
    CONTENT:
    STRENGTHS:
    RISKS:
    ASSUMPTIONS:
    """)


def critique_prompt(topic: str, idea: Idea, critic_label: str, critic_role: str = "Critic", rubric: Iterable[str] = ()) -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    You are the {critic_role} in Synapse, using model slot {critic_label}.
    Give a structured critique that is constructive and repair-oriented.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

    Idea {idea.id}:
    {idea.text}

    Use this exact structure and these exact uppercase labels:
    STRONGEST_PART:
    WEAKEST_PART:
    HIDDEN_ASSUMPTION:
    BIGGEST_RISK:
    MISSING_DETAIL:
    REPAIR_SUGGESTION:
    RUBRIC_SCORES:

    Be specific. Avoid vague praise. Keep each field to 1-2 sentences.
    Do not use Markdown headings, bullet lists, or extra sections.
    """)


def comparison_prompt(topic: str, idea_a: Idea, idea_b: Idea, judge_label: str, rubric: Iterable[str] = (), swapped: bool = False) -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    You are council judge {judge_label}. Choose which idea is stronger for the user's prompt.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

    Idea A ({idea_a.id}):
    {idea_a.text}

    Idea B ({idea_b.id}):
    {idea_b.text}

    Compare them directly using the rubric.

    Respond with this exact structure and no extra text:
    WINNER: Idea A
    REASON: <brief reason>

    The WINNER line must contain only Idea A or Idea B after the colon.
    """)


def strict_comparison_retry_prompt(topic: str, idea_a: Idea, idea_b: Idea, judge_label: str, previous_response: str, rubric: Iterable[str] = ()) -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    Your previous judgment could not be parsed clearly.

    Choose the stronger idea for the user's prompt using only this exact format:
    WINNER: Idea A
    REASON: <one sentence>

    Valid winners are only Idea A or Idea B.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

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
    steelman: Steelman | None,
    critique_summary: str,
    tournament_summary: str,
    memory: Iterable[GenerationMemory],
    model_label: str,
    defeated_idea: Idea | None = None,
    mutation_type: str = "fix_weakness",
) -> str:
    defeated_text = f"{defeated_idea.id}: {defeated_idea.text}" if defeated_idea else "No defeated idea available."
    preserve = steelman.preserve_if_evolved if steelman else idea.strengths or "Preserve the idea's strongest useful mechanism."
    return dedent(f"""
    You are council improver {model_label}. Evolve this surviving idea into a stronger next-generation version.

    User prompt:
    {topic}

    Previous idea {idea.id}:
    {idea.text}

    Strongest part to preserve:
    {preserve}

    Critiques received:
    {critique_summary}

    Tournament feedback:
    {tournament_summary}

    Generation memory:
    {memory_block(memory)}

    Mutation direction:
    {mutation_type}

    Borrow exactly one useful concrete element from this defeated idea:
    {defeated_text}

    Improve the idea according to the mutation direction while preserving its strongest parts.
    Fix its main weakness, address its biggest risk, and explain what changed.

    Use this exact structure:
    TITLE:
    SUMMARY:
    CONTENT:
    BORROWED_ELEMENT:
    DIFF_SUMMARY:
    RISKS_REMAINING:
    """)


def challenge_prompt(topic: str, idea: Idea, rubric: Iterable[str], role: str = "Challenger") -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    return dedent(f"""
    You are the {role} in Synapse. Stress-test this idea without rejecting it.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

    Idea {idea.id}:
    {idea.text}

    Use this exact structure:
    KEY_FAILURE_MODE:
    WEAKEST_ASSUMPTION:
    IMPLEMENTATION_RISK:
    RECOMMENDED_FIX:
    """)


def verification_prompt(topic: str, idea: Idea, challenges: Iterable[Challenge], rubric: Iterable[str], role: str = "Verifier") -> str:
    rubric_text = ", ".join(rubric) or "relevance, clarity, usefulness"
    challenge_text = "\n".join(
        f"- {item.target_idea_id}: {item.recommended_fix}" for item in challenges
    ) or "No challenge notes available."
    return dedent(f"""
    You are the {role} in Synapse. Verify the candidate against the original prompt, rubric, and consistency.

    User prompt:
    {topic}

    Rubric:
    {rubric_text}

    Candidate idea {idea.id}:
    {idea.text}

    Challenge fixes to consider:
    {challenge_text}

    Use this exact structure:
    VERDICT:
    UNMET_REQUIREMENTS:
    UNSUPPORTED_CLAIMS:
    LOGICAL_GAPS:
    MAJOR_RISKS:
    REQUIRED_FIXES:
    REASONING:

    VERDICT must be one of: pass, partial_pass, fail.
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


def final_prompt(
    topic: str,
    idea: Idea,
    memory: Iterable[GenerationMemory],
    borrowed_elements: Iterable[str] = (),
    outsider_ideas: Iterable[Idea] = (),
    challenges: Iterable[Challenge] = (),
    verifications: Iterable[Verification] = (),
) -> str:
    borrowed_text = "\n".join(f"- {item}" for item in borrowed_elements if item) or "No borrowed elements recorded."
    outsider_text = "\n".join(f"- {item.id}: {item.text[:260]}" for item in outsider_ideas) or "No outsider innovations survived."
    challenge_text = "\n".join(f"- {item.target_idea_id}: {item.recommended_fix}" for item in challenges) or "No challenge fixes recorded."
    verification_text = "\n".join(f"- {item.target_idea_id}: {item.verdict}; fixes: {item.required_fixes}" for item in verifications) or "No verification fixes recorded."
    return dedent(f"""
    You are the final synthesizer in Synapse.

    Write the best direct answer to the user's prompt. Do not simply copy the winning idea.
    Do not assume the topic is about education, students, teachers, offline tools, privacy, or low-cost
    devices unless the original user prompt asks for those things.

    User prompt:
    {topic}

    Winning evolved idea:
    {idea.text}

    Useful borrowed elements:
    {borrowed_text}

    Successful outsider innovations:
    {outsider_text}

    Challenge-round fixes:
    {challenge_text}

    Verification fixes:
    {verification_text}

    Generation memory:
    {memory_block(memory)}

    Combine the strongest surviving idea, useful borrowed elements, outsider innovations, challenge fixes,
    and verification fixes into one polished, concise answer.
    Use a topic-appropriate structure. Useful anchors include Clear title or name, Core concept, How it works,
    why it is strong, risks, and practical next steps.
    Do not wrap the answer in a markdown code block.
    """)
