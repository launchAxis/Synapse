import json
from dataclasses import asdict

from synapse.bench.ollama_client import OllamaBenchClient
from synapse.bench.schema import BenchmarkConfig, JudgeConfig
from synapse.providers import (
    AnthropicProvider,
    GeminiProvider,
    ModelRef,
    OpenAIProvider,
    ProviderResponse,
    ProviderRouter,
    parse_model_ref,
    redact_secrets,
)


def test_parse_bare_model_ref_defaults_to_ollama():
    ref = parse_model_ref("qwen2.5:3b")

    assert ref.provider == "ollama"
    assert ref.model == "qwen2.5:3b"
    assert ref.canonical == "ollama:qwen2.5:3b"


def test_parse_explicit_ollama_ref():
    ref = parse_model_ref("ollama:qwen2.5:3b")

    assert ref.provider == "ollama"
    assert ref.model == "qwen2.5:3b"
    assert ref.canonical == "ollama:qwen2.5:3b"


def test_missing_openai_api_key_returns_unavailable_response(monkeypatch):
    monkeypatch.delenv("SYNAPSE_OPENAI_API_KEY", raising=False)

    response = ProviderRouter().chat("openai:gpt-test", "hello")

    assert not response.ok
    assert "SYNAPSE_OPENAI_API_KEY" in response.error


def test_missing_groq_api_key_returns_unavailable_response(monkeypatch):
    monkeypatch.delenv("SYNAPSE_GROQ_API_KEY", raising=False)

    response = ProviderRouter().chat("groq:llama-3.3-70b-versatile", "hello")

    assert not response.ok
    assert "SYNAPSE_GROQ_API_KEY" in response.error


def test_parse_supported_native_provider_refs():
    expected = {
        "openai:gpt-test": ("openai", "gpt-test"),
        "anthropic:claude-test": ("anthropic", "claude-test"),
        "google:gemini-test": ("google", "gemini-test"),
        "mistral:mistral-test": ("mistral", "mistral-test"),
        "deepseek:deepseek-test": ("deepseek", "deepseek-test"),
        "openrouter:router/test": ("openrouter", "router/test"),
        "groq:llama-test": ("groq", "llama-test"),
        "kimi:kimi-test": ("kimi", "kimi-test"),
        "qwen:qwen-test": ("qwen", "qwen-test"),
        "xai:grok-test": ("xai", "grok-test"),
        "openai_compatible:model-test": ("openai_compatible", "model-test"),
    }

    for value, pair in expected.items():
        ref = parse_model_ref(value)
        assert (ref.provider, ref.model) == pair


def test_ollama_bench_client_accepts_provider_refs_with_mocked_router():
    router = _FakeRouter()
    client = OllamaBenchClient(router=router)

    text, latency, metadata = client.chat("openai:gpt-test", "judge prompt")

    assert text == "FINAL_WINNER: A\nREASON: clearer"
    assert latency == 0.01
    assert metadata["provider"] == "openai"
    assert router.seen.provider == "openai"
    assert router.seen.model == "gpt-test"


def test_secret_redaction_and_config_serialization_do_not_leak_api_keys(monkeypatch):
    monkeypatch.setenv("SYNAPSE_OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("SYNAPSE_ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("SYNAPSE_GROQ_API_KEY", "groq-secret")
    config = BenchmarkConfig(run_name="x", seeds=[1], systems=[], judge=JudgeConfig(model="openai:gpt-test"))

    serialized = json.dumps(asdict(config))
    error = redact_secrets("request failed with sk-test-secret, anthropic-secret, and groq-secret")

    assert "sk-test-secret" not in serialized
    assert "sk-test-secret" not in error
    assert "anthropic-secret" not in error
    assert "groq-secret" not in error
    assert "[redacted]" in error


def test_openai_style_provider_successful_chat_call(monkeypatch):
    monkeypatch.setenv("SYNAPSE_MISTRAL_API_KEY", "mistral-secret")
    provider = _FakeOpenAIStyleProvider("mistral", "SYNAPSE_MISTRAL_API_KEY", "https://api.example.test/v1")

    response = provider.chat(parse_model_ref("mistral:mistral-test"), "hello", system_prompt="system")

    assert response.ok
    assert response.text == "provider answer"
    assert provider.seen_payload["model"] == "mistral-test"
    assert provider.seen_payload["messages"][0]["role"] == "system"


def test_groq_provider_is_registered_as_openai_compatible(monkeypatch):
    monkeypatch.setenv("SYNAPSE_GROQ_API_KEY", "groq-secret")
    router = ProviderRouter()
    provider = router.providers["groq"]

    assert provider.provider_name == "groq"
    assert provider.api_key_env == "SYNAPSE_GROQ_API_KEY"
    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert router.provider_available("groq")


def test_openai_style_provider_sends_json_accept_and_user_agent_headers():
    provider = OpenAIProvider("groq", "SYNAPSE_GROQ_API_KEY", "https://api.groq.com/openai/v1")

    headers = provider._headers("test-secret")

    assert headers["Authorization"] == "Bearer test-secret"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == "Synapse/0.3.0"


def test_anthropic_provider_successful_chat_call(monkeypatch):
    monkeypatch.setenv("SYNAPSE_ANTHROPIC_API_KEY", "anthropic-secret")
    provider = _FakeAnthropicProvider()

    response = provider.chat(parse_model_ref("anthropic:claude-test"), "hello", system_prompt="system")

    assert response.ok
    assert response.text == "anthropic answer"
    assert provider.seen_payload["model"] == "claude-test"
    assert provider.seen_payload["system"] == "system"


def test_gemini_provider_successful_chat_call(monkeypatch):
    monkeypatch.setenv("SYNAPSE_GOOGLE_API_KEY", "google-secret")
    provider = _FakeGeminiProvider()

    response = provider.chat(parse_model_ref("google:gemini-test"), "hello", options={"max_tokens": 12})

    assert response.ok
    assert response.text == "gemini answer"
    assert provider.seen_model == "gemini-test"
    assert provider.seen_payload["generationConfig"]["maxOutputTokens"] == 12


class _FakeRouter:
    def __init__(self):
        self.seen: ModelRef | None = None

    def chat(self, model_ref, prompt, system_prompt="", options=None):
        self.seen = parse_model_ref(model_ref)
        return ProviderResponse(
            ok=True,
            text="FINAL_WINNER: A\nREASON: clearer",
            latency_s=0.01,
            metadata={"provider": self.seen.provider},
        )


class _FakeOpenAIStyleProvider(OpenAIProvider):
    def _request(self, method, path, payload=None):
        self.seen_method = method
        self.seen_path = path
        self.seen_payload = payload
        return {"choices": [{"message": {"content": "provider answer"}}]}


class _FakeAnthropicProvider(AnthropicProvider):
    def _request(self, payload):
        self.seen_payload = payload
        return {"content": [{"type": "text", "text": "anthropic answer"}]}


class _FakeGeminiProvider(GeminiProvider):
    def _request(self, model, payload):
        self.seen_model = model
        self.seen_payload = payload
        return {"candidates": [{"content": {"parts": [{"text": "gemini answer"}]}}]}


def test_bench_client_retries_retryable_provider_errors_with_retry_hint():
    sleeps = []
    router = _ScriptedRouter([
        ProviderResponse(ok=False, text="", error='google request failed: HTTP 429: {"retryDelay":"17s"}'),
        ProviderResponse(ok=True, text="FINAL_WINNER: A\nREASON: clearer", latency_s=0.2, metadata={"provider": "google"}),
    ])
    client = OllamaBenchClient(router=router, retry_attempts=2, retry_backoff_s=1, retry_max_sleep_s=5, sleep_fn=sleeps.append)

    text, latency, metadata = client.chat("google:gemini-test", "judge prompt")

    assert text.startswith("FINAL_WINNER")
    assert latency == 0.2
    assert metadata["provider"] == "google"
    assert sleeps == [5.0]
    assert len(router.calls) == 2


def test_bench_client_does_not_retry_nonretryable_errors():
    sleeps = []
    router = _ScriptedRouter([
        ProviderResponse(ok=False, text="", error="google provider is unavailable: set SYNAPSE_GOOGLE_API_KEY."),
    ])
    client = OllamaBenchClient(router=router, retry_attempts=3, sleep_fn=sleeps.append)

    try:
        client.chat("google:gemini-test", "judge prompt")
    except RuntimeError as exc:
        assert "SYNAPSE_GOOGLE_API_KEY" in str(exc)
    else:
        raise AssertionError("client.chat should fail for nonretryable provider errors")

    assert len(router.calls) == 1
    assert sleeps == []


def test_bench_client_applies_min_request_interval_between_calls():
    now = [0.0]
    sleeps = []

    def clock():
        return now[0]

    def sleep(seconds):
        sleeps.append(round(seconds, 2))
        now[0] += seconds

    router = _ScriptedRouter([
        ProviderResponse(ok=True, text="first", latency_s=0.1),
        ProviderResponse(ok=True, text="second", latency_s=0.1),
    ])
    client = OllamaBenchClient(router=router, min_request_interval_s=13.0, sleep_fn=sleep, clock=clock)

    client.chat("google:gemini-test", "first prompt")
    client.chat("google:gemini-test", "second prompt")

    assert sleeps == [13.0]
    assert len(router.calls) == 2


class _ScriptedRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, model_ref, prompt, system_prompt="", options=None):
        self.calls.append((model_ref, prompt, system_prompt, options))
        return self.responses.pop(0)
