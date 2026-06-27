from dataclasses import dataclass

from synapse.core import run_council_result


@dataclass
class FakeResponse:
    ok: bool
    text: str
    error: str = ""


class FakeManager:
    missing_models = {}

    def refresh_available_models(self):
        return {"A": "model-a", "B": "model-b"}

    def ask(self, model, prompt):
        if "Create one fresh outsider idea" in prompt:
            return FakeResponse(True, "Idea: A fresh outsider idea.")
        if "Generate one strong" in prompt:
            return FakeResponse(True, f"Idea: Initial idea from {model}.")
        if "structured critique" in prompt:
            return FakeResponse(
                True,
                "\n".join(
                    [
                        "MAIN_WEAKNESS: It needs sharper implementation detail.",
                        "RISK: It may be too broad.",
                        "MISSING_ELEMENT: A rollout plan.",
                        "UNCLEAR_ASSUMPTION: Users will adopt it quickly.",
                        "SUGGESTED_IMPROVEMENT: Add a small first milestone.",
                    ]
                ),
            )
        if "Choose which idea is stronger" in prompt or "previous judgment" in prompt:
            return FakeResponse(True, "WINNER: A\nREASON: Idea A is clearer.")
        if "final synthesizer" in prompt:
            return FakeResponse(True, "Final answer from fake model.")
        if "Generation" in prompt and "memory" in prompt:
            return FakeResponse(True, "- keep clarity\n- reduce breadth\n- add milestones")
        if "Evolve this surviving idea" in prompt:
            return FakeResponse(True, "Improved idea: A stronger evolved idea.")
        return FakeResponse(True, "Fallback response.")


def test_run_council_result_with_mocked_manager_collects_run_data():
    result = run_council_result(
        "Design a better note-taking app",
        mode="quiet",
        generations=2,
        survivors=2,
        manager=FakeManager(),
    )

    assert result.final_answer == "Final answer from fake model."
    assert len(result.generations) == 2
    assert any(event.phase == "TOURNAMENT" for event in result.events)
    assert any(idea.origin == "fresh" for idea in result.generations[1].ideas)
