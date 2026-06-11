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
    critiques: List["Critique"] = field(default_factory=list)
    wins: int = 0
    losses: int = 0

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
