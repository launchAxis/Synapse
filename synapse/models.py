# This file is the only place that talks directly to Ollama.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import ollama


@dataclass
class ModelResponse:
    ok: bool
    text: str
    error: str = ""


class ModelManager:
    def __init__(self, configured_models: Dict[str, str], timeout_seconds: int = 45, verbose: bool = True):
        self.configured_models = configured_models
        self.usable_models: Dict[str, str] = {}
        self.missing_models: Dict[str, str] = {}
        self.available_model_names: set[str] = set()
        self.verbose = verbose
        self.client = ollama.Client(timeout=timeout_seconds)

    def refresh_available_models(self) -> Dict[str, str]:
        try:
            response = self.client.list()
        except Exception as exc:
            self._warn("could not connect to Ollama.")
            self._warn("Make sure Ollama is installed and running, then try again.")
            self._warn(f"Details: {exc}")
            self.usable_models = {}
            self.missing_models = dict(self.configured_models)
            self.available_model_names = set()
            return self.usable_models

        installed = self._extract_model_names(response)
        self.available_model_names = installed
        usable = {}
        missing = {}
        for key, model in self.configured_models.items():
            if model in installed:
                usable[key] = model
            else:
                missing[key] = model

        if missing:
            self._warn("some configured Ollama models are not installed:")
            for model in missing.values():
                self._warn(f"- {model} (run: ollama pull {model})")
            if installed:
                self._warn("Available models: " + ", ".join(sorted(installed)))
            else:
                self._warn("No installed Ollama models were reported.")

        self.usable_models = usable
        self.missing_models = missing
        return usable

    def ask(self, model: str, prompt: str) -> ModelResponse:
        try:
            response = self.client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            message = str(exc)
            if "not found" in message.lower() or "pull model" in message.lower():
                self._warn(f"model {model} is not installed. Run: ollama pull {model}")
            else:
                self._warn(f"model {model} failed: {message}")
            return ModelResponse(ok=False, text="", error=message)

        text = ""
        try:
            text = response["message"]["content"].strip()
        except Exception:
            text = str(response).strip()

        if not text:
            message = f"model {model} returned an empty response"
            self._warn(message)
            return ModelResponse(ok=False, text="", error=message)

        return ModelResponse(ok=True, text=text)

    def _warn(self, message: str) -> None:
        if self.verbose:
            print(f"Warning: {message}")

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
