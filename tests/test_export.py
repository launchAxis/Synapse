import json

from synapse.export import evaluation_summary, run_result_to_json, save_process_logs
from synapse.ideas import Comparison, DebugEvent, GenerationSnapshot, Idea, GenerationMemory, RunResult, Verification


def test_run_result_serializes_to_json():
    result = RunResult(
        version="0.2.2",
        timestamp="2026-06-13_12-00-00",
        topic="Test topic",
        config={"generations": 1},
        usable_models={"A": "model-a"},
        missing_models={},
        events=[DebugEvent(phase="CONFIG", message="ready")],
        final_answer="Final answer",
    )

    data = json.loads(run_result_to_json(result))

    assert data["version"] == "0.2.2"
    assert data["events"][0]["phase"] == "CONFIG"
    assert data["final_answer"] == "Final answer"


def test_save_process_logs_writes_evaluation_summary(tmp_path):
    result = RunResult(
        version="0.3.0",
        timestamp="2026-06-15_12-00-00",
        topic="Test topic",
        config={
            "mode": "quick",
            "process_mode": "quick",
            "model_preset": "local",
            "models": {"A": "qwen2.5:3b", "J": "openai:gpt-test"},
        },
        usable_models={"A": "qwen2.5:3b"},
        missing_models={"J": "openai:gpt-test"},
        events=[
            DebugEvent(phase="CONFIG", message="ready", elapsed_s=0.0),
            DebugEvent(phase="TOURNAMENT", message="done", elapsed_s=1.2),
        ],
        generations=[
            GenerationSnapshot(
                generation=0,
                ideas=[Idea(id="I001", text="idea", author_model="qwen2.5:3b")],
                steelmen=[],
                critiques=[],
                comparisons=[
                    Comparison("I001", "I002", "I001", "I002", "qwen2.5:3b", "clear"),
                    Comparison("I003", "I004", "", "", "qwen2.5:3b", "bias", valid=True, stable=False),
                    Comparison("I005", "I006", "", "", "qwen2.5:3b", "bad", valid=False, stable=False),
                ],
                ranked=[],
                memory=GenerationMemory(0, "memory"),
                survivor_ids=[],
            )
        ],
        verifications=[
            Verification("I001", "qwen2.5:3b", "Verifier", "partial_pass", "", "", "", "", "", "", "")
        ],
        final_answer="Final answer",
    )

    run_dir = save_process_logs(result, base_dir=tmp_path)
    summary = json.loads((run_dir / "evaluation_summary.json").read_text(encoding="utf-8"))

    assert summary["model_preset"] == "local"
    assert summary["providers"]["A"]["provider"] == "ollama"
    assert summary["providers"]["J"]["provider"] == "openai"
    assert summary["tournament"] == {"stable": 1, "unstable": 1, "invalid": 1}
    assert summary["verification_verdicts"] == {"partial_pass": 1}
    assert summary["final_answer_length"] == len("Final answer")


def test_evaluation_summary_does_not_create_training_data():
    result = RunResult(
        version="0.3.0",
        timestamp="2026-06-15_12-00-00",
        topic="Test topic",
        config={"models": {"A": "qwen2.5:3b"}},
        usable_models={},
        missing_models={},
        final_answer="Final answer",
    )

    summary = evaluation_summary(result)

    assert "training" not in json.dumps(summary).lower()
