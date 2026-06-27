# This file tracks configured models and routes model calls through providers.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from synapse.providers import ProviderRouter, parse_model_ref, redact_secrets


@dataclass
class ModelResponse:
    ok: bool
    text: str
    error: str = ""


class ModelManager:
    def __init__(
        self,
        configured_models: Dict[str, str],
        timeout_seconds: int = 45,
        verbose: bool = True,
        client: object | None = None,
        provider_router: ProviderRouter | None = None,
    ):
        self.configured_models = configured_models
        self.usable_models: Dict[str, str] = {}
        self.missing_models: Dict[str, str] = {}
        self.available_model_names: set[str] = set()
        self.verbose = verbose
        self.client = client or self._create_client(timeout_seconds)
        self.provider_router = provider_router or ProviderRouter(
            timeout_s=timeout_seconds,
            ollama_client=self.client,
        )

    def refresh_available_models(self) -> Dict[str, str]:
        try:
            response = self.client.list()
            installed = self._extract_model_names(response)
        except Exception as exc:
            self._warn("could not connect to Ollama.")
            self._warn("Make sure Ollama is installed and running, then try again.")
            self._warn(f"Details: {exc}")
            installed = set()

        self.available_model_names = installed
        usable = {}
        missing = {}
        for key, model in self.configured_models.items():
            model_ref = parse_model_ref(model)
            if model_ref.provider != "ollama":
                if self.provider_router.provider_available(model_ref.provider):
                    usable[key] = model_ref.canonical
                else:
                    missing[key] = model_ref.canonical
            elif model_ref.model in installed:
                usable[key] = model_ref.model
            else:
                missing[key] = model

        if missing:
            self._warn("some configured models are unavailable:")
            for model in missing.values():
                model_ref = parse_model_ref(model)
                if model_ref.provider == "ollama":
                    self._warn(f"- {model} (run: ollama pull {model_ref.model})")
                else:
                    self._warn(f"- {model} (set the provider API key or choose a local preset)")
            if installed:
                self._warn("Available models: " + ", ".join(sorted(installed)))
            else:
                self._warn("No installed Ollama models were reported.")

        self.usable_models = usable
        self.missing_models = missing
        return usable

    def ask(self, model: str, prompt: str) -> ModelResponse:
        model_ref = parse_model_ref(model)
        provider_response = self.provider_router.chat(model_ref, prompt)
        if not provider_response.ok:
            message = redact_secrets(provider_response.error)
            if "not found" in message.lower() or "pull model" in message.lower():
                self._warn(f"model {model_ref.model} is not installed. Run: ollama pull {model_ref.model}")
            else:
                self._warn(f"model {model_ref.canonical} failed: {message}")
            return ModelResponse(ok=False, text="", error=message)

        text = provider_response.text.strip()
        if not text:
            message = f"model {model} returned an empty response"
            self._warn(message)
            return ModelResponse(ok=False, text="", error=message)

        return ModelResponse(ok=True, text=text)

    def _warn(self, message: str) -> None:
        if self.verbose:
            print(f"Warning: {message}")

    @staticmethod
    def _create_client(timeout_seconds: int) -> object:
        try:
            import ollama
        except ModuleNotFoundError as exc:
            return MissingOllamaClient(exc)
        return ollama.Client(timeout=timeout_seconds)

    @staticmethod
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


class MissingOllamaClient:
    def __init__(self, error: ModuleNotFoundError):
        self.error = error

    def list(self) -> object:
        raise RuntimeError("The ollama Python package is not installed.") from self.error

    def chat(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("The ollama Python package is not installed.") from self.error
