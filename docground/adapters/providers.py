"""Factories for the active non-OpenAI provider adapters."""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from docground.adapters.openai_compatible import OpenAICompatibleAdapter


@dataclass(frozen=True)
class ProviderSettings:
    endpoint: str
    api_key_env: str


PROVIDERS: dict[str, ProviderSettings] = {
    "deepseek": ProviderSettings(
        endpoint="https://api.deepseek.com/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
    ),
    "glm": ProviderSettings(
        endpoint="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        api_key_env="GLM_API_KEY",
    ),
    "xai": ProviderSettings(
        endpoint="https://api.x.ai/v1/chat/completions",
        api_key_env="XAI_API_KEY",
    ),
    "mistral": ProviderSettings(
        endpoint="https://api.mistral.ai/v1/chat/completions",
        api_key_env="MISTRAL_API_KEY",
    ),
}


def build_adapter(provider: str, model: str, **options: object) -> OpenAICompatibleAdapter:
    """Build an adapter for an explicitly selected provider and model."""
    normalized = provider.lower()
    if normalized not in PROVIDERS:
        raise ValueError(f"Unsupported provider {provider!r}; choose from {sorted(PROVIDERS)}")
    load_dotenv(override=False)
    settings = PROVIDERS[normalized]
    return OpenAICompatibleAdapter(
        provider=normalized,
        model=model,
        endpoint=settings.endpoint,
        api_key_env=settings.api_key_env,
        **options,
    )
