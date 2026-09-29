import json

import pytest

from docground.adapters.base import FakeAdapter
from docground.workflow import (
    PromptDecision,
    ReviewSession,
    WorkflowStateError,
    WorkflowStatus,
)


def test_generation_is_blocked_until_prompt_choice_is_explicit():
    session = ReviewSession.prepare("Read a CSV with pandas", "fake", "fake-model")
    adapter = FakeAdapter("print('ok')")
    with pytest.raises(WorkflowStateError):
        session.generate(adapter)
    assert adapter.calls == []


def test_use_original_sends_original_text_not_grounded_proposal():
    task = "Read a CSV with pandas"
    session = ReviewSession.prepare(task, "fake", "fake-model")
    session.decide(PromptDecision.USE_ORIGINAL)
    adapter = FakeAdapter("print('ok')")
    session.generate(adapter)
    assert adapter.calls == [task]
    assert session.status is WorkflowStatus.GENERATED


def test_approved_suggestion_is_the_exact_prompt_sent_to_adapter():
    session = ReviewSession.prepare("Read a CSV with pandas", "fake", "fake-model")
    session.decide(PromptDecision.APPROVE_SUGGESTION)
    adapter = FakeAdapter("print('ok')")
    session.generate(adapter)
    assert adapter.calls == [session.proposal.text]


def test_user_edit_and_cancel_are_distinct_decisions():
    edited = ReviewSession.prepare("original", "fake", "fake-model")
    edited.decide(PromptDecision.USER_EDITED, "edited task")
    assert edited.selected_prompt == "edited task"

    cancelled = ReviewSession.prepare("original", "fake", "fake-model")
    cancelled.decide(PromptDecision.CANCEL)
    with pytest.raises(WorkflowStateError):
        cancelled.generate(FakeAdapter("unused"))


def test_export_requires_verification_and_explicit_approval(tmp_path):
    session = ReviewSession.prepare("task", "fake", "fake-model")
    session.decide(PromptDecision.USE_ORIGINAL)
    session.generate(FakeAdapter("def answer(): return 42"))
    destination = tmp_path / "run.json"
    with pytest.raises(WorkflowStateError):
        session.export_record(destination)
    session.record_verification({"verdict": "pass", "checks": {"syntax": "pass"}})
    with pytest.raises(WorkflowStateError):
        session.export_record(destination)
    session.approve_export()
    session.export_record(destination)
    assert json.loads(destination.read_text())["status"] == "approved_for_export"
    assert session.status is WorkflowStatus.EXPORTED


def test_blocking_verification_cannot_be_exported(tmp_path):
    session = ReviewSession.prepare("task", "fake", "fake-model")
    session.decide(PromptDecision.USE_ORIGINAL)
    session.generate(FakeAdapter("code"))
    session.record_verification({"verdict": "block"})
    with pytest.raises(WorkflowStateError):
        session.approve_export()


def test_export_is_append_only_and_does_not_overwrite(tmp_path):
    session = ReviewSession.prepare("task", "fake", "fake-model")
    session.decide(PromptDecision.USE_ORIGINAL)
    session.generate(FakeAdapter("code"))
    session.record_verification({"verdict": "pass"})
    session.approve_export()
    destination = tmp_path / "run.json"
    destination.write_text("existing")
    with pytest.raises(FileExistsError):
        session.export_record(destination)
    assert destination.read_text() == "existing"
