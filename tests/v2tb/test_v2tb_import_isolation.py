"""V2T-B must leave V2T-A2 alone: importing it changes no E9 module, and no frozen path differs.

Two checks (ADR-0067): the import-isolation test, run in a fresh interpreter so no other test has
touched the modules, and gate G0f, the system-side path list against the E9 freeze commit.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from plantgraph.qa.exp0007.paths import check_paths, is_system_side

_REPO = Path(__file__).resolve().parents[2]
_E9_COMMIT_FILE = _REPO / "data" / "runs" / "exp0008" / "freeze" / "head"

#: Runs in a fresh interpreter: import every E9 module, record each module's namespace by object
#: identity, import every V2T-B module, record again, and print what changed.
_SCRIPT = textwrap.dedent(
    """
    import importlib, pkgutil, sys
    import plantgraph.qa as qa

    def import_all(prefix_filter):
        for info in pkgutil.walk_packages(qa.__path__, "plantgraph.qa."):
            # a `__main__` module is a command line, not a module to import
            if prefix_filter(info.name) and not info.name.endswith("__main__"):
                importlib.import_module(info.name)

    def is_b(name):
        return name.startswith("plantgraph.qa.v2tb")

    import_all(lambda name: not is_b(name))
    before = {n: {k: id(v) for k, v in vars(m).items()} for n, m in sys.modules.items()
              if n.startswith("plantgraph") and not is_b(n)}
    import_all(is_b)
    changed = []
    for name, old in before.items():
        if name in ("plantgraph", "plantgraph.qa"):
            continue  # a parent package gains the attribute `v2tb`; that is the import itself
        new = {k: id(v) for k, v in vars(sys.modules[name]).items()}
        if new != old:
            changed.append(name)
    print("CHECKED", len(before))
    print("CHANGED", sorted(changed))
    print("B_MODULES", sorted(n for n in sys.modules if is_b(n)))
    """
)


def test_importing_the_b_package_changes_no_e9_module() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", _SCRIPT],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO,
    )
    assert result.returncode == 0, result.stderr
    checked = next(line for line in result.stdout.splitlines() if line.startswith("CHECKED"))
    assert int(checked.split()[1]) > 100, checked  # the check looked at the whole E9 package
    changed_line = next(line for line in result.stdout.splitlines() if line.startswith("CHANGED"))
    assert changed_line == "CHANGED []", changed_line
    b_line = next(line for line in result.stdout.splitlines() if line.startswith("B_MODULES"))
    assert "plantgraph.qa.v2tb.scoring_b" in b_line  # the B modules really were imported


def test_no_b_file_is_on_the_system_side_list() -> None:
    assert not is_system_side("src/plantgraph/qa/v2tb/scoring_b.py")


def test_g0f_no_system_side_path_changed_since_the_e9_freeze() -> None:
    if not _E9_COMMIT_FILE.exists():
        pytest.skip("no E9 freeze commit recorded in this checkout")
    commit = _E9_COMMIT_FILE.read_text(encoding="utf-8").strip()
    try:
        assert check_paths(_REPO, commit) == []
    except RuntimeError as error:  # no such commit in a shallow clone
        pytest.skip(f"git cannot compare with the E9 commit here: {error}")
