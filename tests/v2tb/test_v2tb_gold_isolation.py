"""§10.6 (8): no strategy-facing B module imports the answer key, directly or through a B file.

The strategy-facing modules are the ones a model's run can reach: strategies, views, answer step,
registry, the agent's tool text and the readers of the view. The gold-side B modules (`store_b`,
`expressiveness_b`, `corpus_b`, `attempt_b`, `runner_b`, ...) may import gold; they must never be
imported by a strategy-facing one. A `TYPE_CHECKING` import is a type annotation only (nothing
runs), so it is not counted; `TYPE_CHECKING_ALLOWED` lists the ones a reviewer has accepted, and a
new one fails the test until it is reviewed and added.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_B_DIR = Path(__file__).resolve().parents[2] / "src" / "plantgraph" / "qa" / "v2tb"
_B_PREFIX = "plantgraph.qa.v2tb."

STRATEGY_FACING = (
    "strategies_b",
    "views_b",
    "answer_b",
    "registry_b",
    "plant_api_b",
    "item_graph_b",
    "canonical_b",
    "schema_text_b",
    "primer_b",
    "final_answer_b",
    "visible",
)
#: gold or gold-side modules a strategy-facing one may not import
_BANNED_PREFIXES = (
    "plantgraph.qa.corpus",
    "plantgraph.benchmark",
    "plantgraph.qa.questions",
    "plantgraph.qa.exp0009",
    "plantgraph.eval",
    "plantgraph.qa.harness.gold",
    "plantgraph.qa.harness.routing_gold",
    "plantgraph.qa.harness.family_meta",
    "plantgraph.qa.harness.need_gold",
    "plantgraph.resolution.localize",
    f"{_B_PREFIX}store_b",
    f"{_B_PREFIX}positions",
    f"{_B_PREFIX}expressiveness_b",
    f"{_B_PREFIX}corpus_b",
    f"{_B_PREFIX}attempt_b",
    f"{_B_PREFIX}fill_b",
    f"{_B_PREFIX}runner_b",
    f"{_B_PREFIX}load_b",
    f"{_B_PREFIX}shown_b",
)
_BANNED_NAMES = frozenset({"SplitManifest", "OccurrenceMap"})


def _runtime_imports(path: Path) -> tuple[set[str], set[str]]:
    """Dotted modules and imported names of a file, leaving out `if TYPE_CHECKING:` blocks."""
    return _imports_of(path.read_text(encoding="utf-8"))


def _imports_of(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    modules: set[str] = set()
    names: set[str] = set()
    pending: list[ast.AST] = [node for node in tree.body if not _is_type_checking_block(node)]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            for alias in node.names:
                names.add(alias.name)
                modules.add(f"{node.module}.{alias.name}")
        pending.extend(
            child for child in ast.iter_child_nodes(node) if not _is_type_checking_block(child)
        )
    return modules, names


def _is_type_checking_block(node: ast.AST) -> bool:
    return isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test)


def _b_files_reached(start: str) -> list[str]:
    """`start` and every v2tb module it imports, directly or through other v2tb modules."""
    reached: list[str] = []
    todo = [start]
    while todo:
        name = todo.pop()
        if name in reached:
            continue
        reached.append(name)
        modules, _ = _runtime_imports(_B_DIR / f"{name}.py")
        todo += [
            module.removeprefix(_B_PREFIX)
            for module in modules
            if module.startswith(_B_PREFIX)
            and (_B_DIR / f"{module.removeprefix(_B_PREFIX)}.py").is_file()
        ]
    return reached


@pytest.mark.parametrize("name", STRATEGY_FACING)
def test_a_strategy_facing_b_module_reaches_no_gold(name: str) -> None:
    for reached in _b_files_reached(name):
        modules, names = _runtime_imports(_B_DIR / f"{reached}.py")
        banned = sorted(module for module in modules if module.startswith(_BANNED_PREFIXES))
        assert not banned, f"{name} reaches {reached}, which imports {banned}"
        assert not names & _BANNED_NAMES, f"{name} reaches {reached}, which imports the answer key"


def test_the_strategy_facing_list_names_real_files() -> None:
    assert all((_B_DIR / f"{name}.py").is_file() for name in STRATEGY_FACING)


def test_the_scan_can_fail() -> None:
    """Source that imports `qa.corpus`, or the answer key's class, is caught by the same scan."""
    modules, names = _imports_of("from plantgraph.qa.corpus import OccurrenceMap\n")

    assert any(module.startswith(_BANNED_PREFIXES) for module in modules)
    assert names & _BANNED_NAMES


def test_the_scan_skips_a_type_checking_import() -> None:
    source = "if TYPE_CHECKING:\n    from plantgraph.benchmark.sheet_graph import SheetGraph\n"

    assert _imports_of(source) == (set(), set())


# ---- the TYPE_CHECKING allow-list (design §10.9 R17) ---------------------------------------------

#: (module file, imported module, imported name): the `TYPE_CHECKING` imports of a banned module
#: that were reviewed. `views_b` names `SheetGraph` as the type of the frozen constructor's own
#: parameter; no gold value reaches a strategy through an annotation.
TYPE_CHECKING_ALLOWED = {("views_b", "plantgraph.benchmark.sheet_graph", "SheetGraph")}


def _type_checking_imports(name: str, source: str) -> set[tuple[str, str, str]]:
    """Every `from X import Y` inside an `if TYPE_CHECKING:` block of a file, as (file, X, Y)."""
    found: set[tuple[str, str, str]] = set()
    for block in (n for n in ast.walk(ast.parse(source)) if _is_type_checking_block(n)):
        for node in ast.walk(block):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                found.update((name, node.module, alias.name) for alias in node.names)
    return found


def _banned(module: str, imported: str) -> bool:
    return module.startswith(_BANNED_PREFIXES) or imported in _BANNED_NAMES


def test_every_type_checking_import_of_a_banned_module_is_on_the_reviewed_list() -> None:
    found: set[tuple[str, str, str]] = set()
    for path in sorted(_B_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        found |= {t for t in _type_checking_imports(path.stem, source) if _banned(t[1], t[2])}

    assert found == TYPE_CHECKING_ALLOWED


def test_a_new_type_checking_import_of_gold_is_not_on_the_list() -> None:
    source = "if TYPE_CHECKING:" + chr(10) + "    from plantgraph.qa.corpus import CorpusArtifacts"

    found = {t for t in _type_checking_imports("views_b", source) if _banned(t[1], t[2])}

    assert found == {("views_b", "plantgraph.qa.corpus", "CorpusArtifacts")}
    assert not found <= TYPE_CHECKING_ALLOWED


def test_a_strategy_facing_module_that_imports_load_b_or_shown_b_is_caught() -> None:
    for gold_side in ("load_b", "shown_b"):
        modules, _names = _imports_of(f"from {_B_PREFIX}{gold_side} import anything")

        assert any(module.startswith(_BANNED_PREFIXES) for module in modules), gold_side
