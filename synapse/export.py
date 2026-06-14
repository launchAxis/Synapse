from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from synapse.ideas import RunResult


def run_result_to_dict(result: RunResult) -> dict:
    return asdict(result)


def run_result_to_json(result: RunResult) -> str:
    return json.dumps(run_result_to_dict(result), indent=2, ensure_ascii=False)


def save_run(result: RunResult, base_dir: str | Path = "runs") -> Path:
    base_path = Path(base_dir)
    slug = slugify(result.topic)
    run_dir = base_path / f"{result.timestamp.replace(':', '-')}_{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result.run_directory = str(run_dir)
    (run_dir / "run.json").write_text(run_result_to_json(result), encoding="utf-8")
    (run_dir / "final_answer.md").write_text(result.final_answer, encoding="utf-8")
    (run_dir / "debug_log.txt").write_text(debug_log_text(result), encoding="utf-8")
    return run_dir


def write_json_file(result: RunResult, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True) if path.parent != Path(".") else None
    path.write_text(run_result_to_json(result), encoding="utf-8")
    return path


def debug_log_text(result: RunResult) -> str:
    lines = []
    for event in result.events:
        parts = [f"[{event.phase}]"]
        if event.generation is not None:
            parts.append(f"generation={event.generation}")
        if event.model:
            parts.append(f"model={event.model}")
        if event.idea_id:
            parts.append(f"idea={event.idea_id}")
        parts.append(event.message)
        lines.append(" ".join(parts))
    return "\n".join(lines)


def slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].strip("-") or "synapse-run")
