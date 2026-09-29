from io import StringIO
from types import SimpleNamespace

from docground.adapters.base import FakeAdapter
from docground.cli import command_check, command_generate, command_ground


def test_generate_cancel_does_not_call_model_or_export(tmp_path):
    adapter = FakeAdapter("print('ok')")
    output = StringIO()
    result = command_generate(
        "Write a small Python function", "fake", "fake-model", tmp_path / "run.json",
        adapter=adapter, input_fn=lambda _: "c", output=output,
    )
    assert result == 0
    assert adapter.calls == []
    assert not (tmp_path / "run.json").exists()


def test_generate_uses_explicit_prompt_choice_and_requires_export_approval(tmp_path):
    task = "Write a small Python function"
    adapter = FakeAdapter("def answer(): return 42")
    answers = iter(("o", "n"))
    output = StringIO()
    result = command_generate(
        task, "fake", "fake-model", tmp_path / "run.json",
        adapter=adapter, input_fn=lambda _: next(answers), output=output,
    )
    assert result == 0
    assert adapter.calls == [task]
    assert not (tmp_path / "run.json").exists()
    assert "Export declined" in output.getvalue()


def test_generate_exports_only_after_second_explicit_approval(tmp_path):
    adapter = FakeAdapter("def answer(): return 42")
    answers = iter(("o", "y"))
    destination = tmp_path / "run.json"
    result = command_generate(
        "Write a small Python function", "fake", "fake-model", destination,
        adapter=adapter, input_fn=lambda _: next(answers), output=StringIO(),
    )
    assert result == 0
    assert destination.exists()


def test_generate_redacts_display_and_export_but_sends_exact_approved_prompt(tmp_path, monkeypatch):
    task = 'Use GLM_API_KEY="prompt-dummy-secret"'
    adapter = FakeAdapter('MISTRAL_API_KEY = "code-dummy-secret"')
    report = SimpleNamespace(
        verdict="warn",
        to_dict=lambda: {"verdict": "warn", "stdout": 'XAI_API_KEY="output-dummy-secret"'},
    )
    monkeypatch.setattr("docground.cli.evaluate", lambda *args, **kwargs: report)
    answers = iter(("o", "y"))
    output = StringIO()
    destination = tmp_path / "run.json"
    assert command_generate(
        task, "fake", "fake-model", destination, adapter=adapter,
        input_fn=lambda _: next(answers), output=output,
    ) == 0
    assert adapter.calls == [task]
    for value in ("prompt-dummy-secret", "code-dummy-secret", "output-dummy-secret"):
        assert value not in output.getvalue()
        assert value not in destination.read_text()


def test_ground_redacts_prompt_secrets_from_display():
    output = StringIO()
    command_ground('Use GLM_API_KEY="prompt-dummy-secret"', output=output)
    assert "prompt-dummy-secret" not in output.getvalue()


def test_check_redacts_verification_output(tmp_path, monkeypatch):
    code_path = tmp_path / "candidate.py"
    code_path.write_text("pass")
    report = SimpleNamespace(
        verdict="warn", to_dict=lambda: {"stdout": '"GLM_API_KEY": "dummy-secret"'},
    )
    monkeypatch.setattr("docground.cli.evaluate", lambda *args, **kwargs: report)
    output = StringIO()
    command_check(code_path, output=output)
    assert "dummy-secret" not in output.getvalue()
