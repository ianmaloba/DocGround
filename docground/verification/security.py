"""Run Bandit over generated Python without executing it."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from bandit.core import config as bandit_config
from bandit.core import manager as bandit_manager


@dataclass(frozen=True)
class SecurityFinding:
    test_id: str
    test_name: str
    severity: str
    confidence: str
    description: str
    line_number: int


def scan_code(code: str, severity_threshold: str = "LOW") -> list[SecurityFinding]:
    with tempfile.TemporaryDirectory(prefix="docground-bandit-") as directory:
        path = os.path.join(directory, "generated.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code)
        manager = bandit_manager.BanditManager(
            bandit_config.BanditConfig(), "file", quiet=True
        )
        manager.discover_files([path])
        manager.run_tests()
        issues = manager.get_issue_list(sev_level=severity_threshold)
    findings = [
        SecurityFinding(
            test_id=issue.test_id,
            test_name=issue.test,
            severity=str(issue.severity).upper(),
            confidence=str(issue.confidence).upper(),
            description=issue.text,
            line_number=issue.lineno,
        )
        for issue in issues
    ]
    return sorted(findings, key=lambda item: (item.line_number, item.test_id))
