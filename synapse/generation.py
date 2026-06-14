# This file creates the first set of ideas from the available Ollama models.
from __future__ import annotations

from typing import Dict, List

from synapse.ideas import Idea
from synapse.models import ModelManager
from synapse.prompts import generation_prompt
from synapse.utils import strip_response_label


def generate_initial_ideas(topic: str, models: Dict[str, str], manager: ModelManager) -> List[Idea]:
    ideas: List[Idea] = []

    for label, model in models.items():
        response = manager.ask(model, generation_prompt(topic, label))
        if not response.ok:
            continue

        ideas.append(
            Idea(
                id=label,
                text=strip_response_label(response.text, ["Idea"]),
                author_model=model,
                generation=0,
                origin="generated",
            )
        )

    return ideas
