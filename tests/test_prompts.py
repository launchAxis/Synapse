from synapse.ideas import Idea
from synapse.prompts import final_prompt


def test_final_prompt_uses_topic_neutral_sections():
    prompt = final_prompt(
        "A fantasy game about peaceful robot explorers",
        Idea(id="A", text="A calm exploration game.", author_model="test-model"),
        [],
    )

    assert "How it supports teachers" not in prompt
    assert "How it works offline" not in prompt
    assert "How it works on low-cost devices" not in prompt
    assert "Clear title or name" in prompt
    assert "Core concept" in prompt
