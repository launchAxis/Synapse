# Changelog

## Unreleased

- Added simplified output mode for compact generation overviews.
- Removed duplicate `main.py` entrypoint so `synapse.py` is the single launcher.

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
