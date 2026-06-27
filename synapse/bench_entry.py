from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from synapse.core import run_council_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Synapse benchmark adapter")
    parser.add_argument("--profile", default="quiet", help="Synapse mode/profile")
    parser.add_argument("--payload-file", required=True, help="JSON payload with prompt and optional seed")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    prompt = payload["prompt"]
    profile = payload.get("profile") or args.profile
    started = time.perf_counter()
    result = run_council_result(prompt, mode=profile)
    print(json.dumps({
        "text": result.final_answer,
        "latency_s": time.perf_counter() - started,
        "model_calls": sum(1 for event in result.events if event.model),
        "metadata": {
            "run_directory": result.run_directory,
            "synapse_version": result.version,
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

