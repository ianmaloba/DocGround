"""Human-reviewed command-line workflow for DocGround."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from docground.adapters.providers import build_adapter
from docground.grounding.doc_store import DocStore
from docground.grounding.wrapper import ground
from docground.provenance import sanitize_object, sanitize_text
from docground.verification.gate import evaluate
from docground.workflow import PromptDecision, ReviewSession, WorkflowStateError

InputFn = Callable[[str], str]


def command_ground(task: str, output: TextIO = sys.stdout) -> int:
    proposal = ground(task)
    print(sanitize_text(proposal.text), file=output)
    return 0


def command_check(
    code_path: str | Path,
    test_path: str | Path | None = None,
    output: TextIO = sys.stdout,
) -> int:
    code = Path(code_path).read_text(encoding="utf-8")
    test = Path(test_path).read_text(encoding="utf-8") if test_path else None
    report = evaluate(code, test=test)
    print(json.dumps(sanitize_object(report.to_dict()), indent=2, sort_keys=True), file=output)
    return 2 if report.verdict == "block" else 0


def command_generate(
    task: str,
    provider: str,
    model: str,
    export_path: str | Path,
    test_path: str | Path | None = None,
    *,
    adapter: object | None = None,
    input_fn: InputFn = input,
    output: TextIO = sys.stdout,
) -> int:
    session = ReviewSession.prepare(task, provider, model)
    print("ORIGINAL PROMPT:\n" + sanitize_text(task), file=output)
    print("\nSUGGESTED PROMPT:\n" + sanitize_text(session.proposal.text), file=output)
    choice = input_fn("Choose [s]uggested, [o]riginal, [e]dit, or [c]ancel: ").strip().lower()
    if choice == "c":
        session.decide(PromptDecision.CANCEL)
        print("Cancelled before provider call.", file=output)
        return 0
    if choice == "s":
        session.decide(PromptDecision.APPROVE_SUGGESTION)
    elif choice == "o":
        session.decide(PromptDecision.USE_ORIGINAL)
    elif choice == "e":
        edited = input_fn("Enter the complete prompt to send: ")
        session.decide(PromptDecision.USER_EDITED, edited)
    else:
        print("Invalid choice. No provider call was made.", file=output)
        return 2

    selected_adapter = adapter or build_adapter(provider, model)
    try:
        generated_code = session.generate(selected_adapter)  # type: ignore[arg-type]
    except Exception as error:
        # Provider exception bodies can contain request details; do not print them.
        print(f"Generation failed ({type(error).__name__}). No record was exported.", file=output)
        return 2

    print("\nGENERATED CODE:\n" + sanitize_text(generated_code), file=output)
    test = Path(test_path).read_text(encoding="utf-8") if test_path else None
    report = evaluate(generated_code, test=test)
    session.record_verification(report.to_dict())
    print(
        "\nVERIFICATION:\n" + json.dumps(sanitize_object(report.to_dict()), indent=2, sort_keys=True),
        file=output,
    )
    if report.verdict == "block":
        print("Export blocked by verification findings.", file=output)
        return 2
    approval = input_fn("Approve writing this run's provenance record? [y/N]: ").strip().lower()
    if approval != "y":
        print("Export declined. No record was written.", file=output)
        return 0
    try:
        session.approve_export()
        path = session.export_record(export_path)
    except (OSError, WorkflowStateError) as error:
        print(f"Export failed ({type(error).__name__}).", file=output)
        return 2
    print(f"Provenance record written to {path}", file=output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docground")
    commands = parser.add_subparsers(dest="command", required=True)

    ground_parser = commands.add_parser("ground", help="show a proposed grounded prompt")
    ground_parser.add_argument("task")

    check_parser = commands.add_parser("check", help="run verification on a code file")
    check_parser.add_argument("code")
    check_parser.add_argument("--test")

    generate_parser = commands.add_parser("generate", help="review a prompt and generate code")
    generate_parser.add_argument("task")
    generate_parser.add_argument("--provider", required=True, choices=("deepseek", "glm", "xai", "mistral"))
    generate_parser.add_argument("--model", required=True)
    generate_parser.add_argument("--export", required=True, help="new provenance JSON path")
    generate_parser.add_argument("--test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ground":
        return command_ground(args.task)
    if args.command == "check":
        return command_check(args.code, args.test)
    if args.command == "generate":
        return command_generate(
            args.task, args.provider, args.model, args.export, test_path=args.test
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
