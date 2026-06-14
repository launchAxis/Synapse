from synapse.critique import parse_critique


def test_parse_critique_fallback_preserves_raw_text():
    critique = parse_critique(
        idea_id="A",
        critic_model="test-model",
        text="This idea needs a clearer deployment path and has cost risk.",
    )

    assert "deployment path" in critique.main_weakness
    assert "cost risk" in critique.suggested_improvement
