"""Stable hashes and conservative redaction for local workflow records."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_SECRET_KEY = r"(?:(?:OPENAI|GLM|DEEPSEEK|XAI|MINIMAX|MISTRAL)_)?API_KEY|AUTHORIZATION|ACCESS_TOKEN"
_SENSITIVE_KEY = re.compile(rf"(?:{_SECRET_KEY})", re.IGNORECASE)
_SECRET_PATTERNS = (
    re.compile(
        rf"(?i)(\b(?:{_SECRET_KEY})[\"']?\s*\]?\s*[=:]\s*)"
        r"(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;}]+)"
    ),
    re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(
            lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]",
            sanitized,
        )
    return sanitized


def sanitize_object(value: Any) -> Any:
    """Recursively redact text fields and retain JSON-compatible values."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {
            sanitize_text(str(key)): (
                "[REDACTED]" if _SENSITIVE_KEY.fullmatch(str(key)) else sanitize_object(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_object(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value))
