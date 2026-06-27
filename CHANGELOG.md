# Changelog

## v0.3.0

Synapse v0.3.0 is the first public release of the fuller Synapse experience. Earlier internal 0.2.x work has been folded into this release entry so the public changelog reflects the shipped 0.3.0 package instead of private checkpoints.

### Core Council Process

- Added the structured council loop: task routing, role-based generation, steelman, critique, pairwise tournament, evolution, challenge, verification, synthesis, and logs.
- Added task-specific rubrics and role-based independent generation for diverse first drafts.
- Added steelman notes before critique so useful strengths are preserved.
- Added structured critiques with rubric scores and repair suggestions.
- Added evolution rounds that preserve strengths, fix weaknesses, borrow useful elements from defeated ideas, and inject fresh outsider ideas.
- Added challenge and verification stages before final synthesis.
- Added automatic structured process logs under `logs/run_.../`.
- Added process modes: `quick`, `balanced`, `deep`, and `dev`.

### Tournament Reliability

- Added symmetric pairwise judging so each comparison is judged in both answer orders.
- Award wins only when both directions select the same underlying idea.
- Mark position-biased or inconsistent comparisons as unstable with no win awarded.
- Kept strict winner parsing and retry behavior.
- Added visible stable, unstable, and invalid comparison records.

### Benchmarking And Evidence

- Added the benchmark harness in `synapse.bench` and `synapse.bench_entry` for external runners.
- Added benchmark config and prompt suites under `configs/` and `benchmarks/`.
- Added completion, pairwise judgment, rubric score, metrics, summary, and human-review outputs.
- Enabled primary rubric grading in benchmark configs.
- Added conservative `benchmark_verdict.json` outputs and Benchmark Verdict sections in summaries.
- Mark invalid rubric outputs invalid instead of scoring them as zero.
- Added diagnostic rubric fallback for unstable pairwise judgments without letting invalid rubric scores override pairwise results.
- Added blind human-review exports with randomized Answer A/B order and separate answer keys.
- Added multi-judge support, explicit comparison pairs, stability warnings, Wilson intervals, and run-level inconclusive warnings.
- Stopped caching failed completions, failed judgments, invalid rubric scores, and provider quota failures.
- Stopped retrying non-recoverable daily-token or billing-quota provider errors while preserving retries for transient rate limits.
- Documented benchmark evidence honestly as diagnostic rather than a superiority claim.

### Providers And Presets

- Added provider-aware model references while keeping Ollama as the default.
- Bare names and `ollama:*` use Ollama.
- Added optional provider refs for benchmark judges and main council calls: `openai:*`, `anthropic:*`, `google:*`, `mistral:*`, `deepseek:*`, `openrouter:*`, `groq:*`, `kimi:*`, `qwen:*`, `xai:*`, and `openai_compatible:*`.
- Added `local`, `hybrid`, and `strong` model presets, with `local` as the default.
- Read API keys only from environment variables and avoid writing secrets to configs, logs, traces, errors, or benchmark outputs.

### Local API

- Added a small standard-library local HTTP API.
- Added `/health`, `/models`, and backward-compatible blocking `/run`.
- Added live run endpoints: `POST /runs`, `GET /runs/{id}`, and `GET /runs/{id}/events`.
- Added core event streaming through an optional `event_sink` callback without changing the council process.
- Added evaluation-only `evaluation_summary.json` to normal process logs.

### Terminal UI

- Added an optional Ink/React terminal frontend in `terminal-ui/` that calls the local Synapse API.
- Added Signal Ring terminal rendering with compact ANSI truecolor half-block output and a no-color fallback.
- Added slash commands, model status, provider status, mode/preset selection, stable run monitoring, optional live progress bullets, and result evidence.
- Added calm/council/dev view levels and expandable details.
- Moved the Signal Ring into the left welcome column.
- Reduced typing flicker by keeping prompt draft updates local to the input line.
- Defaulted long runs to stable polling to avoid terminal memory pressure, with live events available as experimental mode.

### Packaging And Docs

- Added release packaging tooling for separate Windows and Linux packages from the same shared source tree.
- Added package-root npm scripts so `npm start` and `npm start -- --smoke` work from the package root.
- Added package PATH launchers so `synapse` and `synapse-tui` can work after one-time setup.
- Added Windows and Linux platform helper generation through `scripts/build_release_packages.py`.
- Added `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `.gitattributes`, and pull request template.
- Updated README and docs for the 0.3.0 public release.