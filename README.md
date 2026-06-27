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

Core ideas:
local-first by default with Ollama
multiple models or roles instead of one direct answer
pairwise tournaments between ideas
symmetric judging to reduce position bias
evolution rounds that preserve strengths and repair weaknesses
challenge and verification before final synthesis
structured logs for debugging and evaluation
evidence-aware benchmarking with conservative verdicts