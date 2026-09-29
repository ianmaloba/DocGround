from docground.verification.correctness import CorrectnessResult
from docground.verification.gate import evaluate
from docground.verification.hallucination import HallucinationFinding


class FakeRunner:
    def __init__(self, result):
        self.result = result

    def run(self, code, test, timeout):
        return self.result


def test_parse_failure_blocks_and_skips_other_checks():
    result = evaluate("def unfinished(")
    assert result.verdict == "block"
    assert result.syntax_status == "fail"
    assert result.security_findings == ()


def test_successful_static_and_sandbox_checks_pass():
    result = evaluate(
        "def answer(): return 42",
        test="def test_answer(): assert answer() == 42",
        package_resolver=lambda name: True,
        correctness_runner=FakeRunner(CorrectnessResult("pass", returncode=0)),
    )
    assert result.verdict == "pass"


def test_no_test_is_warned_about_not_counted_as_a_failure():
    result = evaluate("def answer(): return 42", package_resolver=lambda name: True)
    assert result.verdict == "warn"
    assert "not tested" in result.notes[0]


def test_correctness_failure_blocks():
    result = evaluate(
        "def answer(): return 0",
        test="def test_answer(): assert answer() == 42",
        package_resolver=lambda name: True,
        correctness_runner=FakeRunner(CorrectnessResult("fail", returncode=1)),
    )
    assert result.verdict == "block"
