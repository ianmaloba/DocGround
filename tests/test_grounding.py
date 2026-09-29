from docground.grounding.doc_store import DocStore
from docground.grounding.retriever import mentions, retrieve_from_store
from docground.grounding.wrapper import ground


def test_default_snapshot_is_hashed_and_metadata_is_not_a_library():
    store = DocStore.load()
    assert len(store) == 8
    assert "_meta" not in store.library_names()
    assert store.snapshot_date == "2026-09-29"
    assert len(store.snapshot_sha256 or "") == 64


def test_retrieval_matches_library_names_and_registered_keywords():
    store = DocStore.load()
    assert retrieve_from_store("Read a CSV into a dataframe", store) == ["pandas"]
    assert retrieve_from_store("Use pandas and requests", store) == ["pandas", "requests"]
    assert retrieve_from_store("Use pandas", store, use_keywords=False) == ["pandas"]


def test_snapshot_includes_top_level_pandas_merge_api():
    doc = DocStore.load().get("pandas")
    assert doc is not None
    assert "pandas.merge" in doc.apis
    assert any(url.endswith("/pandas.merge.html") for url in doc.source_urls)
    assert any(signature.startswith("pandas.merge(") for signature in doc.signatures)


def test_json_data_format_does_not_retrieve_stdlib_module_docs():
    store = DocStore.load()
    assert retrieve_from_store("Read a JSON response with requests", store) == ["requests"]
    assert retrieve_from_store("Decode it with json.loads", store) == ["json"]
    assert retrieve_from_store("Use the json module to serialize it", store) == ["json"]


def test_whole_word_match_avoids_accidental_substring_matches():
    assert mentions("use pandas", "pandas")
    assert not mentions("use pandasx", "pandas")


def test_grounding_preserves_original_task_and_exposes_snapshot():
    task = "Read a CSV with pandas and show the first rows."
    result = ground(task, store=DocStore.load())
    assert task in result.text
    assert "pandas.read_csv" in result.text
    assert result.libraries == ("pandas",)
    assert result.snapshot_sha256
    assert "official Python" in result.snapshot_metadata["source"]
    assert "pandas.DataFrame.groupby" in result.text
    assert "pandas.pydata.org" in result.text
    assert "Source checked: 3.0.6, 2026-09-29" in result.text


def test_no_retrieval_degrades_with_explicit_uncertainty_note():
    result = ground("Implement a custom numeric routine.", store=DocStore.load())
    assert result.libraries == ()
    assert "No documentation was retrieved" in result.text
