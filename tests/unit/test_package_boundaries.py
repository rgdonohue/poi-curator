from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOTS = {
    "ingestion": Path("packages/ingestion/poi_curator_ingestion"),
    "enrichment": Path("packages/enrichment/poi_curator_enrichment"),
    "scoring": Path("packages/scoring/poi_curator_scoring"),
    "editorial": Path("packages/editorial/poi_curator_editorial"),
}
PACKAGE_PREFIXES = {
    "ingestion": "poi_curator_ingestion",
    "enrichment": "poi_curator_enrichment",
    "scoring": "poi_curator_scoring",
    "editorial": "poi_curator_editorial",
}


def test_runtime_packages_do_not_cross_import_each_other() -> None:
    violations: list[str] = []
    for source_name, root in PACKAGE_ROOTS.items():
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for imported in imported_module_names(node):
                    imported_package = package_for_module(imported)
                    if imported_package is None or imported_package == source_name:
                        continue
                    violations.append(f"{path}:{getattr(node, 'lineno', 0)} imports {imported}")

    assert violations == []


def imported_module_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module] if node.module is not None else []
    return []


def package_for_module(module_name: str) -> str | None:
    for package, prefix in PACKAGE_PREFIXES.items():
        if module_name == prefix or module_name.startswith(f"{prefix}."):
            return package
    return None
