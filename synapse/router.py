from __future__ import annotations

from synapse.ideas import TaskRouting


RUBRICS = {
    "creative_design": ["originality", "usefulness", "feasibility", "clarity", "depth"],
    "technical_plan": ["correctness", "simplicity", "maintainability", "implementation detail", "risk handling"],
    "strategy": ["impact", "feasibility", "scalability", "trade-offs", "clarity"],
    "explanation": ["accuracy", "completeness", "clarity", "examples", "structure"],
    "decision": ["criteria coverage", "trade-off analysis", "recommendation strength", "risk handling"],
    "debugging": ["root cause accuracy", "fix correctness", "prevention", "clarity"],
    "story": ["creativity", "coherence", "character", "pacing", "tone"],
    "research_outline": ["coverage", "structure", "source awareness", "feasibility", "novelty"],
    "general": ["relevance", "clarity", "usefulness", "completeness", "practicality"],
}


def route_task(prompt: str) -> TaskRouting:
    text = prompt.lower()
    task_type = "general"
    reason = "No strong task-specific keyword matched."

    keyword_routes = [
        ("debugging", ["bug", "debug", "traceback", "error", "failing", "fix this code", "exception"]),
        ("story", ["story", "novel", "scene", "character", "plot", "dialogue"]),
        ("research_outline", ["research", "literature", "sources", "paper outline", "study"]),
        ("technical_plan", ["architecture", "implement", "code", "software", "system design", "technical plan"]),
        ("decision", ["choose", "decide", "which option", "recommend", "trade off", "trade-off"]),
        ("strategy", ["strategy", "go-to-market", "business", "growth", "roadmap", "policy"]),
        ("explanation", ["explain", "teach", "how does", "why does", "summarize"]),
        ("creative_design", ["design", "invent", "brainstorm", "creative", "concept"]),
    ]

    for candidate, keywords in keyword_routes:
        if any(keyword in text for keyword in keywords):
            task_type = candidate
            reason = f"Matched {candidate} keyword."
            break

    return TaskRouting(task_type=task_type, rubric=RUBRICS[task_type], reason=reason)
