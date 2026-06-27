# This file defines the data containers Synapse passes between steps.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Idea:
    id: str
    text: str
    author_model: str
    generation: int = 0
    parent_id: str | None = None
    parent_ids: List[str] = field(default_factory=list)
    origin: str = "generated"
    mutation_type: str | None = None
    role: str = ""
    title: str = ""
    summary: str = ""
    strengths: str = ""
    risks: str = ""
    assumptions: str = ""
    borrowed_from: str | None = None
    borrowed_element: str = ""
    diff_summary: str = ""
    risks_remaining: str = ""
    critiques: List["Critique"] = field(default_factory=list)
    wins: int = 0
    losses: int = 0

    def __post_init__(self) -> None:
        if self.parent_id and not self.parent_ids:
            self.parent_ids = [self.parent_id]
        elif self.parent_ids and not self.parent_id:
            self.parent_id = self.parent_ids[0]

    def reset_record(self) -> None:
        self.wins = 0
        self.losses = 0


@dataclass
class Critique:
    idea_id: str
    critic_model: str
    main_weakness: str
    risk: str
    missing_element: str
    unclear_assumption: str
    suggested_improvement: str
    raw_text: str
    critic_role: str = "Critic"
    strongest_part: str = ""
    weakest_part: str = ""
    hidden_assumption: str = ""
    biggest_risk: str = ""
    missing_detail: str = ""
    repair_suggestion: str = ""
    rubric_scores: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskRouting:
    task_type: str
    rubric: List[str]
    reason: str = ""


@dataclass
class Steelman:
    target_idea_id: str
    model: str
    role: str
    strongest_part: str
    best_use_case: str
    preserve_if_evolved: str
    raw_text: str


@dataclass
class Comparison:
    idea_a_id: str
    idea_b_id: str
    winner_id: str
    loser_id: str
    judge_model: str
    reason: str
    comparison_id: str = ""
    judge_role: str = "Judge"
    valid: bool = True
    stable: bool = True
    first_winner_id: str = ""
    second_winner_id: str = ""
    second_reason: str = ""


@dataclass
class Challenge:
    target_idea_id: str
    challenger_model: str
    challenger_role: str
    key_failure_mode: str
    weakest_assumption: str
    implementation_risk: str
    recommended_fix: str
    raw_text: str


@dataclass
class Verification:
    target_idea_id: str
    verifier_model: str
    verifier_role: str
    verdict: str
    unmet_requirements: str
    unsupported_claims: str
    logical_gaps: str
    major_risks: str
    required_fixes: str
    reasoning: str
    raw_text: str


@dataclass
class ConversationEvent:
    speaker: str
    round: str
    message: str
    target: str | None = None
    model: str | None = None
    generation: int | None = None


@dataclass
class GenerationMemory:
    generation: int
    summary: str


@dataclass
class DebugEvent:
    phase: str
    message: str
    model: str | None = None
    idea_id: str | None = None
    generation: int | None = None
    timestamp: str | None = None
    elapsed_s: float | None = None
    index: int | None = None


@dataclass
class GenerationSnapshot:
    generation: int
    ideas: List[Idea]
    steelmen: List[Steelman]
    critiques: List[Critique]
    comparisons: List[Comparison]
    ranked: List[Idea]
    memory: GenerationMemory
    survivor_ids: List[str]


@dataclass
class RunResult:
    version: str
    timestamp: str
    topic: str
    config: dict
    usable_models: dict[str, str]
    missing_models: dict[str, str]
    routing: TaskRouting | None = None
    generations: List[GenerationSnapshot] = field(default_factory=list)
    challenges: List[Challenge] = field(default_factory=list)
    verifications: List[Verification] = field(default_factory=list)
    conversation: List[ConversationEvent] = field(default_factory=list)
    events: List[DebugEvent] = field(default_factory=list)
    final_answer: str = ""
    run_directory: str | None = None
