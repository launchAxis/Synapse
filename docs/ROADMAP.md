# Roadmap

## v0.2.x

- Tune tournament prompts with more real run examples.
- Add more lightweight tests for mocked council runs.
- Improve final synthesis by combining the top two survivors.
- Keep developer mode useful without turning the terminal UI into a large dependency.

## v0.3.0

- Persistent run history across sessions.
- Optional memory across runs.
- Configurable presets such as fast, quality, and deep.
- Better final synthesis from multiple top ideas.
- Optional concurrency for independent Ollama calls.

## v0.4.0

- Specialized agent roles.
- Debate rounds where models respond to each other.
- Role-specific prompts for Skeptic, Engineer, Researcher, Synthesizer, and Optimizer.
- Pydantic or Ollama structured-output experiments if the small-model behavior is reliable enough.

## Later

- Rich or local web UI for reviewing council runs.
- Visual idea lineage graph.
- Benchmark prompts for comparing Synapse versions.
- Cloud provider support.
- Plugin system.
