# Config Guide

Synapse keeps configuration simple in v0.2.2. Runtime settings live in `synapse/config.py`, and temporary run overrides can be passed through CLI flags.

## Models

Edit `MODELS` in `synapse/config.py`:

```python
MODELS = {
    "A": "qwen2.5:3b",
    "B": "gemma2:2b",
    "C": "llama3.2:3b",
}
```

The keys are short council labels used in output. The values are Ollama model names.

Check availability:

```bash
python synapse.py --models
```

## Generations

`MAX_GENERATIONS` controls how many rounds of critique, tournament voting, memory, and evolution Synapse runs.

Shorter runs are faster:

```bash
python synapse.py --prompt "Design a better notes app" --generations 1
```

Longer runs may produce stronger ideas, but they make many more Ollama calls.

## Survivors

`TOP_K_SURVIVORS` controls how many ranked ideas are evolved into the next generation.

You can override it per run:

```bash
python synapse.py --prompt "Design a better notes app" --survivors 2
```

v0.2.2 also adds one fresh outsider idea per non-final generation, so idea pools stay more diverse without growing without bound.

## Output Modes

Use `--mode`:

```bash
python synapse.py --prompt "Design a better notes app" --mode detailed
python synapse.py --prompt "Design a better notes app" --mode simplified
python synapse.py --prompt "Design a better notes app" --mode quiet
python synapse.py --prompt "Design a better notes app" --mode json
python synapse.py --prompt "Design a better notes app" --mode dev
```

`dev` mode shows structured debug events and model notes. It does not expose hidden model reasoning; it only shows model-provided critique summaries, judge reasons, and system events.

## Run Export

Save a run:

```bash
python synapse.py --prompt "Design a better notes app" --save-run
```

Write JSON to a specific file:

```bash
python synapse.py --prompt "Design a better notes app" --mode json --output-file result.json
```

Saved runs include:

- `run.json`
- `final_answer.md`
- `debug_log.txt`

## Postponed

v0.2.2 intentionally does not add YAML config, Rich UI, concurrency, Pydantic structured outputs, cloud APIs, web UI, or persistent cross-run memory.
