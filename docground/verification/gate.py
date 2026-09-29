"""Combine static API/package, syntax, Bandit, and optional correctness findings."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from typing import Iterable

from docground.grounding.doc_store import DocStore
from docground.verification.correctness import (
    CorrectnessResult,
    CorrectnessRunner,
    check_correctness,
)
from docground.verification.hallucination import (
    HallucinationFinding,
    PackageResolver,
    check_hallucinations,
)
from docground.verification.security import SecurityFinding, scan_code


@dataclass(frozen=True)
class VerificationReport:
    verdict: str
    syntax_status: str
    syntax_error: str | None
    hallucination_findings: tuple[HallucinationFinding, ...]
    security_findings: tuple[SecurityFinding, ...]
    correctness: CorrectnessResult | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "syntax_status": self.syntax_status,
            "syntax_error": self.syntax_error,
            "hallucination_findings": [asdict(item) for item in self.hallucination_findings],
            "security_findings": [asdict(item) for item in self.security_findings],
            "correctness": asdict(self.correctness) if self.correctness else None,
            "notes": list(self.notes),
        }


def evaluate(
    code: str,
    test: str | None = None,
    store: DocStore | None = None,
    package_resolver: PackageResolver | None = None,
    known_local_modules: Iterable[str] = (),
    correctness_runner: CorrectnessRunner | None = None,
    timeout: float = 10.0,
) -> VerificationReport:
    selected_store = DocStore.load() if store is None else store
    try:
        ast.parse(code)
    except SyntaxError as error:
        return VerificationReport(
            verdict="block",
            syntax_status="fail",
            syntax_error=f"{error.msg} (line {error.lineno})",
            hallucination_findings=(),
            security_findings=(),
            correctness=None,
            notes=("Static checks after parsing were not run.",),
        )

    hallucinations = tuple(check_hallucinations(
        code,
        store=selected_store,
        package_resolver=package_resolver,
        known_local_modules=known_local_modules,
    ))
    security = tuple(scan_code(code))
    correctness = check_correctness(code, test=test, timeout=timeout, runner=correctness_runner)
    blocking = any(item.status == "hallucinated" for item in hallucinations)
    blocking = blocking or any(item.severity == "HIGH" for item in security)
    blocking = blocking or bool(correctness and correctness.status in {"fail", "timeout"})

    notes: list[str] = []
    if any(item.status == "unknown" for item in hallucinations):
        notes.append("One or more package checks could not be verified from the package index.")
    if any(item.status == "unverified" for item in hallucinations):
        notes.append("API use outside a partial documentation snapshot is unverified, not called hallucinated.")
    if any(item.severity in {"LOW", "MEDIUM"} for item in security):
        notes.append("Bandit reported one or more low or medium severity findings.")
    if test is None or not test.strip():
        notes.append("Functional correctness was not tested because no test was supplied.")
    elif correctness and correctness.status == "unavailable":
        notes.append("The Docker correctness sandbox is unavailable; generated code was not run on the host.")

    warning = bool(notes) or bool(security) or bool(hallucinations)
    verdict = "block" if blocking else "warn" if warning else "pass"
    return VerificationReport(
        verdict=verdict,
        syntax_status="pass",
        syntax_error=None,
        hallucination_findings=hallucinations,
        security_findings=security,
        correctness=correctness,
        notes=tuple(notes),
    )
