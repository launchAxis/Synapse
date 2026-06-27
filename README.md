![Python](https://img.shields.io/badge/python-3.10+-blue)
![Ollama](https://img.shields.io/badge/LLM-Ollama-black)

<img width="321" height="307" alt="Synapse_Logo_Img" src="https://github.com/user-attachments/assets/b914d983-6a78-4312-86ba-900d7620d1cd" />

# Synapse

Synapse is a local-first idea evolution engine where multiple models generate, critique, compare, evolve, and synthesize ideas instead of relying on one single answer.

You can think of it as a local AI council: models propose ideas, steelman them, critique them, compare them in tournaments, evolve the strongest survivors, challenge assumptions, verify candidates, and synthesize a final answer.

## What Synapse Does

Synapse runs a structured idea-evolution process:

```text
TASK -> GENERATE -> STEELMAN -> CRITIQUE -> TOURNAMENT -> EVOLVE -> CHALLENGE -> VERIFY -> SYNTHESIZE -> LOG
```

Core ideas:

- local-first by default with Ollama
- multiple models or roles instead of one direct answer
- pairwise tournaments between ideas
- symmetric judging to reduce position bias
- evolution rounds that preserve strengths and repair weaknesses
- challenge and verification before final synthesis
- structured logs for debugging and evaluation
- evidence-aware benchmarking with conservative verdicts

## v0.3.0 Highlights

- Symmetric pairwise judging so unstable tournament comparisons do not award wins
- Evidence-grade benchmark verdicts, rubric grading, and conservative summaries
- Optional provider refs for benchmark judging and main-council roles
- `local`, `hybrid`, and `strong` model presets
- Local HTTP API with blocking `/run` and background `/runs`
- Ink/React terminal UI with Signal Ring pixel logo
- Stable TUI run monitoring by default, with optional experimental live events
- Evaluation-only `evaluation_summary.json` in process logs
- Separate Windows and Linux release packages generated from the same source

## Downloads

Download the latest release from the GitHub Releases page:

- `Synapse 0.3.0 Windows.zip`
- `Synapse 0.3.0 Linux.zip`

## Requirements

- Python 3.10+
- Ollama
- Node.js 18+ for the optional terminal UI

Default local models:

```bash
ollama pull qwen2.5:3b
ollama pull gemma2:2b
ollama pull llama3.2:3b
```

## Quick Start

Python-only:

```bash
pip install -r requirements.txt
python synapse.py --prompt "Design a better note-taking app" --mode balanced
```

Terminal UI:

```bash
cd terminal-ui
npm install
npm start
```

After installing a platform release package, you can also use the helper scripts included in the Windows/Linux zip.

## Usage

Interactive mode:

```bash
python synapse.py
```

Scripted mode:

```bash
python synapse.py --prompt "Design a better note-taking app" --mode balanced
```

Useful flags:

```bash
python synapse.py --version
python synapse.py --models
python synapse.py --api
python synapse.py --tui
python synapse.py --prompt "Design a better note-taking app" --mode quick
python synapse.py --prompt "Design a better note-taking app" --mode deep
python synapse.py --prompt "Design a better note-taking app" --mode json
```

## Terminal UI

The optional terminal UI is built with Ink/React and calls the local Python API. It does not reimplement Synapse logic in Node.

```bash
cd terminal-ui
npm install
npm start
```

The default terminal UI uses stable polling to avoid long-run terminal memory issues. Experimental live event bullets are available with:

```bash
npm start -- --live-events
```

## Local HTTP API

Start the local API:

```bash
python synapse.py --api
```

Endpoints:

```text
GET  /health
GET  /models
POST /run
POST /runs
GET  /runs/{id}
GET  /runs/{id}/events
```

`/run` is the backward-compatible blocking endpoint. `/runs` starts a background run and can be monitored through status polling or Server-Sent Events.

## Provider Refs And Presets

Synapse remains local-first. Bare model names mean Ollama:

```text
qwen2.5:3b == ollama:qwen2.5:3b
```

Optional provider refs include:

```text
openai:*
anthropic:*
google:*
mistral:*
deepseek:*
openrouter:*
groq:*
kimi:*
qwen:*
xai:*
openai_compatible:*
```

API keys are read only from environment variables. They are not stored in configs, logs, traces, errors, or benchmark outputs.

Model presets:

- `local`: Ollama-first behavior
- `hybrid`: local council plus optional configured provider judge/synthesis models
- `strong`: optional stronger configured judge/synthesis model with local fallback

## Benchmarking

Run the smoke benchmark:

```bash
python -m synapse.bench.cli -c configs/benchmark.default.yaml -s benchmarks/synapse_smoke.yaml
```

Run the 30-prompt benchmark:

```bash
python -m synapse.bench.cli -c configs/benchmark.default.yaml -s benchmarks/synapse_default_30.yaml
```

Benchmark verdicts are deliberately conservative. Current benchmark evidence should be treated as diagnostic rather than a superiority claim.

Do not interpret v0.3.0 as proving Synapse objectively beats baselines. Important benchmark results should still be reviewed manually.

## Project Structure

```text
synapse/
  bench/
terminal-ui/
configs/
benchmarks/
bench/
docs/
scripts/
packaging/
  windows/
  linux/
tests/
```

## Developer Checks

```bash
python -m compileall .
python -m pytest
npm.cmd --prefix terminal-ui run check
npm.cmd --prefix terminal-ui test
```

## License

Synapse is licensed under the Business Source License 1.1. See `LICENSE` and `NOTICE`.

## Status

Synapse is experimental. Results depend heavily on installed models, hardware, prompts, provider availability, and generation settings.