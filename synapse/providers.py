from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


KNOWN_PROVIDERS = {
    "ollama",
    "openai",
    "anthropic",
    "google",
    "mistral",
    "deepseek",
    "openrouter",
    "groq",
    "kimi",
    "qwen",
    "xai",
    "openai_compatible",
}
SECRET_ENV_VARS = (
    "SYNAPSE_OPENAI_API_KEY",
    "SYNAPSE_ANTHROPIC_API_KEY",
    "SYNAPSE_GOOGLE_API_KEY",
    "SYNAPSE_MISTRAL_API_KEY",
    "SYNAPSE_DEEPSEEK_API_KEY",
    "SYNAPSE_OPENROUTER_API_KEY",
    "SYNAPSE_GROQ_API_KEY",
    "SYNAPSE_KIMI_API_KEY",
    "SYNAPSE_QWEN_API_KEY",
    "SYNAPSE_XAI_API_KEY",
    "SYNAPSE_OPENAI_COMPATIBLE_API_KEY",
)


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str
    raw: str

    @property
    def canonical(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass
class ProviderResponse:
    ok: bool
    text: str
    error: str = ""
    latency_s: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)


class ModelProvider(Protocol):
    def list_models(self) -> list[str]:
        ...

    def chat(
        self,
        model_ref: ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        ...


def parse_model_ref(value: str) -> ModelRef:
    raw = str(value).strip()
    if not raw:
        raise ValueError("Model reference cannot be empty.")

    prefix, separator, remainder = raw.partition(":")
    if separator and prefix in KNOWN_PROVIDERS:
        model = remainder.strip()
        if not model:
            raise ValueError(f"Model reference {raw!r} is missing a model name.")
        return ModelRef(provider=prefix, model=model, raw=raw)

    return ModelRef(provider="ollama", model=raw, raw=raw)


def redact_secrets(text: object) -> str:
    cleaned = str(text)
    for name in SECRET_ENV_VARS:
        secret = os.environ.get(name)
        if secret:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


class ProviderRouter:
    def __init__(
        self,
        timeout_s: int = 120,
        providers: dict[str, ModelProvider] | None = None,
        ollama_client: object | None = None,
    ):
        self.timeout_s = timeout_s
        self.providers = providers or {
            "ollama": OllamaProvider(timeout_s=timeout_s, client=ollama_client),
            "openai": OpenAIProvider(
                provider_name="openai",
                api_key_env="SYNAPSE_OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",
                timeout_s=timeout_s,
            ),
            "mistral": OpenAIProvider(
                provider_name="mistral",
                api_key_env="SYNAPSE_MISTRAL_API_KEY",
                base_url="https://api.mistral.ai/v1",
                timeout_s=timeout_s,
            ),
            "deepseek": OpenAIProvider(
                provider_name="deepseek",
                api_key_env="SYNAPSE_DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com",
                timeout_s=timeout_s,
            ),
            "openrouter": OpenAIProvider(
                provider_name="openrouter",
                api_key_env="SYNAPSE_OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
                timeout_s=timeout_s,
            ),
            "groq": OpenAIProvider(
                provider_name="groq",
                api_key_env="SYNAPSE_GROQ_API_KEY",
                base_url="https://api.groq.com/openai/v1",
                timeout_s=timeout_s,
            ),
            "kimi": OpenAIProvider(
                provider_name="kimi",
                api_key_env="SYNAPSE_KIMI_API_KEY",
                base_url="https://api.moonshot.cn/v1",
                timeout_s=timeout_s,
            ),
            "qwen": OpenAIProvider(
                provider_name="qwen",
                api_key_env="SYNAPSE_QWEN_API_KEY",
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                timeout_s=timeout_s,
            ),
            "xai": OpenAIProvider(
                provider_name="xai",
                api_key_env="SYNAPSE_XAI_API_KEY",
                base_url="https://api.x.ai/v1",
                timeout_s=timeout_s,
            ),
            "anthropic": AnthropicProvider(timeout_s=timeout_s),
            "google": GeminiProvider(timeout_s=timeout_s),
            "openai_compatible": OpenAIProvider(
                provider_name="openai_compatible",
                api_key_env="SYNAPSE_OPENAI_COMPATIBLE_API_KEY",
                base_url=os.environ.get("SYNAPSE_OPENAI_COMPATIBLE_BASE_URL", ""),
                timeout_s=timeout_s,
                base_url_env="SYNAPSE_OPENAI_COMPATIBLE_BASE_URL",
            ),
        }

    def list_models(self, provider: str | None = None) -> dict[str, list[str]]:
        names = [provider] if provider else sorted(self.providers)
        status: dict[str, list[str]] = {}
        for name in names:
            item = self.providers.get(name)
            if item is None:
                status[name] = []
                continue
            try:
                status[name] = item.list_models()
            except Exception:
                status[name] = []
        return status

    def chat(
        self,
        model_ref: str | ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        ref = parse_model_ref(model_ref) if isinstance(model_ref, str) else model_ref
        provider = self.providers.get(ref.provider)
        if provider is None:
            return ProviderResponse(ok=False, text="", error=f"Unsupported model provider: {ref.provider}")
        try:
            return provider.chat(ref, prompt, system_prompt=system_prompt, options=options)
        except Exception as exc:
            return ProviderResponse(ok=False, text="", error=redact_secrets(exc))

    def provider_available(self, provider: str) -> bool:
        item = self.providers.get(provider)
        if item is None:
            return False
        availability = getattr(item, "available", None)
        if callable(availability):
            return bool(availability())
        if provider == "ollama":
            return True
        return False

    def provider_status(self) -> dict[str, dict[str, object]]:
        status: dict[str, dict[str, object]] = {}
        for name in sorted(self.providers):
            item = self.providers[name]
            key_env = getattr(item, "api_key_env", None)
            base_env = getattr(item, "base_url_env", None)
            configured = self.provider_available(name)
            status[name] = {
                "configured": configured if name != "ollama" else True,
                "available": configured if name != "ollama" else None,
                "key_source": key_env if key_env and os.environ.get(key_env) else None,
            }
            if base_env:
                status[name]["base_url_source"] = base_env if os.environ.get(base_env) else None
            if name == "ollama":
                status[name]["note"] = "Local model availability is reported in usable_models and missing_models."
        return status


class OllamaProvider:
    def __init__(self, timeout_s: int = 120, client: object | None = None):
        self.timeout_s = timeout_s
        self._client = client

    @property
    def client(self) -> object:
        if self._client is None:
            import ollama

            self._client = ollama.Client(timeout=self.timeout_s)
        return self._client

    def list_models(self) -> list[str]:
        response = self.client.list()
        return sorted(_extract_model_names(response))

    def chat(
        self,
        model_ref: ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        started = time.perf_counter()
        response = self.client.chat(model=model_ref.model, messages=messages, options=options or {})
        latency = time.perf_counter() - started
        try:
            text = response["message"]["content"].strip()
        except Exception:
            text = str(response).strip()
        metadata = {
            "provider": "ollama",
            "model": model_ref.model,
            "total_duration": getattr(response, "total_duration", None),
            "load_duration": getattr(response, "load_duration", None),
        }
        if isinstance(response, dict):
            metadata.update(
                {
                    "total_duration": response.get("total_duration"),
                    "load_duration": response.get("load_duration"),
                    "prompt_eval_count": response.get("prompt_eval_count"),
                    "eval_count": response.get("eval_count"),
                }
            )
        return ProviderResponse(ok=True, text=text, latency_s=latency, metadata=metadata)


class OpenAIProvider:
    def __init__(
        self,
        provider_name: str,
        api_key_env: str,
        base_url: str,
        timeout_s: int = 120,
        base_url_env: str | None = None,
    ):
        self.provider_name = provider_name
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.base_url_env = base_url_env

    def available(self) -> bool:
        return bool(self._api_key() and self.base_url)

    def list_models(self) -> list[str]:
        if not self._api_key() or not self.base_url:
            return []
        try:
            data = self._request("GET", "/models")
        except Exception:
            return []
        return sorted(str(item.get("id", "")) for item in data.get("data", []) if item.get("id"))

    def chat(
        self,
        model_ref: ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        options = options or {}
        if not self._api_key():
            return ProviderResponse(
                ok=False,
                text="",
                error=f"{self.provider_name} provider is unavailable: set {self.api_key_env}.",
            )
        if not self.base_url:
            return ProviderResponse(
                ok=False,
                text="",
                error=f"{self.provider_name} provider is unavailable: set SYNAPSE_OPENAI_COMPATIBLE_BASE_URL.",
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, object] = {"model": model_ref.model, "messages": messages}
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "num_predict" in options:
            payload["max_tokens"] = options["num_predict"]
        if "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]

        started = time.perf_counter()
        data = self._request("POST", "/chat/completions", payload)
        latency = time.perf_counter() - started
        try:
            text = str(data["choices"][0]["message"]["content"]).strip()
        except Exception:
            text = ""
        return ProviderResponse(
            ok=bool(text),
            text=text,
            error="" if text else "Provider returned an empty response.",
            latency_s=latency,
            metadata={"provider": self.provider_name, "model": model_ref.model},
        )

    def _api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Synapse/0.3.0",
        }

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError(f"{self.provider_name} provider is unavailable: set {self.api_key_env}.")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=self._headers(api_key),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(redact_secrets(f"{self.provider_name} request failed: HTTP {exc.code}: {detail}")) from exc
        except Exception as exc:
            raise RuntimeError(redact_secrets(f"{self.provider_name} request failed: {exc}")) from exc


class AnthropicProvider:
    api_key_env = "SYNAPSE_ANTHROPIC_API_KEY"

    def __init__(self, timeout_s: int = 120, base_url: str = "https://api.anthropic.com/v1"):
        self.timeout_s = timeout_s
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(os.environ.get(self.api_key_env))

    def list_models(self) -> list[str]:
        return []

    def chat(
        self,
        model_ref: ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        if not self.available():
            return ProviderResponse(ok=False, text="", error=f"anthropic provider is unavailable: set {self.api_key_env}.")

        options = options or {}
        payload: dict[str, object] = {
            "model": model_ref.model,
            "max_tokens": int(options.get("max_tokens") or options.get("num_predict") or 2048),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        if "temperature" in options:
            payload["temperature"] = options["temperature"]

        started = time.perf_counter()
        data = self._request(payload)
        latency = time.perf_counter() - started
        text = _extract_anthropic_text(data)
        return ProviderResponse(
            ok=bool(text),
            text=text,
            error="" if text else "Provider returned an empty response.",
            latency_s=latency,
            metadata={"provider": "anthropic", "model": model_ref.model},
        )

    def _request(self, payload: dict[str, object]) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/messages",
            data=body,
            method="POST",
            headers={
                "x-api-key": os.environ.get(self.api_key_env, ""),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(redact_secrets(f"anthropic request failed: HTTP {exc.code}: {detail}")) from exc
        except Exception as exc:
            raise RuntimeError(redact_secrets(f"anthropic request failed: {exc}")) from exc


class GeminiProvider:
    api_key_env = "SYNAPSE_GOOGLE_API_KEY"

    def __init__(self, timeout_s: int = 120, base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.timeout_s = timeout_s
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(os.environ.get(self.api_key_env))

    def list_models(self) -> list[str]:
        return []

    def chat(
        self,
        model_ref: ModelRef,
        prompt: str,
        system_prompt: str = "",
        options: dict | None = None,
    ) -> ProviderResponse:
        if not self.available():
            return ProviderResponse(ok=False, text="", error=f"google provider is unavailable: set {self.api_key_env}.")

        options = options or {}
        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        generation_config: dict[str, object] = {}
        if "temperature" in options:
            generation_config["temperature"] = options["temperature"]
        if "max_tokens" in options:
            generation_config["maxOutputTokens"] = options["max_tokens"]
        if "num_predict" in options:
            generation_config["maxOutputTokens"] = options["num_predict"]
        if generation_config:
            payload["generationConfig"] = generation_config

        started = time.perf_counter()
        data = self._request(model_ref.model, payload)
        latency = time.perf_counter() - started
        text = _extract_gemini_text(data)
        return ProviderResponse(
            ok=bool(text),
            text=text,
            error="" if text else "Provider returned an empty response.",
            latency_s=latency,
            metadata={"provider": "google", "model": model_ref.model},
        )

    def _request(self, model: str, payload: dict[str, object]) -> dict:
        api_key = os.environ.get(self.api_key_env, "")
        model_path = model if model.startswith("models/") else f"models/{model}"
        encoded_model = urllib.parse.quote(model_path, safe="/")
        url = f"{self.base_url}/{encoded_model}:generateContent?key={urllib.parse.quote(api_key)}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(redact_secrets(f"google request failed: HTTP {exc.code}: {detail}")) from exc
        except Exception as exc:
            raise RuntimeError(redact_secrets(f"google request failed: {exc}")) from exc


def _extract_model_names(response: object) -> set[str]:
    names: set[str] = set()
    models = getattr(response, "models", None)
    if models is None and isinstance(response, dict):
        models = response.get("models", [])

    for item in models or []:
        name = getattr(item, "model", None) or getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("model") or item.get("name")
        if name:
            names.add(str(name))
    return names


def _extract_anthropic_text(data: dict) -> str:
    parts = []
    for item in data.get("content", []) or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")).strip())
    return "\n".join(part for part in parts if part).strip()


def _extract_gemini_text(data: dict) -> str:
    parts = []
    for candidate in data.get("candidates", []) or []:
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []) or []:
            if isinstance(part, dict) and part.get("text"):
                parts.append(str(part.get("text", "")).strip())
    return "\n".join(part for part in parts if part).strip()
