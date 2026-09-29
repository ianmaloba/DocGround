"""Conservative package and API reference checks tied to documentation coverage."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from typing import Callable, Iterable

import requests

from docground.grounding.doc_store import DocStore, LibraryDoc

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
IMPORT_TO_PYPI_NAME = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
}
PackageResolver = Callable[[str], bool | None]


@dataclass(frozen=True)
class HallucinationFinding:
    category: str
    symbol: str
    status: str
    message: str


def pypi_resolver(timeout: float = 5.0) -> PackageResolver:
    """Return True/False for a definite PyPI result and None for a lookup failure."""
    def resolve(package: str) -> bool | None:
        try:
            response = requests.get(PYPI_JSON_URL.format(package=package), timeout=timeout)
        except requests.RequestException:
            return None
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        return None

    return resolve


def extract_imports(code: str) -> list[str]:
    tree = ast.parse(code)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return sorted(modules)


def check_hallucinations(
    code: str,
    store: DocStore,
    package_resolver: PackageResolver | None = None,
    known_local_modules: Iterable[str] = (),
) -> list[HallucinationFinding]:
    """Report nonexistent imports and API calls outside a declared complete snapshot.

    Missing entries in an incomplete documentation snapshot are advisory, not
    hallucination claims. Network failures from the package index are unknown.
    """
    tree = ast.parse(code)
    resolver = package_resolver or pypi_resolver()
    local_modules = set(known_local_modules)
    modules = _module_docs(store)
    aliases, imported_modules = _imports_and_aliases(tree)
    findings: list[HallucinationFinding] = []

    checked_distributions: dict[str, bool | None] = {}
    for module in sorted(imported_modules):
        if module in sys.stdlib_module_names or module in local_modules:
            continue
        doc = modules.get(module)
        if doc is not None:
            continue
        distribution = IMPORT_TO_PYPI_NAME.get(module, module)
        if distribution not in checked_distributions:
            try:
                checked_distributions[distribution] = resolver(distribution)
            except Exception:
                checked_distributions[distribution] = None
        exists = checked_distributions[distribution]
        if exists is False:
            findings.append(HallucinationFinding(
                "package", module, "hallucinated",
                f"Import {module!r} maps to distribution {distribution!r}, which returned PyPI 404.",
            ))
        elif exists is None:
            findings.append(HallucinationFinding(
                "package", module, "unknown",
                f"Could not verify whether distribution {distribution!r} exists.",
            ))

    for call in _called_names(tree):
        normalized = _normalize_call(call, aliases)
        if not normalized:
            continue
        doc = _doc_for_symbol(normalized, modules)
        if doc is None:
            continue
        if normalized in doc.apis:
            continue
        status = "hallucinated" if doc.coverage_complete else "unverified"
        category = "api" if doc.coverage_complete else "api_coverage"
        message = (
            f"Call {normalized!r} is outside the complete verified API snapshot."
            if doc.coverage_complete
            else f"Call {normalized!r} is not in this partial snapshot; existence is unknown."
        )
        findings.append(HallucinationFinding(category, normalized, status, message))
    return findings


def _module_docs(store: DocStore) -> dict[str, LibraryDoc]:
    result: dict[str, LibraryDoc] = {}
    for name in store.library_names():
        doc = store.get(name)
        if doc is None:
            continue
        for module in doc.modules or (name,):
            result[module] = doc
    return result


def _imports_and_aliases(tree: ast.AST) -> tuple[dict[str, str], set[str]]:
    aliases: dict[str, str] = {}
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                imported_modules.add(root)
                aliases[alias.asname or root] = alias.name if alias.asname else root
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            imported_modules.add(root)
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{node.module}.{alias.name}"
    return aliases, imported_modules


def _called_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            dotted = _dotted_name(node.func)
            if dotted:
                names.add(dotted)
    return names


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _normalize_call(name: str, aliases: dict[str, str]) -> str:
    head, separator, tail = name.partition(".")
    replacement = aliases.get(head, head)
    if not separator:
        return replacement
    return f"{replacement}.{tail}"


def _doc_for_symbol(name: str, modules: dict[str, LibraryDoc]) -> LibraryDoc | None:
    root = name.split(".")[0]
    return modules.get(root)
