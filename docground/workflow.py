"""Review, approve, generate, verify, and explicitly approve export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from docground.adapters.base import ModelAdapter
from docground.grounding.doc_store import DocStore
from docground.grounding.wrapper import GroundedPrompt, ground
from docground.provenance import sanitize_object, sanitize_text, sha256_text


class PromptDecision(StrEnum):
    APPROVE_SUGGESTION = "approve_suggestion"
    USE_ORIGINAL = "use_original"
    USER_EDITED = "user_edited"
    CANCEL = "cancel"


class WorkflowStatus(StrEnum):
    AWAITING_PROMPT_APPROVAL = "awaiting_prompt_approval"
    PROMPT_APPROVED = "prompt_approved"
    CANCELLED = "cancelled"
    GENERATED = "generated"
    VERIFIED = "verified"
    APPROVED_FOR_EXPORT = "approved_for_export"
    EXPORTED = "exported"


class WorkflowStateError(RuntimeError):
    """Raised when a workflow transition is attempted out of order."""


@dataclass
class ReviewSession:
    """A task's prompt decision and resulting model/verification provenance."""

    original_task: str
    proposal: GroundedPrompt
    provider: str
    model: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: WorkflowStatus = WorkflowStatus.AWAITING_PROMPT_APPROVAL
    decision: PromptDecision | None = None
    selected_prompt: str | None = None
    generated_code: str | None = None
    verification: dict[str, object] | None = None
    export_approval_at: str | None = None

    @classmethod
    def prepare(
        cls,
        task: str,
        provider: str,
        model: str,
        store: DocStore | None = None,
    ) -> "ReviewSession":
        return cls(
            original_task=task,
            proposal=ground(task, store=store),
            provider=provider,
            model=model,
        )

    def decide(
        self,
        decision: PromptDecision,
        edited_prompt: str | None = None,
    ) -> None:
        self._require_status(WorkflowStatus.AWAITING_PROMPT_APPROVAL)
        if decision is PromptDecision.CANCEL:
            self.decision = decision
            self.status = WorkflowStatus.CANCELLED
            return
        if decision is PromptDecision.APPROVE_SUGGESTION:
            selected = self.proposal.text
        elif decision is PromptDecision.USE_ORIGINAL:
            selected = self.original_task
        elif decision is PromptDecision.USER_EDITED:
            selected = edited_prompt.strip() if isinstance(edited_prompt, str) else ""
            if not selected:
                raise ValueError("An edited prompt must contain non-whitespace text")
        else:
            raise ValueError(f"Unsupported prompt decision: {decision}")
        self.decision = decision
        self.selected_prompt = selected
        self.status = WorkflowStatus.PROMPT_APPROVED

    def generate(self, adapter: ModelAdapter) -> str:
        self._require_status(WorkflowStatus.PROMPT_APPROVED)
        if self.selected_prompt is None:
            raise WorkflowStateError("No approved prompt is selected")
        if adapter.provider != self.provider or adapter.model != self.model:
            raise WorkflowStateError("Adapter provider/model does not match the reviewed selection")
        self.generated_code = adapter.generate(self.selected_prompt)
        self.status = WorkflowStatus.GENERATED
        return self.generated_code

    def record_verification(self, result: dict[str, object]) -> None:
        self._require_status(WorkflowStatus.GENERATED)
        self.verification = dict(result)
        self.status = WorkflowStatus.VERIFIED

    def approve_export(self) -> None:
        self._require_status(WorkflowStatus.VERIFIED)
        if self.verification is None or self.verification.get("verdict") not in {"pass", "warn"}:
            raise WorkflowStateError("A blocking or missing verification result cannot be exported")
        self.export_approval_at = datetime.now(UTC).isoformat()
        self.status = WorkflowStatus.APPROVED_FOR_EXPORT

    def export_record(self, path: str | Path) -> Path:
        self._require_status(WorkflowStatus.APPROVED_FOR_EXPORT)
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(self.to_record(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        self.status = WorkflowStatus.EXPORTED
        return destination

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "provider": self.provider,
            "model": self.model,
            "decision": self.decision.value if self.decision else None,
            "prompt_versions": {
                "original": sanitize_text(self.original_task),
                "suggested": sanitize_text(self.proposal.text),
                "selected": sanitize_text(self.selected_prompt or ""),
            },
            "prompt_hashes": {
                "original": sha256_text(self.original_task),
                "suggested": sha256_text(self.proposal.text),
                "selected": sha256_text(self.selected_prompt or ""),
            },
            "documentation": {
                "libraries": list(self.proposal.libraries),
                "snapshot_date": self.proposal.snapshot_date,
                "snapshot_sha256": self.proposal.snapshot_sha256,
                "snapshot_metadata": sanitize_object(self.proposal.snapshot_metadata),
            },
            "generated_code": sanitize_text(self.generated_code or ""),
            "generated_code_sha256": sha256_text(self.generated_code or ""),
            "verification": sanitize_object(self.verification),
            "export_approval_at": self.export_approval_at,
        }

    def _require_status(self, expected: WorkflowStatus) -> None:
        if self.status is not expected:
            raise WorkflowStateError(
                f"Expected workflow status {expected.value!r}, found {self.status.value!r}"
            )
