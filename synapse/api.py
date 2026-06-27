from __future__ import annotations

import contextlib
import io
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import Callable

from synapse import __version__
from synapse.config import MODELS, OLLAMA_TIMEOUT_SECONDS
from synapse.core import run_council_result
from synapse.export import run_result_to_dict
from synapse.ideas import DebugEvent
from synapse.models import ModelManager
from synapse.providers import ProviderRouter, redact_secrets


RunFunction = Callable[..., object]
ManagerFactory = Callable[[], ModelManager]


@dataclass
class RunRecord:
    run_id: str
    prompt: str
    mode: str
    model_preset: str
    generations: int | None
    survivors: int | None
    status: str = "queued"
    events: list[dict] = field(default_factory=list)
    result: dict | None = None
    error: str = ""
    condition: threading.Condition = field(default_factory=threading.Condition)

    def add_event(self, event: DebugEvent) -> None:
        with self.condition:
            self.events.append(asdict(event))
            self.condition.notify_all()

    def finish(self, status: str, result: dict | None = None, error: str = "") -> None:
        with self.condition:
            self.status = status
            self.result = result
            self.error = redact_secrets(error)
            self.condition.notify_all()

    def wait_for_events(self, cursor: int, timeout: int = 15) -> tuple[list[dict], bool]:
        with self.condition:
            if cursor >= len(self.events) and self.status not in {"complete", "error"}:
                self.condition.wait(timeout=timeout)
            return self.events[cursor:], self.status in {"complete", "error"}

    def status_payload(self, include_result: bool = True) -> dict:
        payload = {
            "run_id": self.run_id,
            "status": self.status,
            "mode": self.mode,
            "model_preset": self.model_preset,
            "event_count": len(self.events),
            "error": self.error or None,
        }
        if include_result:
            payload["result"] = self.result
        return payload


class RunRegistry:
    def __init__(self, run_function: RunFunction):
        self.run_function = run_function
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def start(
        self,
        prompt: str,
        mode: str,
        generations: int | None,
        survivors: int | None,
        model_preset: str,
    ) -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        record = RunRecord(
            run_id=run_id,
            prompt=prompt,
            mode=mode,
            model_preset=model_preset,
            generations=generations,
            survivors=survivors,
        )
        with self._lock:
            self._runs[run_id] = record
        thread = threading.Thread(target=self._run, args=(record,), daemon=True)
        thread.start()
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def status_payload(self, run_id: str) -> dict | None:
        record = self.get(run_id)
        return record.status_payload() if record else None

    def _run(self, record: RunRecord) -> None:
        record.status = "running"
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = self.run_function(
                    record.prompt,
                    mode=record.mode,
                    generations=record.generations,
                    survivors=record.survivors,
                    model_preset=record.model_preset,
                    event_sink=record.add_event,
                )
        except ValueError as exc:
            record.add_event(DebugEvent("ERROR", str(exc)))
            record.finish("error", error=str(exc))
            return
        except Exception as exc:
            message = redact_secrets(exc)
            record.add_event(DebugEvent("ERROR", message))
            record.finish("error", error=message)
            return
        record.finish("complete", result=run_result_to_dict(result))


def create_api_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    run_function: RunFunction = run_council_result,
    manager_factory: ManagerFactory | None = None,
) -> ThreadingHTTPServer:
    manager_factory = manager_factory or (
        lambda: ModelManager(MODELS, timeout_seconds=OLLAMA_TIMEOUT_SECONDS, verbose=False)
    )
    registry = RunRegistry(run_function=run_function)

    class SynapseApiHandler(BaseHTTPRequestHandler):
        server_version = "SynapseAPI/0.1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self._send_json(200, health_payload())
                return
            if path == "/models":
                self._send_json(200, model_status_payload(manager_factory))
                return
            run_match = parse_run_path(path)
            if run_match:
                run_id, child = run_match
                if child == "events":
                    self._stream_run_events(run_id)
                    return
                if child is None:
                    payload = registry.status_payload(run_id)
                    self._send_json(200 if payload else 404, payload or {"error": "Run not found."})
                    return
            if path in {"/run", "/runs"}:
                self._send_json(405, {"error": "Method not allowed."})
                return
            self._send_json(404, {"error": "Not found."})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path in {"/health", "/models"}:
                self._send_json(405, {"error": "Method not allowed."})
                return
            if parse_run_path(path):
                self._send_json(405, {"error": "Method not allowed."})
                return
            if path not in {"/run", "/runs"}:
                self._send_json(404, {"error": "Not found."})
                return

            payload = self._read_json()
            if payload is None:
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json(400, {"error": "Prompt cannot be empty."})
                return

            mode = str(payload.get("mode") or "balanced").strip()
            if mode not in {"quick", "balanced", "deep"}:
                self._send_json(400, {"error": "Mode must be quick, balanced, or deep."})
                return

            generations = payload.get("generations")
            survivors = payload.get("survivors")
            if generations is not None and not isinstance(generations, int):
                self._send_json(400, {"error": "generations must be an integer or null."})
                return
            if survivors is not None and not isinstance(survivors, int):
                self._send_json(400, {"error": "survivors must be an integer or null."})
                return

            if path == "/runs":
                model_preset = str(payload.get("model_preset") or "local").strip().lower()
                if model_preset not in {"local", "hybrid", "strong"}:
                    self._send_json(400, {"error": "model_preset must be local, hybrid, or strong."})
                    return
                record = registry.start(
                    prompt=prompt,
                    mode=mode,
                    generations=generations if generations is not None else None,
                    survivors=survivors if survivors is not None else None,
                    model_preset=model_preset,
                )
                self._send_json(
                    202,
                    {
                        "run_id": record.run_id,
                        "status": record.status,
                        "events_url": f"/runs/{record.run_id}/events",
                        "result_url": f"/runs/{record.run_id}",
                    },
                )
                return

            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = run_function(
                        prompt,
                        mode=mode,
                        generations=generations if generations is not None else None,
                        survivors=survivors if survivors is not None else None,
                    )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
                return

            self._send_json(200, run_result_to_dict(result))

        def do_PUT(self) -> None:
            self._method_not_allowed_or_not_found()

        def do_PATCH(self) -> None:
            self._method_not_allowed_or_not_found()

        def do_DELETE(self) -> None:
            self._method_not_allowed_or_not_found()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> dict | None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(raw or "{}")
            except Exception:
                self._send_json(400, {"error": "Invalid JSON."})
                return None
            if not isinstance(data, dict):
                self._send_json(400, {"error": "JSON body must be an object."})
                return None
            return data

        def _method_not_allowed_or_not_found(self) -> None:
            path = urlparse(self.path).path
            if path in {"/health", "/models", "/run", "/runs"} or parse_run_path(path):
                self._send_json(405, {"error": "Method not allowed."})
            else:
                self._send_json(404, {"error": "Not found."})

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream_run_events(self, run_id: str) -> None:
            record = registry.get(run_id)
            if record is None:
                self._send_json(404, {"error": "Run not found."})
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            cursor = 0
            while True:
                events, done = record.wait_for_events(cursor, timeout=15)
                for event in events:
                    self._write_sse("event", event)
                cursor += len(events)
                if done:
                    self._write_sse("done", record.status_payload(include_result=False))
                    self.close_connection = True
                    break
                if not events:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()

        def _write_sse(self, event_name: str, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False)
            self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
            self.wfile.write(f"data: {body}\n\n".encode("utf-8"))
            self.wfile.flush()

    return ThreadingHTTPServer((host, port), SynapseApiHandler)


def health_payload() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "api": {
            "name": "Synapse local HTTP API",
            "local_first": True,
            "hybrid_capable": "Synapse defaults to local Ollama models and can use optional provider refs when explicitly configured.",
        },
    }


def model_status_payload(manager_factory: ManagerFactory) -> dict:
    manager = manager_factory()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        usable = manager.refresh_available_models()
    missing = dict(getattr(manager, "missing_models", {}))
    available = sorted(getattr(manager, "available_model_names", set()))
    return {
        "configured_models": dict(getattr(manager, "configured_models", MODELS)),
        "usable_models": dict(usable),
        "missing_models": missing,
        "available_local_models": available,
        "providers": provider_status_payload(),
    }


def provider_status_payload() -> dict:
    return ProviderRouter(timeout_s=OLLAMA_TIMEOUT_SECONDS).provider_status()


def parse_run_path(path: str) -> tuple[str, str | None] | None:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) == 2 and parts[0] == "runs":
        return parts[1], None
    if len(parts) == 3 and parts[0] == "runs" and parts[2] == "events":
        return parts[1], "events"
    return None


def serve_api(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_api_server(host, port)
    print(f"Synapse API listening on http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
