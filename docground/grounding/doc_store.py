"""Load and query a versioned, hand-reviewed documentation snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DOC_STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "doc_store.json"
METADATA_KEY = "_meta"


@dataclass(frozen=True)
class LibraryDoc:
    """A small documentation record used for prompt grounding."""

    name: str
    kind: str
    summary: str
    keywords: tuple[str, ...]
    signatures: tuple[str, ...]
    distribution_name: str | None = None
    modules: tuple[str, ...] = ()
    apis: tuple[str, ...] = ()
    coverage_complete: bool = False
    source_url: str | None = None
    source_urls: tuple[str, ...] = ()
    source_version: str | None = None
    source_checked_at: str | None = None

    def as_prompt_block(self) -> str:
        lines = [f"## {self.name} ({self.kind}): {self.summary}"]
        if self.source_version or self.source_checked_at:
            source_state = ", ".join(
                value for value in (self.source_version, self.source_checked_at) if value
            )
            lines.append(f"Source checked: {source_state}")
        sources = self.source_urls or ((self.source_url,) if self.source_url else ())
        lines.extend(f"Official reference: {source}" for source in sources)
        lines.extend(f"- {signature}" for signature in self.signatures)
        return "\n".join(lines)


class DocStore:
    """An in-memory view of a documentation snapshot."""

    def __init__(
        self,
        docs: dict[str, LibraryDoc],
        meta: dict[str, Any] | None = None,
        snapshot_sha256: str | None = None,
    ) -> None:
        self._docs = dict(docs)
        self._meta = dict(meta or {})
        self.snapshot_sha256 = snapshot_sha256

    @classmethod
    def load(cls, path: str | Path | None = None) -> "DocStore":
        source = Path(path) if path is not None else DEFAULT_DOC_STORE_PATH
        raw_bytes = source.read_bytes()
        try:
            raw = json.loads(raw_bytes)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid documentation snapshot JSON: {source}") from error
        if not isinstance(raw, dict):
            raise ValueError("Documentation snapshot root must be a JSON object")

        meta = raw.get(METADATA_KEY, {})
        if not isinstance(meta, dict):
            raise ValueError(f"{METADATA_KEY} must be a JSON object")
        docs: dict[str, LibraryDoc] = {}
        for name, entry in raw.items():
            if name.startswith("_"):
                continue
            if not isinstance(entry, dict):
                raise ValueError(f"Documentation entry {name!r} must be a JSON object")
            docs[name] = LibraryDoc(
                name=name,
                kind=_string(entry, "kind", "unknown"),
                summary=_string(entry, "summary", ""),
                keywords=_string_tuple(entry, "keywords"),
                signatures=_string_tuple(entry, "signatures"),
                distribution_name=_optional_string(entry, "distribution_name"),
                modules=_string_tuple(entry, "modules"),
                apis=_string_tuple(entry, "apis"),
                coverage_complete=_boolean(entry, "coverage_complete", False),
                source_url=_optional_string(entry, "source_url"),
                source_urls=_string_tuple(entry, "source_urls"),
                source_version=_optional_string(entry, "source_version"),
                source_checked_at=_optional_string(entry, "source_checked_at"),
            )
        expected_count = meta.get("library_count")
        if isinstance(expected_count, int) and expected_count != len(docs):
            raise ValueError(
                f"Snapshot library_count says {expected_count}, found {len(docs)} entries"
            )
        return cls(
            docs,
            meta=meta,
            snapshot_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        )

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._meta)

    @property
    def snapshot_date(self) -> str | None:
        value = self._meta.get("snapshot_date")
        return value if isinstance(value, str) else None

    def get(self, name: str) -> LibraryDoc | None:
        return self._docs.get(name)

    def library_names(self) -> list[str]:
        return sorted(self._docs)

    def keywords_for(self, name: str) -> tuple[str, ...]:
        doc = self.get(name)
        return doc.keywords if doc else ()

    def __len__(self) -> int:
        return len(self._docs)

    def __contains__(self, name: object) -> bool:
        return name in self._docs


def _string(entry: dict[str, Any], key: str, default: str) -> str:
    value = entry.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"Documentation field {key!r} must be a string")
    return value


def _string_tuple(entry: dict[str, Any], key: str) -> tuple[str, ...]:
    value = entry.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Documentation field {key!r} must be a list of strings")
    return tuple(value)


def _optional_string(entry: dict[str, Any], key: str) -> str | None:
    value = entry.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Documentation field {key!r} must be a string or null")
    return value


def _boolean(entry: dict[str, Any], key: str, default: bool) -> bool:
    value = entry.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"Documentation field {key!r} must be a boolean")
    return value
