# These are the Ollama models Synapse will try to use.
# The letters A, B, and C are simple council member names used in the output.
MODELS = {
    "A": "qwen2.5:3b",
    "B": "gemma2:2b",
    "C": "llama3.2:3b",
}

# How many rounds of idea improvement Synapse should run.
MAX_GENERATIONS = 3

# How many top ideas survive after each tournament round.
TOP_K_SURVIVORS = 2

# Which council member writes the final polished answer when available.
FINAL_SYNTHESIS_MODEL_KEY = "A"

# How long Synapse waits for an Ollama response before giving up.
OLLAMA_TIMEOUT_SECONDS = 45

# If True, Synapse prints short generation summaries instead of the full detailed trace.
# You can still choose detailed or simplified mode when running from the terminal.
SIMPLIFIED = False
