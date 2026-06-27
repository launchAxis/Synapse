from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from synapse.bench.ollama_client import OllamaBenchClient
from synapse.bench.schema import CompletionRecord, PromptCase, SystemConfig
from synapse.core import run_council_result
from synapse.providers import parse_model_ref


def run_system(
    run_id: str,
    system: SystemConfig,
    case: PromptCase,
    seed: int,
    ollama_client: OllamaBenchClient | None = None,
) -> CompletionRecord:
    started = time.perf_counter()
    try:
        if system.kind == "synapse_python":
            result = run_council_result(case.prompt, mode=system.profile or "quiet")
            return CompletionRecord(
                run_id=run_id,
                system_id=system.id,
                prompt_id=case.id,
                seed=seed,
                text=result.final_answer,
                latency_s=time.perf_counter() - started,
                model_calls=count_model_events(result),
                metadata={"run_directory": result.run_directory, "synapse_version": result.version, "prompt": case.prompt},
            )

        if system.kind == "synapse_cli":
            return run_synapse_cli(run_id, system, case, seed, started)

        if system.kind == "ollama_single":
            if not system.model:
                raise ValueError(f"System {system.id} is missing model.")
            require_ollama_system_model(system)
            client = ollama_client or OllamaBenchClient(timeout_s=system.timeout_s)
            text, latency, metadata = client.chat(
                model=system.model,
                prompt=case.prompt,
                system_prompt=system.system_prompt,
                options={
                    "temperature": system.temperature,
                    "num_predict": case.max_output_tokens or system.max_output_tokens,
                    "seed": seed,
                },
            )
            return CompletionRecord(
                run_id=run_id,
                system_id=system.id,
                prompt_id=case.id,
                seed=seed,
                text=text,
                latency_s=latency,
                model_calls=1,
                prompt_tokens=metadata.get("prompt_eval_count"),
                output_tokens=metadata.get("eval_count"),
                metadata={**metadata, "prompt": case.prompt},
            )

        if system.kind == "naive_ensemble":
            if not system.model:
                raise ValueError(f"System {system.id} is missing model.")
            require_ollama_system_model(system)
            client = ollama_client or OllamaBenchClient(timeout_s=system.timeout_s)
            drafts = []
            total_latency = 0.0
            for index in range(3):
                draft, latency, _metadata = client.chat(
                    model=system.model,
                    prompt=f"Draft {index + 1}. Answer independently:\n\n{case.prompt}",
                    system_prompt=system.system_prompt,
                    options={
                        "temperature": system.temperature,
                        "num_predict": case.max_output_tokens or system.max_output_tokens,
                        "seed": seed + index,
                    },
                )
                drafts.append(draft)
                total_latency += latency
            synthesis_prompt = "\n\n".join(f"Draft {index + 1}:\n{text}" for index, text in enumerate(drafts))
            text, latency, metadata = client.chat(
                model=system.model,
                prompt=f"Combine the best parts of these drafts into one direct answer.\n\n{synthesis_prompt}",
                system_prompt=system.system_prompt,
                options={
                    "temperature": system.temperature,
                    "num_predict": case.max_output_tokens or system.max_output_tokens,
                    "seed": seed + 1000,
                },
            )
            return CompletionRecord(
                run_id=run_id,
                system_id=system.id,
                prompt_id=case.id,
                seed=seed,
                text=text,
                latency_s=total_latency + latency,
                model_calls=4,
                prompt_tokens=metadata.get("prompt_eval_count"),
                output_tokens=metadata.get("eval_count"),
                metadata={**metadata, "prompt": case.prompt},
            )

        raise ValueError(f"Unsupported benchmark system kind: {system.kind}")
    except Exception as exc:
        return CompletionRecord(
            run_id=run_id,
            system_id=system.id,
            prompt_id=case.id,
            seed=seed,
            text="",
            latency_s=time.perf_counter() - started,
            model_calls=0,
            error=str(exc),
            metadata={"prompt": case.prompt},
        )


def run_synapse_cli(run_id: str, system: SystemConfig, case: PromptCase, seed: int, started: float) -> CompletionRecord:
    if not system.command:
        raise ValueError(f"System {system.id} is missing command.")
    payload = {"prompt": case.prompt, "seed": seed, "profile": system.profile or "quiet"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle)
        payload_path = Path(handle.name)
    command = system.command.format(payload_file=str(payload_path))
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=system.timeout_s,
    )
    payload_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    data = json.loads(completed.stdout)
    return CompletionRecord(
        run_id=run_id,
        system_id=system.id,
        prompt_id=case.id,
        seed=seed,
        text=data.get("text", ""),
        latency_s=time.perf_counter() - started,
        model_calls=int(data.get("model_calls", 0)),
        metadata={**data.get("metadata", {}), "prompt": case.prompt},
    )


def require_ollama_system_model(system: SystemConfig) -> None:
    model_ref = parse_model_ref(system.model or "")
    if model_ref.provider != "ollama":
        raise ValueError(
            f"Benchmark system {system.id} uses kind {system.kind}, which is local Ollama-only in this release."
        )


def count_model_events(result: object) -> int:
    return sum(1 for event in getattr(result, "events", []) if getattr(event, "model", None))
