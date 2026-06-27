from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from synapse.ideas import RunResult
from synapse.providers import parse_model_ref


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


def save_process_logs(result: RunResult, base_dir: str | Path = "logs") -> Path:
    base_path = Path(base_dir)
    slug = slugify(result.topic)
    run_dir = base_path / f"run_{result.timestamp.replace(':', '-')}_{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    result.run_directory = str(run_dir)

    payload = run_result_to_dict(result)
    stages = {
        "prompt.txt": result.topic,
        "config.json": payload.get("config", {}),
        "router.json": payload.get("routing", {}),
        "generation.json": [snapshot.get("ideas", []) for snapshot in payload.get("generations", [])],
        "steelman.json": [snapshot.get("steelmen", []) for snapshot in payload.get("generations", [])],
        "critique.json": [snapshot.get("critiques", []) for snapshot in payload.get("generations", [])],
        "tournament.json": [snapshot.get("comparisons", []) for snapshot in payload.get("generations", [])],
        "evolution.json": [
            [idea for idea in snapshot.get("ideas", []) if idea.get("origin") in {"evolved", "fresh"}]
            for snapshot in payload.get("generations", [])
        ],
        "challenge.json": payload.get("challenges", []),
        "verification.json": payload.get("verifications", []),
        "synthesis.json": {"final_answer": result.final_answer},
        "evaluation_summary.json": evaluation_summary(result),
        "trace.json": payload,
        "dialogue_log.jsonl": payload.get("conversation", []),
    }

    for filename, content in stages.items():
        path = run_dir / filename
        if filename.endswith(".txt"):
            path.write_text(str(content), encoding="utf-8")
        elif filename.endswith(".jsonl"):
            lines = [json.dumps(item, ensure_ascii=False) for item in content]
            path.write_text("\n".join(lines), encoding="utf-8")
        else:
            path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")

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


def evaluation_summary(result: RunResult) -> dict:
    phase_counts: dict[str, int] = {}
    phase_timings: dict[str, dict[str, float | None]] = {}
    for event in result.events:
        phase_counts[event.phase] = phase_counts.get(event.phase, 0) + 1
        if event.elapsed_s is None:
            continue
        item = phase_timings.setdefault(event.phase, {"first_elapsed_s": event.elapsed_s, "last_elapsed_s": event.elapsed_s})
        item["first_elapsed_s"] = min(float(item["first_elapsed_s"]), event.elapsed_s)
        item["last_elapsed_s"] = max(float(item["last_elapsed_s"]), event.elapsed_s)

    comparisons = [
        comparison
        for snapshot in result.generations
        for comparison in snapshot.comparisons
    ]
    tournament = {
        "stable": sum(1 for item in comparisons if item.valid and item.stable),
        "unstable": sum(1 for item in comparisons if item.valid and not item.stable),
        "invalid": sum(1 for item in comparisons if not item.valid),
    }

    verdict_counts: dict[str, int] = {}
    for verification in result.verifications:
        verdict_counts[verification.verdict] = verdict_counts.get(verification.verdict, 0) + 1

    configured_models = dict(result.config.get("models", {}))
    providers = {}
    for key, model in configured_models.items():
        ref = parse_model_ref(model)
        providers[key] = {
            "provider": ref.provider,
            "model_ref": ref.canonical,
        }

    return {
        "version": result.version,
        "timestamp": result.timestamp,
        "mode": result.config.get("mode"),
        "process_mode": result.config.get("process_mode"),
        "model_preset": result.config.get("model_preset", "local"),
        "phase_timings": phase_timings,
        "event_counts": phase_counts,
        "model_refs": configured_models,
        "providers": providers,
        "usable_models": dict(result.usable_models),
        "missing_models": dict(result.missing_models),
        "tournament": tournament,
        "verification_verdicts": verdict_counts,
        "final_answer_length": len(result.final_answer or ""),
    }


def slugify(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].strip("-") or "synapse-run")
