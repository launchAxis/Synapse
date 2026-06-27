from synapse.model_presets import phase_models, resolve_model_plan


def test_local_model_preset_keeps_base_models_only(monkeypatch):
    monkeypatch.delenv("SYNAPSE_HYBRID_JUDGE_MODEL", raising=False)
    plan = resolve_model_plan("local", {"A": "qwen2.5:3b"})

    assert plan.preset == "local"
    assert plan.configured_models == {"A": "qwen2.5:3b"}
    assert plan.judge_key is None
    assert plan.synthesis_key is None


def test_hybrid_model_preset_adds_optional_judge_and_synthesis_refs(monkeypatch):
    monkeypatch.setenv("SYNAPSE_HYBRID_JUDGE_MODEL", "openai:gpt-test")
    monkeypatch.setenv("SYNAPSE_HYBRID_SYNTHESIS_MODEL", "anthropic:claude-test")

    plan = resolve_model_plan("hybrid", {"A": "qwen2.5:3b"})
    council, judge, synthesis = phase_models(
        {
            "A": "qwen2.5:3b",
            "__judge__": "openai:gpt-test",
            "__synthesis__": "anthropic:claude-test",
        },
        plan,
    )

    assert council == {"A": "qwen2.5:3b"}
    assert judge == {"A": "qwen2.5:3b", "J": "openai:gpt-test"}
    assert synthesis == "anthropic:claude-test"


def test_strong_model_preset_falls_back_to_local_when_provider_ref_missing(monkeypatch):
    monkeypatch.setenv("SYNAPSE_STRONG_MODEL", "openai:gpt-test")

    plan = resolve_model_plan("strong", {"A": "qwen2.5:3b"})
    council, judge, synthesis = phase_models({"A": "qwen2.5:3b"}, plan)

    assert council == {"A": "qwen2.5:3b"}
    assert judge == {"A": "qwen2.5:3b"}
    assert synthesis == "qwen2.5:3b"
