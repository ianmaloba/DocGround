"""Provider-neutral generation interface and a deterministic offline adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class MissingAPIKeyError(RuntimeError):
    """Raised when a live adapter has no configured credential."""


class AdapterError(RuntimeError):
    """A provider failure with non-secret diagnostic metadata."""


class ModelAdapter(Protocol):
    provider: str
    model: str

    def generate(self, prompt: str) -> str: ...


@dataclass
class FakeAdapter:
    """An offline adapter for tests. It records exactly what it was asked to send."""

    response: str
    provider: str = "fake"
    model: str = "fake-model"
    calls: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def extract_code(response: str) -> str:
    """Return the first fenced block when present, otherwise return the response."""
    if "```" not in response:
        return response.strip()
    after = response.split("```", 1)[1]
    first_line, newline, remainder = after.partition("\n")
    tag = first_line.strip()
    body = remainder if newline and (not tag or tag.isidentifier()) else after
    return body.split("```", 1)[0].strip()
