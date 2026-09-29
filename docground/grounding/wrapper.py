"""Prepare a visible grounding proposal without changing the user's task."""

from __future__ import annotations

from dataclasses import dataclass

from docground.grounding.doc_store import DocStore, LibraryDoc
from docground.grounding.retriever import retrieve_from_store

DOC_HEADER = "Reference API documentation from the selected snapshot:"
NO_DOCS_NOTE = (
    "No documentation was retrieved from this snapshot. Do not treat this as proof "
    "that an API exists; prefer APIs you can verify from another named source."
)
INSTRUCTION_FOOTER = (
    "Use the documented APIs where they fit the task. Do not invent package or API "
    "names. If the documentation is insufficient, state the uncertainty."
)


@dataclass(frozen=True)
class GroundedPrompt:
    original_task: str
    libraries: tuple[str, ...]
    documents: tuple[LibraryDoc, ...]
    text: str
    snapshot_date: str | None
    snapshot_sha256: str | None
    snapshot_metadata: dict[str, object]


def build_documentation_block(libraries: list[str], store: DocStore) -> str:
    documents = [store.get(name) for name in libraries]
    blocks = [doc.as_prompt_block() for doc in documents if doc is not None]
    if not blocks:
        return NO_DOCS_NOTE
    snapshot = store.snapshot_date or "date not recorded"
    return f"{DOC_HEADER}\nSnapshot date: {snapshot}\n\n" + "\n\n".join(blocks)


def ground(
    task: str,
    store: DocStore | None = None,
    use_keywords: bool = True,
) -> GroundedPrompt:
    selected_store = DocStore.load() if store is None else store
    libraries = retrieve_from_store(task, selected_store, use_keywords=use_keywords)
    documents = tuple(
        doc for name in libraries if (doc := selected_store.get(name)) is not None
    )
    text = "\n\n".join(
        (
            f"ORIGINAL TASK (preserved verbatim):\n{task.strip()}",
            build_documentation_block(libraries, selected_store),
            INSTRUCTION_FOOTER,
        )
    )
    return GroundedPrompt(
        original_task=task,
        libraries=tuple(libraries),
        documents=documents,
        text=text,
        snapshot_date=selected_store.snapshot_date,
        snapshot_sha256=selected_store.snapshot_sha256,
        snapshot_metadata=selected_store.meta,
    )


def build_grounded_prompt(
    task: str,
    store: DocStore | None = None,
    use_keywords: bool = True,
) -> str:
    return ground(task, store=store, use_keywords=use_keywords).text
