from __future__ import annotations

import http.client
import json
import threading
import time
from dataclasses import dataclass

from synapse.api import create_api_server
from synapse.ideas import DebugEvent, RunResult, TaskRouting


def test_health_returns_json():
    with running_server() as base:
        status, payload = request_json(base, "GET", "/health")

    assert status == 200
    assert payload["status"] == "ok"
    assert payload["version"] == "0.3.0"
    assert payload["api"]["local_first"] is True


def test_models_returns_status_without_secrets(monkeypatch):
    monkeypatch.setenv("SYNAPSE_OPENAI_API_KEY", "sk-secret-value")
    with running_server(manager_factory=lambda: FakeManager()) as base:
        status, payload = request_json(base, "GET", "/models")

    serialized = json.dumps(payload)
    assert status == 200
    assert payload["configured_models"] == {"A": "qwen2.5:3b", "B": "missing:1b"}
    assert payload["usable_models"] == {"A": "qwen2.5:3b"}
    assert payload["missing_models"] == {"B": "missing:1b"}
    assert payload["providers"]["openai"]["configured"] is True
    assert "sk-secret-value" not in serialized


def test_run_invalid_json_returns_400():
    with running_server() as base:
        status, payload = request_json(base, "POST", "/run", raw_body="{bad json")

    assert status == 400
    assert "Invalid JSON" in payload["error"]


def test_run_empty_prompt_returns_400():
    with running_server() as base:
        status, payload = request_json(base, "POST", "/run", {"prompt": "   ", "mode": "quick"})

    assert status == 400
    assert "Prompt" in payload["error"]


def test_unsupported_path_returns_404():
    with running_server() as base:
        status, payload = request_json(base, "GET", "/missing")

    assert status == 404
    assert payload["error"] == "Not found."


def test_unsupported_method_returns_405():
    with running_server() as base:
        status, payload = request_json(base, "GET", "/run")

    assert status == 405
    assert payload["error"] == "Method not allowed."


def test_successful_run_returns_run_result_json():
    calls = []

    def fake_run(prompt, mode="balanced", generations=None, survivors=None):
        calls.append((prompt, mode, generations, survivors))
        return RunResult(
            version="0.3.0",
            timestamp="2026-06-15_12-00-00",
            topic=prompt,
            config={"mode": mode, "generations": generations, "survivors": survivors},
            usable_models={"A": "qwen2.5:3b"},
            missing_models={},
            routing=TaskRouting("creative_design", ["clarity"], "test route"),
            events=[DebugEvent("SYNTHESIS", "done")],
            final_answer="Final answer from mocked API run.",
        )

    with running_server(run_function=fake_run) as base:
        status, payload = request_json(
            base,
            "POST",
            "/run",
            {"prompt": "Design a local workflow", "mode": "quick", "generations": None, "survivors": 2},
        )

    assert status == 200
    assert payload["final_answer"] == "Final answer from mocked API run."
    assert payload["routing"]["task_type"] == "creative_design"
    assert calls == [("Design a local workflow", "quick", None, 2)]


def test_live_run_returns_status_and_sse_events():
    def fake_run(prompt, mode="balanced", generations=None, survivors=None, model_preset="local", event_sink=None):
        if event_sink:
            event_sink(DebugEvent("CONFIG", "ready", index=1))
            event_sink(DebugEvent("TOURNAMENT", "recorded 1 stable, 0 unstable, 0 invalid comparison(s)", generation=0, index=2))
        return RunResult(
            version="0.3.0",
            timestamp="2026-06-15_12-00-00",
            topic=prompt,
            config={"mode": mode, "model_preset": model_preset},
            usable_models={"A": "qwen2.5:3b"},
            missing_models={},
            events=[DebugEvent("CONFIG", "ready"), DebugEvent("SYNTHESIS", "done")],
            final_answer="Live final answer.",
        )

    with running_server(run_function=fake_run) as base:
        status, payload = request_json(
            base,
            "POST",
            "/runs",
            {"prompt": "Live run", "mode": "quick", "model_preset": "hybrid"},
        )
        assert status == 202
        run_id = payload["run_id"]

        sse_status, sse_body = request_text(base, "GET", payload["events_url"])
        status_code, status_payload = wait_for_run_status(base, run_id)

    assert sse_status == 200
    assert "event: event" in sse_body
    assert '"phase": "CONFIG"' in sse_body
    assert '"phase": "TOURNAMENT"' in sse_body
    assert "event: done" in sse_body
    assert status_code == 200
    assert status_payload["status"] == "complete"
    assert status_payload["model_preset"] == "hybrid"
    assert status_payload["result"]["final_answer"] == "Live final answer."


def test_live_run_invalid_model_preset_returns_400():
    with running_server() as base:
        status, payload = request_json(
            base,
            "POST",
            "/runs",
            {"prompt": "x", "mode": "quick", "model_preset": "massive"},
        )

    assert status == 400
    assert "model_preset" in payload["error"]


@dataclass
class FakeManager:
    configured_models: dict[str, str] | None = None
    missing_models: dict[str, str] | None = None
    available_model_names: set[str] | None = None

    def __post_init__(self):
        self.configured_models = {"A": "qwen2.5:3b", "B": "missing:1b"}
        self.missing_models = {"B": "missing:1b"}
        self.available_model_names = {"qwen2.5:3b"}

    def refresh_available_models(self):
        return {"A": "qwen2.5:3b"}


class running_server:
    def __init__(self, run_function=None, manager_factory=None):
        kwargs = {}
        if run_function is not None:
            kwargs["run_function"] = run_function
        if manager_factory is not None:
            kwargs["manager_factory"] = manager_factory
        self.server = create_api_server("127.0.0.1", 0, **kwargs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return ("127.0.0.1", self.server.server_port)

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def request_json(base, method, path, payload=None, raw_body=None):
    host, port = base
    body = raw_body if raw_body is not None else (json.dumps(payload).encode("utf-8") if payload is not None else None)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection = http.client.HTTPConnection(host, port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        return response.status, data
    finally:
        connection.close()


def request_text(base, method, path):
    host, port = base
    connection = http.client.HTTPConnection(host, port, timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def wait_for_run_status(base, run_id):
    for _ in range(20):
        status, payload = request_json(base, "GET", f"/runs/{run_id}")
        if payload.get("status") in {"complete", "error"}:
            return status, payload
        time.sleep(0.05)
    return request_json(base, "GET", f"/runs/{run_id}")
