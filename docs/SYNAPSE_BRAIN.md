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

- `synapse/models.py`: Ollama calls and missing-model handling
- `synapse/generation.py`: initial idea generation
- `synapse/critique.py`: structured critiques
- `synapse/tournament.py`: pairwise tournament voting
- `synapse/evolution.py`: survivor improvement
- `synapse/memory.py`: simple generation memory
- `synapse/prompts.py`: prompt templates
- `synapse/core.py`: the main pipeline

## Current Limits

v0.2.0 intentionally stays simple.

It does not yet include:

- web UI
- database memory
- advanced agent personalities
- full debate between agents
- benchmark scoring
- cloud model providers
- persistent JSON run history