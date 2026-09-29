from types import SimpleNamespace

import pytest

from docground.adapters.base import AdapterError, MissingAPIKeyError
from docground.adapters.openai_compatible import OpenAICompatibleAdapter
from docground.adapters.providers import PROVIDERS, build_adapter


def _response(status=200, payload=None):
    return SimpleNamespace(status_code=status, json=lambda: payload or {})


def test_provider_factory_supports_only_the_active_non_openai_set():
    assert set(PROVIDERS) == {"deepseek", "glm", "xai", "mistral"}
    for provider in PROVIDERS:
        adapter = build_adapter(provider, "test-model", api_key="test-secret")
        assert adapter.provider == provider
        assert adapter.model == "test-model"
    with pytest.raises(ValueError):
        build_adapter("openai", "test-model")


def test_missing_key_fails_before_transport_is_called(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    calls = []
    adapter = build_adapter("deepseek", "test-model", post=lambda *a, **k: calls.append((a, k)))
    with pytest.raises(MissingAPIKeyError):
        adapter.generate("prompt")
    assert calls == []


def test_adapter_sends_selected_prompt_and_extracts_code():
    captured = {}

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _response(200, {"choices": [{"message": {"content": "```python\nprint(1)\n```"}}]})

    adapter = build_adapter("glm", "glm-test", api_key="private-key", post=post)
    assert adapter.generate("approved prompt") == "print(1)"
    assert captured["json"]["messages"] == [{"role": "user", "content": "approved prompt"}]
    assert captured["json"]["model"] == "glm-test"
    assert captured["headers"]["Authorization"] == "Bearer private-key"
    assert captured["url"] == PROVIDERS["glm"].endpoint


def test_adapter_does_not_retry_or_echo_credentials_on_http_error():
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _response(429, {"error": {"message": "sensitive provider detail"}})

    adapter = build_adapter("mistral", "test-model", api_key="do-not-log-this", post=post)
    with pytest.raises(AdapterError) as error:
        adapter.generate("approved prompt")
    assert len(calls) == 1
    assert "429" in str(error.value)
    assert "do-not-log-this" not in str(error.value)
    assert "sensitive provider detail" not in str(error.value)


def test_adapter_accepts_text_blocks_and_rejects_invalid_json():
    adapter = OpenAICompatibleAdapter(
        provider="xai",
        model="test-model",
        endpoint="https://example.invalid",
        api_key_env="XAI_API_KEY",
        api_key="key",
        post=lambda *args, **kwargs: _response(
            200,
            {"choices": [{"message": {"content": [{"type": "text", "text": "return 7"}]}}]},
        ),
    )
    assert adapter.generate("prompt") == "return 7"

    broken = OpenAICompatibleAdapter(
        provider="xai",
        model="test-model",
        endpoint="https://example.invalid",
        api_key_env="XAI_API_KEY",
        api_key="key",
        post=lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: (_ for _ in ()).throw(ValueError())),
    )
    with pytest.raises(AdapterError, match="invalid JSON"):
        broken.generate("prompt")


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls"])
def test_incomplete_or_non_text_completion_is_not_returned_as_code(finish_reason):
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs)
        return _response(200, {"choices": [{
            "finish_reason": finish_reason,
            "message": {"content": "def answer(): return 42"},
        }]})

    adapter = build_adapter("mistral", "test-model", api_key="dummy-key", post=post)
    with pytest.raises(AdapterError, match="completed text answer"):
        adapter.generate("prompt")
    assert len(calls) == 1
