"""Provider boundary. One fixed HTTPS endpoint, no tools, no retries, no body logging."""

from dataclasses import dataclass
from typing import Protocol

import httpx2 as httpx

from app.ai.config import AiConfig

ENDPOINT = "https://api.openai.com/v1/chat/completions"
MAX_ANSWER_CHARS = 8000


class AiError(Exception):
    """Failure with a message safe to show: never contains keys, prompts or provider bodies."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int | None
    output_tokens: int | None


class Provider(Protocol):
    def complete(self, system: str, user: str, max_output_tokens: int) -> Completion: ...


class OpenAIProvider:
    def __init__(
        self, config: AiConfig, transport: httpx.BaseTransport | None = None, timeout: float = 45
    ) -> None:
        if not config.api_key:
            raise ValueError("API key required")
        self._config, self._transport, self._timeout = config, transport, timeout

    def complete(self, system: str, user: str, max_output_tokens: int) -> Completion:
        body = {
            "model": self._config.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_completion_tokens": max_output_tokens,
            "store": False,
        }
        try:
            with httpx.Client(
                transport=self._transport, timeout=self._timeout, follow_redirects=False
            ) as client:
                response = client.post(
                    ENDPOINT,
                    json=body,
                    headers={"Authorization": f"Bearer {self._config.api_key}"},
                )
        except httpx.TimeoutException:
            raise AiError(504, "timeout", "The AI service did not answer in time.") from None
        except httpx.HTTPError:
            raise AiError(502, "unreachable", "The AI service could not be reached.") from None
        status = response.status_code
        if status in (401, 403):
            raise AiError(502, "rejected", "The AI service rejected the configured key.")
        if status == 429:
            raise AiError(502, "provider_quota", "The AI service reports a quota or rate limit.")
        if status != 200:
            raise AiError(502, "unavailable", f"The AI service is unavailable ({status}).")
        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
            prompt, answer = usage.get("prompt_tokens"), usage.get("completion_tokens")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise AiError(
                502, "bad_response", "The AI service returned an unusable reply."
            ) from None
        if not isinstance(text, str) or not text.strip():
            raise AiError(502, "bad_response", "The AI service returned an unusable reply.")
        return Completion(
            text.strip()[:MAX_ANSWER_CHARS],
            prompt if isinstance(prompt, int) else None,
            answer if isinstance(answer, int) else None,
        )
