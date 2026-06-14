import json

from synapse.export import run_result_to_json
from synapse.ideas import DebugEvent, RunResult


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
