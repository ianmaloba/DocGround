import pytest

from docground.provenance import sanitize_object, sanitize_text, sha256_text


def test_hash_is_stable_and_secret_text_is_redacted():
    assert sha256_text("task") == sha256_text("task")
    value = "GLM_API_KEY=secret-value Authorization: Bearer abc.def.ghi"
    sanitized = sanitize_text(value)
    assert "secret-value" not in sanitized
    assert "abc.def.ghi" not in sanitized
    assert sanitized.count("[REDACTED]") == 2


def test_nested_record_values_are_redacted_recursively():
    result = sanitize_object({"details": ["MISTRAL_API_KEY=secret-value"]})
    assert "secret-value" not in str(result)


@pytest.mark.parametrize("text", [
    '"GLM_API_KEY": "dummy-secret-123"',
    "'MISTRAL_API_KEY': 'dummy-secret-123'",
    'api_key = "dummy-secret-123"',
    'os.environ["GLM_API_KEY"] = "dummy-secret-123"',
    'Authorization: Bearer dummy-secret-123',
    'ACCESS_TOKEN=dummy-secret-123',
])
def test_quoted_and_unquoted_secret_assignments_are_redacted(text):
    assert "dummy-secret-123" not in sanitize_text(text)


def test_secret_dictionary_values_are_redacted_using_their_key():
    result = sanitize_object({
        "config": {"GLM_API_KEY": "dummy-secret-123", "api_key": "another-secret"},
        "Authorization": "Bearer other-secret", "safe": "keep me",
    })
    assert result == {
        "config": {"GLM_API_KEY": "[REDACTED]", "api_key": "[REDACTED]"},
        "Authorization": "[REDACTED]", "safe": "keep me",
    }
