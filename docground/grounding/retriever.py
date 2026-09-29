"""Deterministic whole-word retrieval for the curated documentation snapshot."""

from __future__ import annotations

import re
from typing import Iterable

from docground.grounding.doc_store import DocStore


def mentions(text: str, term: str) -> bool:
    if not term:
        return False
    pattern = r"(?<![\w.])" + re.escape(term) + r"(?![\w])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def retrieve(
    prompt: str,
    library_names: Iterable[str],
    keywords: dict[str, Iterable[str]] | None = None,
) -> list[str]:
    terms_by_name = keywords or {}
    selected = []
    for name in library_names:
        if name == "json":
            # JSON is often mentioned as a data format or Response.json() method;
            # retrieve stdlib docs only when the module itself is requested.
            module_mentioned = re.search(
                r"\b(?:import\s+json|from\s+json\s+import|json\s+module|"
                r"json\s*\.\s*(?:load|loads|dump|dumps))\b",
                prompt,
                flags=re.IGNORECASE,
            ) is not None
            if module_mentioned:
                selected.append(name)
            continue
        if any(mentions(prompt, term) for term in [name, *terms_by_name.get(name, ())]):
            selected.append(name)
    return sorted(selected)


def retrieve_from_store(
    prompt: str,
    store: DocStore,
    use_keywords: bool = True,
) -> list[str]:
    names = store.library_names()
    keywords = (
        {name: store.keywords_for(name) for name in names} if use_keywords else None
    )
    return retrieve(prompt, names, keywords)
