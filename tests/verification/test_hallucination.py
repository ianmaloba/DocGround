from docground.grounding.doc_store import DocStore, LibraryDoc
from docground.verification.hallucination import check_hallucinations


def test_stdlib_and_known_package_imports_do_not_query_pypi():
    store = DocStore.load()
    calls = []
    findings = check_hallucinations(
        "import json\nimport pandas as pd\npd.read_csv('data.csv')",
        store,
        package_resolver=lambda name: calls.append(name) or False,
    )
    assert findings == []
    assert calls == []


def test_nonexistent_package_is_distinguished_from_lookup_failure():
    store = DocStore.load()
    findings = check_hallucinations(
        "import fabricated_package_123",
        store,
        package_resolver=lambda name: False,
    )
    assert [(finding.category, finding.status) for finding in findings] == [("package", "hallucinated")]

    unknown = check_hallucinations(
        "import fabricated_package_123",
        store,
        package_resolver=lambda name: None,
    )
    assert unknown[0].status == "unknown"


def test_missing_api_in_partial_snapshot_is_not_claimed_hallucinated():
    store = DocStore.load()
    findings = check_hallucinations(
        "import pandas as pd\npd.made_up_api()",
        store,
        package_resolver=lambda name: True,
    )
    assert len(findings) == 1
    assert findings[0].status == "unverified"
    assert findings[0].category == "api_coverage"


def test_missing_api_in_complete_snapshot_is_a_definite_api_finding():
    doc = LibraryDoc(
        name="demo",
        kind="third-party",
        summary="fixture",
        keywords=(),
        signatures=("demo.run()",),
        modules=("demo",),
        apis=("demo.run",),
        coverage_complete=True,
    )
    store = DocStore({"demo": doc})
    findings = check_hallucinations(
        "import demo\ndemo.fake()",
        store,
        package_resolver=lambda name: True,
    )
    assert findings[0].category == "api"
    assert findings[0].status == "hallucinated"


def test_from_import_alias_is_normalized_to_documented_symbol():
    store = DocStore.load()
    findings = check_hallucinations(
        "from pandas import read_csv as load_table\nload_table('file.csv')",
        store,
        package_resolver=lambda name: True,
    )
    assert findings == []


def test_aliased_submodule_keeps_its_full_documented_path():
    doc = LibraryDoc(
        name="demo", kind="third-party", summary="fixture", keywords=(),
        signatures=("demo.sub.run()",), modules=("demo",),
        apis=("demo.sub.run",), coverage_complete=True,
    )
    store = DocStore({"demo": doc})
    for code in (
        "import demo.sub as sub\nsub.run()",
        "import demo.sub\ndemo.sub.run()",
    ):
        assert check_hallucinations(code, store, package_resolver=lambda _: True) == []
