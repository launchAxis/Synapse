from dataclasses import dataclass
from pathlib import Path

from synapse.core import run_council_result
from synapse.router import route_task
from synapse.tournament import parse_judgment


@dataclass
class FakeResponse:
    ok: bool
    text: str
    error: str = ""


class ProcessFakeManager:
    missing_models = {}

    def refresh_available_models(self):
        return {"A": "model-a", "B": "model-b", "C": "model-c"}

    def ask(self, model, prompt):
        if "Generate independently" in prompt or "Generate a new idea" in prompt:
            return FakeResponse(
                True,
                "\n".join(
                    [
                        "TITLE: Local-first Plan",
                        "SUMMARY: A practical candidate.",
                        "CONTENT: Build a focused local workflow with clear checkpoints.",
                        "STRENGTHS: Simple and inspectable.",
                        "RISKS: It may be too narrow.",
                        "ASSUMPTIONS: Users want local execution.",
                    ]
                ),
            )
        if "steelman this idea" in prompt:
            return FakeResponse(True, "STRONGEST_PART: The checkpoints.\nBEST_USE_CASE: Local planning.\nPRESERVE_IF_EVOLVED: Keep inspectability.")
        if "structured critique" in prompt:
            return FakeResponse(
                True,
                "STRONGEST_PART: It is clear.\nWEAKEST_PART: It needs a rollout.\nHIDDEN_ASSUMPTION: Users agree with defaults.\nBIGGEST_RISK: Scope creep.\nMISSING_DETAIL: Metrics.\nREPAIR_SUGGESTION: Add a first milestone.\nRUBRIC_SCORES: clarity=high",
            )
        if "Choose which idea is stronger" in prompt:
            return FakeResponse(True, "WINNER: Idea A\nREASON: Idea A is clearer.")
        if "Evolve this surviving idea" in prompt:
            return FakeResponse(
                True,
                "TITLE: Improved Plan\nSUMMARY: Stronger candidate.\nCONTENT: Keep checkpoints, add rollout, and borrow a concrete metric.\nBORROWED_ELEMENT: A concrete metric.\nDIFF_SUMMARY: Added rollout and metrics.\nRISKS_REMAINING: Adoption uncertainty.",
            )
        if "Stress-test this idea" in prompt:
            return FakeResponse(True, "KEY_FAILURE_MODE: No adoption.\nWEAKEST_ASSUMPTION: Clear demand.\nIMPLEMENTATION_RISK: Too many options.\nRECOMMENDED_FIX: Start with one workflow.")
        if "Verify the candidate" in prompt:
            return FakeResponse(True, "VERDICT: partial_pass\nUNMET_REQUIREMENTS: None major.\nUNSUPPORTED_CLAIMS: Some benefits.\nLOGICAL_GAPS: Adoption path.\nMAJOR_RISKS: Scope.\nREQUIRED_FIXES: Add pilot step.\nREASONING: Mostly aligned.")
        if "final synthesizer" in prompt:
            return FakeResponse(True, "Final v0.2.3 answer.")
        if "Generation" in prompt and "memory" in prompt:
            return FakeResponse(True, "- keep checkpoints\n- add metrics\n- pilot first")
        return FakeResponse(True, "Fallback.")


def test_route_task_selects_technical_rubric():
    routing = route_task("Create a technical plan to implement a plugin system")

    assert routing.task_type == "technical_plan"
    assert "correctness" in routing.rubric


def test_parse_judgment_accepts_required_idea_format():
    assert parse_judgment("WINNER: Idea B\nREASON: stronger trade-offs")[0] == "B"


def test_v024_process_records_all_required_stages():
    result = run_council_result(
        "Design a local developer workflow",
        mode="quick",
        manager=ProcessFakeManager(),
    )

    assert result.version == "0.3.0"
    assert result.routing.task_type == "creative_design"
    assert result.generations[0].steelmen
    assert result.generations[0].critiques
    assert result.generations[0].comparisons
    assert result.challenges
    assert result.verifications
    assert any(event.round == "challenge" for event in result.conversation)
    assert result.final_answer == "Final v0.2.3 answer."

    run_dir = Path(result.run_directory)
    assert (run_dir / "router.json").exists()
    assert (run_dir / "steelman.json").exists()
    assert (run_dir / "challenge.json").exists()
    assert (run_dir / "verification.json").exists()
    assert (run_dir / "dialogue_log.jsonl").exists()


def test_process_event_sink_receives_ordered_real_phase_events():
    live_events = []

    result = run_council_result(
        "Design a local developer workflow",
        mode="quick",
        manager=ProcessFakeManager(),
        event_sink=live_events.append,
    )

    phases = [event.phase for event in live_events]
    assert phases[0] == "CONFIG"
    assert "GENERATION" in phases
    assert "TOURNAMENT" in phases
    assert "SYNTHESIS" in phases
    assert "LOG" in phases
    assert [event.index for event in live_events if event.index is not None] == sorted(
        event.index for event in live_events if event.index is not None
    )
    assert live_events[-1].message.startswith("saved process logs to")
    assert result.events[-1].message == live_events[-1].message
