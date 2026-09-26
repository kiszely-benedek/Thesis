"""AST-based guard: the resolver must never read the answer key (design `kg-construction.md` §5.7).

`resolve()` must stay blind to the splitter and to OPEN100 — if any
`plantgraph.resolution` module imported `SplitManifest`, `OccurrenceMap` from
elsewhere, or the splitter's internal modules (`benchmark.splitter`,
`benchmark.rejoin`, `benchmark.strategies`) or the `eval` package, that would
reopen the leak that `localize()` and `contract.py` sealed off (design §4). This
test checks the source code itself, not runtime behaviour: a single forbidden
import is enough to break the design's promise. `localize.py` itself
**defines** `OccurrenceMap` — that is not an import, so it does not trip this test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_RESOLUTION_DIR = Path(__file__).resolve().parent.parent / "src" / "plantgraph" / "resolution"
_BANNED_MODULES = (
    "plantgraph.benchmark.splitter",
    "plantgraph.benchmark.rejoin",
    "plantgraph.benchmark.strategies",
    "plantgraph.eval",
)
_BANNED_NAMES = frozenset({"SplitManifest", "OccurrenceMap"})


def _module_files() -> list[Path]:
    return sorted(_RESOLUTION_DIR.glob("*.py"))


def _imported_modules_and_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    """The full dotted path of every import statement, and every name from a `from ... import y`.

    Only looks at import statements — a module's own class definition (like
    `OccurrenceMap` in `localize.py`) is never an import, so it never trips the
    banlist. The form `from plantgraph.benchmark import splitter` imports a module
    name as a submodule (not a class) — so we also record the joined
    "module.submodule" path, otherwise this form would slip past the ban.
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


@pytest.mark.parametrize("path", _module_files(), ids=lambda path: path.name)
def test_resolution_module_never_imports_the_answer_key(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules, names = _imported_modules_and_names(tree)

    for banned in _BANNED_MODULES:
        matching = {
            module for module in modules if module == banned or module.startswith(f"{banned}.")
        }
        assert not matching, f"{path.name} imports banned module(s) {matching}"

    leaked_names = names & _BANNED_NAMES
    assert not leaked_names, f"{path.name} imports the answer key: {leaked_names}"
