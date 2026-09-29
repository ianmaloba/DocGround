"""Small OpenAI-compatible chat adapter with injected transport for offline tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import requests

from docground.adapters.base import AdapterError, MissingAPIKeyError, extract_code

HttpPost = Callable[..., Any]


class OpenAICompatibleAdapter:
    """Call a provider's chat-completions endpoint without implicit retries."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        endpoint: str,
        api_key_env: str,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout: float = 60.0,
        post: HttpPost | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self._api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._post = post or requests.post

    def generate(self, prompt: str) -> str:
        api_key = self._api_key or os.environ.get(self.api_key_env)
        if not api_key:
            raise MissingAPIKeyError(
                f"Set {self.api_key_env} to use the {self.provider} adapter"
            )
        response = self._post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            timeout=self.timeout,
        )
        status = getattr(response, "status_code", None)
        if not isinstance(status, int) or status < 200 or status >= 300:
            raise AdapterError(f"{self.provider} returned HTTP {status}; no retry was attempted")
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise AdapterError(f"{self.provider} returned invalid JSON") from error
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                finish_reason = choices[0].get("finish_reason")
                if finish_reason not in (None, "stop"):
                    # A truncated but syntactically valid prefix is not a finished
                    # answer. Do not forward it for verification or export.
                    raise AdapterError(
                        f"{self.provider} did not return a completed text answer; no retry was attempted"
                    )
        content = _message_content(payload)
        if not content.strip():
            raise AdapterError(f"{self.provider} returned an empty message")
        return extract_code(content)


def _message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""
