# Changelog

## v0.3.0

- Added a small provider-aware model layer for benchmark judging while keeping Ollama as the default.
- Added provider refs for benchmark judges and main council calls: bare names and `ollama:*` use Ollama, with optional `openai:*`, `anthropic:*`, `google:*`, `mistral:*`, `deepseek:*`, `openrouter:*`, `kimi:*`, `qwen:*`, `xai:*`, and `openai_compatible:*` support through environment variables.
- Added local/hybrid/strong model presets while keeping `local` as the default.
- Added a small standard-library local HTTP API with `/health`, `/models`, and `/run`.
- Added live run API endpoints: `POST /runs`, `GET /runs/{id}`, and `GET /runs/{id}/events` for Server-Sent Events.
- Added core event streaming through an optional `event_sink` callback without changing the council process.
- Added evaluation-only `evaluation_summary.json` to normal process logs.
- Added release packaging tooling for separate Windows and Linux folders from the same shared source tree.
- Added an optional Ink/React terminal frontend in `terminal-ui/` that calls the local Synapse API.
- Updated the terminal UI to use live `/runs` progress bullets, expandable details, calm/council/dev view levels, local/hybrid/strong intelligence presets, and provider status commands.
- Added slash commands to the terminal UI and revised the Signal Ring to use compact ANSI truecolor half-block rendering with a text fallback.
- Moved the terminal UI Signal Ring into the left welcome column instead of using a top banner.
- Reduced terminal UI typing flicker by keeping prompt draft updates local to the input line.
- Added optional npm command shims so the terminal UI can be launched as `synapse` or `synapse-tui` after one-time linking.
- Added package-root npm scripts so `npm start` and `npm start -- --smoke` work without changing into `terminal-ui/`.
- Improved the Windows command installer so it can explain and optionally fix missing npm global `PATH` configuration.
- Added direct package PATH installers with `bin/synapse` launchers, so `synapse` and `synapse-tui` can work without npm global linking.
- Made the terminal UI launcher auto-start the default local API, preferring a small Windows Terminal side pane and falling back to a separate API window.
- Enabled primary rubric grading in the default and strong-judge benchmark configs.
- Added `benchmark_verdict.json` with conservative comparison and run-level verdicts.
- Added a Benchmark Verdict section and rubric ranking table to benchmark summaries.
- Hardened the rubric grading prompt while keeping invalid rubric parses excluded from scores.
- Added the benchmark harness in `synapse.bench`.
- Added `synapse.bench_entry` as a stable adapter for external benchmark runners.
- Added benchmark config and prompt suites under `configs/` and `benchmarks/`.
- Added benchmark outputs for completions, pairwise judgments, pairwise metrics, system metrics, human review sheets, and Markdown summaries.
- Added optional rubric grading diagnostics with weighted 0-100 scores.
- Added readiness checks so benchmark runs fail when all completions fail or no pairwise judgments are produced.
- Stopped caching failed completions and failed pairwise judgments.
- Passed benchmark seeds into Ollama generation and judge options.
- Reworked human review export into a blinded reviewer sheet plus a separate key file.
- Added explicit `comparison_pairs` config and default Synapse-vs-baselines pairs.
- Added summary warnings and per-system error counts when completions fail.
- Improved pairwise judge prompt to require strengths/weaknesses and `FINAL_WINNER`.
- Added `judge_min_stability`, per-pair unreliability warnings, run-level inconclusive warnings, and visible A/B choice diagnostics.
- Added optional multi-judge mode through `judge.models`.
- Added diagnostic rubric fallback for unstable pairwise judgments.
- Added biased-judge regression coverage.
- Made rubric fallback auditable via `rubric_fallback_scores.jsonl`, raw responses, validity flags, and parse errors.
- Prevented invalid rubric fallback parses from silently scoring 0 or overriding pairwise results.
- Stopped caching invalid or errored rubric scores, including provider quota failures.
- Stopped retrying non-recoverable daily token or billing quota provider errors while preserving retries for transient rate limits.
- Documented the v0.3.0 benchmark evidence status honestly: clean smoke evidence is mixed/diagnostic, while quota-invalidated full runs should not be cited as credible proof.
- Randomized human-review Answer A/B order and kept true mapping only in `human_review_key.csv`.
- Added `configs/benchmark.strong-judge.yaml` for stronger local judge models.
- Added benchmark tests for config loading, stats, pair parsing, and system-pair selection.

## v0.2.3

- Added heuristic task typing and task-specific rubrics.
- Added role-based independent generation with Creator, Pragmatist, Contrarian, Engineer, and User Advocate roles.
- Added a steelman stage before critique.
- Expanded structured critiques with strongest part, weakest part, hidden assumption, biggest risk, missing detail, repair suggestion, and rubric scores.
- Updated tournaments to require `WINNER: Idea A` or `WINNER: Idea B`, save invalid comparisons, and swap A/B positions across judges.
- Updated evolution to preserve steelmanned strengths, borrow one concrete element from a defeated idea, and record diff summaries.
- Kept fresh outsider injection as part of the process loop.
- Added challenge and verification stages before synthesis.
- Added conversation-shaped events and automatic structured logs under `logs/run_.../`.
- Added required process modes: `quick`, `balanced`, `deep`, and `dev`.
- Updated tests for the v0.2.3 Process Core.

## v0.2.2

- Replaced the hardcoded education-focused final synthesis prompt with a topic-neutral prompt.
- Added CLI flags for prompt, mode, generation count, survivor count, version, model listing, JSON output, and run saving.
- Added quiet, JSON, and developer output modes.
- Added structured debug events and model notes for inspectable runs.
- Added JSON run export under `runs/` with `run.json`, `final_answer.md`, and `debug_log.txt`.
- Added controlled fresh outsider ideas during evolution to reduce premature convergence.
- Improved missing-model reporting by showing available models when possible.
- Hardened tournament parsing to accept strict markdown-wrapped `WINNER:` lines while still rejecting vague judgments.
- Added pytest-based development tests through `requirements-dev.txt`.

## v0.2.1

- Fixed tournament winner parsing so unclear judgments are retried once and then skipped instead of guessed.
- Changed judge prompts to require strict `WINNER:` and `REASON:` labels.
- Changed critique prompts to require strict uppercase labels.
- Improved critique parsing fallback so raw critique text is preserved when fields cannot be parsed.
- Strengthened the final synthesis prompt into a complete proposal format.
- Added a diversity instruction during evolution so survivors keep distinct approaches.

## v0.2.0

- Added pairwise tournament voting.
- Added structured critiques.
- Added idea evolution across generations.
- Added simple generation memory.
- Added clearer console output.
- Added missing Ollama model warnings and graceful continuation.
- Reorganized the project into a small `synapse/` package.

