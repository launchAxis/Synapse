# Synapse Brain

## What Synapse Is

Synapse is a local multi-agent AI system powered by Ollama models.

The purpose of Synapse is to make several small models work together as an AI council. Instead of asking one model for one answer, Synapse asks multiple models to generate ideas, critique those ideas, compare them, evolve the survivors, and converge toward a stronger final answer.

The important idea is interaction. Synapse is not just a wrapper that prints several model responses. It is an experiment in structured disagreement, feedback, and idea evolution.

## Why It Exists

Most AI tools produce one answer and stop. Synapse explores a different question:

Can several local models, guided through a structured process, produce a better answer than any one model's first attempt?

The project is meant to stay local, understandable, and hackable. It should be easy to inspect, modify, and run on normal hardware with small Ollama models.

## AI Council Metaphor

Synapse behaves like a small council:

- generators propose ideas
- critics identify weaknesses
- judges compare ideas directly
- survivors are improved
- memory carries lessons forward
- the final answer emerges from repeated refinement

The council should feel like a debate-and-refinement engine, not a single chatbot.

## v0.2.0 Architecture

Synapse v0.2.0 uses this loop:

1. The user enters a prompt.
2. Available Ollama models generate initial ideas.
3. Models produce structured critiques.
4. Every idea is compared against every other idea.
5. Judges choose winners and explain why.
6. Synapse records wins, losses, rankings, and comparison reasons.
7. The strongest ideas survive.
8. Survivors are evolved using critiques, tournament feedback, and generation memory.
9. The loop repeats.
10. Synapse synthesizes a final result from the strongest evolved idea.

The implementation is split into small modules:

- `synapse/models.py`: configured model status and provider-routed model calls
- `synapse/providers.py`: local Ollama and optional API provider adapters
- `synapse/generation.py`: initial idea generation
- `synapse/critique.py`: structured critiques
- `synapse/tournament.py`: pairwise tournament voting
- `synapse/evolution.py`: survivor improvement
- `synapse/memory.py`: simple generation memory
- `synapse/prompts.py`: prompt templates
- `synapse/core.py`: the main pipeline

## v0.2.3 Architecture Update

Synapse v0.2.3 turns the council loop into an explicit process core:

```text
TASK -> GENERATE -> STEELMAN -> CRITIQUE -> TOURNAMENT -> EVOLVE -> CHALLENGE -> VERIFY -> SYNTHESIZE -> LOG
```

Each run starts with heuristic task routing and a simple rubric. Ideas are generated independently by role prompts, then steelmanned before they are critiqued. Tournaments still use strict pairwise judging, but comparisons now use the selected rubric and swap A/B positions to reduce bias.

Evolution preserves steelmanned strengths, fixes weaknesses, borrows one concrete element from a defeated idea, and injects a fresh outsider. Before synthesis, the strongest candidates are challenged and verified against the original prompt, rubric, and consistency checks.

Every run produces a structured `RunResult`.

That run result contains:

- topic and config snapshot
- task type and rubric
- usable and missing models
- generation snapshots
- steelman notes
- idea lineage and mutation origin
- critiques and tournament comparisons
- challenge and verification results
- conversation-shaped events
- debug events
- final answer

This makes Synapse easier to inspect without adding a heavy UI. Developer mode shows debug events and model notes in the terminal, and every run saves stage logs under `logs/run_.../`.

## Current Limits

v0.2.3 intentionally stays focused on process quality.

It does not yet include:

- web UI
- database memory
- full debate between agents
- benchmark scoring
- training or fine-tuning Synapse-specific models
- persistent memory across runs
- Rich split-screen UI
- concurrency
- Pydantic structured outputs

## Future Roadmap

Possible future versions:

- v0.3.0: optional persistent memory across runs
- v0.3.0: stronger final synthesis from multiple top ideas
- v0.4.0: specialized agent roles such as Skeptic, Engineer, Researcher, and Synthesizer
- v0.4.0: richer debate where models respond directly to each other
- v0.5.0: configurable model profiles and prompt presets
- later: simple local UI for inspecting idea lineage and tournament results

The long-term dream is an idea evolution engine where local models can argue, critique, improve, remember, and converge.
