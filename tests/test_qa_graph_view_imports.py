"""AST-based guard: the QA retrieval view must never read the answer key (`qa-system.md` §16).

The occurrence graph is built from `localized_sheets` and the resolver's own
output only (`qa-system.md` §2.1, D8/D9) — never from `SplitManifest` or
`OccurrenceMap`, which is the gold side the question generator and the
scoring code use. This mirrors `tests/test_resolution_imports.py`'s approach
exactly, checked against the design's own banlist for this pair of modules
(§16, "Answer-key import ban").
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_QA_DIR = Path(__file__).resolve().parent.parent / "src" / "plantgraph" / "qa"
_CHECKED_FILES = (
    _QA_DIR / "graph_view.py",
    _QA_DIR / "serialize.py",
    _QA_DIR / "anchors.py",
    _QA_DIR / "routing.py",
    _QA_DIR / "sheet_selection.py",
    _QA_DIR / "context_budget.py",
    _QA_DIR / "unit_router.py",
    _QA_DIR / "strategies" / "hierarchical.py",
)
_BANNED_MODULES = (
    "plantgraph.qa.corpus",
    "plantgraph.qa.questions",
    "plantgraph.benchmark.splitter",
    "plantgraph.benchmark.rejoin",
    "plantgraph.eval",
)
_BANNED_NAMES = frozenset({"SplitManifest", "OccurrenceMap"})


def _imported_modules_and_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Every dotted import path, and every name from a `from ... import y` (see design §16).

    `from plantgraph.benchmark import splitter` imports a module as a
    submodule, not a class — so the joined "module.submodule" path is also
    recorded, otherwise this form would slip past the module banlist.
    """
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            for alias in node.names:
                names.add(alias.name)
                modules.add(f"{node.module}.{alias.name}")
    return modules, names


@pytest.mark.parametrize("path", _CHECKED_FILES, ids=lambda path: path.name)
def test_qa_graph_view_and_serialize_never_import_the_answer_key(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules, names = _imported_modules_and_names(tree)

    for banned in _BANNED_MODULES:
        matching = {
            module for module in modules if module == banned or module.startswith(f"{banned}.")
        }
        assert not matching, f"{path.name} imports banned module(s) {matching}"

    leaked_names = names & _BANNED_NAMES
    assert not leaked_names, f"{path.name} imports the answer key: {leaked_names}"
