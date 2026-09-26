"""AST-alapú őr: a resolver sosem olvashatja a válaszkulcsot (design `kg-construction.md` §5.7).

A `resolve()`-nak vakon kell működnie a splitteren és az OPEN100-on — ha
bármelyik `plantgraph.resolution` modul importálná a `SplitManifest`-et, az
`OccurrenceMap`-et máshonnan, vagy a splitter belső moduljait
(`benchmark.splitter`, `benchmark.rejoin`, `benchmark.strategies`) vagy az
`eval` csomagot, az visszanyitná a szivárgást, amit `localize()` és
`contract.py` lezárt (design §4). Ez a teszt nem a viselkedést, hanem magát a
forráskódot ellenőrzi: egyetlen tiltott import is elég ahhoz, hogy a design
ígérete hamis legyen. `localize.py` maga **definiálja** az `OccurrenceMap`-et
— ez nem import, ezért nem bukik el rajta.
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
    """Minden import-utasítás teljes elérési útja, és minden `from ... import y` importált neve.

    Csak import-utasításokat néz — egy modul saját osztálydefiníciója (mint az
    `OccurrenceMap` a `localize.py`-ban) sosem import, tehát sosem üti meg a
    tiltólistát. A `from plantgraph.benchmark import splitter` alak modul-nevet
    importál almodulként (nem osztályt) — ezért az összerakott
    "modul.almodul" utat is felvesszük, különben ez a forma megkerülné a tiltást.
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
