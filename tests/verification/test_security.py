from docground.verification.security import scan_code


def test_bandit_finds_assert_in_generated_source():
    findings = scan_code("def f(x):\n    assert x\n")
    assert any(item.test_id == "B101" and item.line_number == 2 for item in findings)


def test_bandit_accepts_simple_safe_source():
    assert scan_code("def add(a, b):\n    return a + b\n") == []
