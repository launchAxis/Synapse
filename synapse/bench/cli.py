from __future__ import annotations

import argparse

from synapse.bench.runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Synapse benchmarks")
    parser.add_argument("-c", "--config", required=True, help="Benchmark config YAML/JSON file")
    parser.add_argument("-s", "--suite", required=True, help="Benchmark suite YAML/JSON file")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached completions and judgments")
    args = parser.parse_args()

    try:
        run_dir = run_benchmark(args.config, args.suite, no_cache=args.no_cache)
    except RuntimeError as exc:
        raise SystemExit(f"Benchmark failed: {exc}") from exc
    print(f"Benchmark written to {run_dir}")


if __name__ == "__main__":
    main()
