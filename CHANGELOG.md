# Changelog

## Unreleased

- Added simplified output mode for compact generation overviews.
- Removed duplicate `main.py` entrypoint so `synapse.py` is the single launcher.

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
