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


@dataclass
class Comparison:
    idea_a_id: str
    idea_b_id: str
    winner_id: str
    loser_id: str
    judge_model: str
    reason: str


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


@dataclass
class GenerationSnapshot:
    generation: int
    ideas: List[Idea]
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
    generations: List[GenerationSnapshot] = field(default_factory=list)
    events: List[DebugEvent] = field(default_factory=list)
    final_answer: str = ""
    run_directory: str | None = None
