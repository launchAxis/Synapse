from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable

from synapse.providers import ProviderRouter, redact_secrets


_RETRY_HINT_PATTERNS = (
    r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"',
    r"retry\s+in\s+(\d+(?:\.\d+)?)s",
    r"Retry-After\s*:?\s*(\d+(?:\.\d+)?)",
)
_RETRYABLE_MARKERS = (
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "RESOURCE_EXHAUSTED",
    "rate limit",
    "high demand",
    "temporarily unavailable",
)
_NON_RETRYABLE_MARKERS = (
    "tokens per day",
    "tpd",
    "daily token",
    "daily quota",
    "billing",
    "prepayment credits are depleted",
    "insufficient_quota",
)


class OllamaBenchClient:
    def __init__(
        self,
        timeout_s: int = 120,
        router: ProviderRouter | None = None,
        retry_attempts: int = 0,
        retry_backoff_s: float = 2.0,
        retry_max_sleep_s: float = 30.0,
        min_request_interval_s: float = 0.0,
        sleep_fn: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.timeout_s = timeout_s
        self.router = router or ProviderRouter(timeout_s=timeout_s)
        self.retry_attempts = max(0, int(retry_attempts))
        self.retry_backoff_s = max(0.0, float(retry_backoff_s))
        self.retry_max_sleep_s = max(0.0, float(retry_max_sleep_s))
        self.min_request_interval_s = max(0.0, float(min_request_interval_s))
        self._sleep = sleep_fn or time.sleep
        self._clock = clock or time.monotonic
        self._rate_lock = threading.Lock()
        self._last_request_at: float | None = None

    def chat(self, model: str, prompt: str, system_prompt: str = "", options: dict | None = None) -> tuple[str, float, dict]:
        last_error = "Provider returned no response."
        for attempt in range(self.retry_attempts + 1):
            self._wait_for_rate_limit()
            response = self.router.chat(model, prompt, system_prompt=system_prompt, options=options or {})
            if response.ok:
                return response.text, response.latency_s, response.metadata

            last_error = redact_secrets(response.error)
            if attempt >= self.retry_attempts or not is_retryable_provider_error(last_error):
                break

            delay = retry_delay_seconds(
                last_error,
                attempt=attempt,
                backoff_s=self.retry_backoff_s,
                max_sleep_s=self.retry_max_sleep_s,
            )
            if delay > 0:
                self._sleep(delay)

        raise RuntimeError(redact_secrets(last_error))

    def _wait_for_rate_limit(self) -> None:
        if self.min_request_interval_s <= 0:
            return

        with self._rate_lock:
            now = self._clock()
            if self._last_request_at is not None:
                elapsed = now - self._last_request_at
                wait_s = self.min_request_interval_s - elapsed
                if wait_s > 0:
                    self._sleep(wait_s)
                    now = self._clock()
            self._last_request_at = now


def bench_client_from_judge_config(judge_config) -> OllamaBenchClient:
    return OllamaBenchClient(
        timeout_s=judge_config.timeout_s,
        retry_attempts=getattr(judge_config, "retry_attempts", 0),
        retry_backoff_s=getattr(judge_config, "retry_backoff_s", 2.0),
        retry_max_sleep_s=getattr(judge_config, "retry_max_sleep_s", 30.0),
        min_request_interval_s=getattr(judge_config, "min_request_interval_s", 0.0),
    )


def is_retryable_provider_error(error: object) -> bool:
    lower_text = str(error).lower()
    if is_non_retryable_provider_error(lower_text):
        return False
    return any(marker.lower() in lower_text for marker in _RETRYABLE_MARKERS)


def is_non_retryable_provider_error(error: object) -> bool:
    lower_text = str(error).lower()
    return any(marker in lower_text for marker in _NON_RETRYABLE_MARKERS)


def retry_delay_seconds(error: object, attempt: int, backoff_s: float, max_sleep_s: float) -> float:
    retry_hint = retry_after_seconds(error)
    if retry_hint is None:
        retry_hint = max(0.0, backoff_s) * (2 ** max(0, attempt))
    if max_sleep_s > 0:
        retry_hint = min(retry_hint, max_sleep_s)
    return max(0.0, retry_hint)


def retry_after_seconds(error: object) -> float | None:
    text = str(error)
    for pattern in _RETRY_HINT_PATTERNS:
        match = re.search(pattern, text, flags=re.I)
        if match:
            try:
                return max(0.0, float(match.group(1)))
            except ValueError:
                return None
    return None
