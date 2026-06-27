# Project History

## v0.1.0

Initial local multi-model generation and critique prototype.

The early version explored the basic AI council idea:

- multiple Ollama models generate ideas
- models critique ideas
- weaker ideas are removed
- survivors are improved
- a final answer is selected

This version proved the concept but relied mainly on score-style evaluation.

## v0.2.0

First serious multi-agent upgrade.

Added:

- pairwise tournament voting
- structured critique prompts
- idea lineage across generations
- lightweight generation memory
- clearer console output
- better missing-model handling for Ollama
- modular beginner-readable project structure

The main v0.2.0 shift is from score-first evaluation to direct comparison between ideas.

## v0.2.1

Bugfix and output-quality release.

Fixed tournament winner parsing so Synapse no longer guesses when a judge response is unclear. Added a retry for invalid judgments, stricter critique labels, better critique fallback behavior, a stronger final proposal prompt, and light diversity guidance during evolution.

## v0.2.2

Hybrid reliability and inspectability release.

Added a topic-neutral final synthesis prompt, CLI flags, quiet/JSON/dev modes, structured debug events, JSON run export, stronger missing-model diagnostics, markdown-tolerant strict tournament parsing, and controlled fresh outsider ideas during evolution. This release keeps Synapse local and beginner-readable while making each run easier to inspect and test.

## v0.2.3

Process Core release.

Refactored Synapse into a general-purpose structured process: task routing, role-based independent generation, steelman, structured critique, pairwise tournament, evolution with borrowed strengths, outsider injection, challenge, verification, synthesis, and structured logging.

This release adds `quick`, `balanced`, `deep`, and `dev` process modes and saves every run under `logs/run_.../` with stage-specific JSON files plus conversation-shaped JSONL events for future visualization.
