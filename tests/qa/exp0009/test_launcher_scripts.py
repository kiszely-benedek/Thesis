"""The shell side of T13c: what can be checked without running a stage (B1, B7, F6, F2, F3, F7)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "data" / "runs" / "exp0009"
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def _text(*parts: str) -> str:
    return EXP.joinpath(*parts).read_text(encoding="utf-8")


def _sh(script: str, tmp: Path, **env: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a POSIX sh at the repo root with the launcher's lib.sh sourced."""
    python = sys.executable.replace("\\", "/")
    base = {**os.environ, "E10_ROOT": tmp.as_posix(), "E10_PYTHON": python}
    return subprocess.run(  # noqa: S603
        ["sh", "-c", script],
        cwd=REPO,
        env={**base, **env},
        capture_output=True,
        text=True,
        check=False,
    )


# ---- B1, B7 -------------------------------------------------------------------------------------


def test_the_judge_is_called_with_the_stage_the_cli_accepts() -> None:
    text = _text("stages", "p1d.sh")
    assert "--stage audit " in text and "audit$aj_sys" not in text  # B1
    assert "exp0009.audit_judge" in text and "exp0009.audit_select" in text  # B2, F9


@needs_sh
def test_launch_refuses_a_database_other_than_neo4j_at_the_start(tmp_path: Path) -> None:
    result = _sh("sh data/runs/exp0009/launch.sh", tmp_path, NEO4J_DATABASE="ds-someone-else",
                 E10_NEO4J_HOME=tmp_path.as_posix())  # fmt: skip
    assert result.returncode == 2
    assert "ds-someone-else" in result.stderr and "NEO4J_DATABASE" in result.stderr


def test_launch_pins_the_database_name_before_it_executes_run_all() -> None:
    text = _text("launch.sh")
    exported, started = text.index("export NEO4J_DATABASE=neo4j"), text.index("exec sh ")
    assert exported < started


# ---- F6 -----------------------------------------------------------------------------------------


@needs_sh
def test_a_stop_inside_a_redirected_block_still_reaches_the_launcher_log(tmp_path: Path) -> None:
    script = f""". data/runs/exp0009/lib.sh
mkdir -p "$STATE"; exec 4>&1; LAUNCHER_FD4=yes; CUR_STAGE=PX
( try false > "{tmp_path.as_posix()}/step.log" 2>&1 )
"""
    result = _sh(script, tmp_path)
    assert result.returncode == 10
    assert "PX STOP [infrastructure]" in result.stdout  # on the launcher's own output
    assert "STOP" not in (tmp_path / "step.log").read_text(encoding="utf-8")  # not buried there
    assert "[infrastructure]" in (tmp_path / "state" / "STOPPED").read_text(encoding="utf-8")


# ---- F2, F3, F7 ---------------------------------------------------------------------------------


@needs_sh
def test_a_plant_is_loaded_only_while_a_cypher_run_or_its_replay_is_pending(tmp_path: Path) -> None:
    script = f""". data/runs/exp0009/lib.sh; . data/runs/exp0009/lib_runs.sh
SD="{tmp_path.as_posix()}/step"; mkdir -p "$SD/runs" "$SD/replays"
needs_database R1 yes && echo "R1 no run: load"
: > "$SD/runs/R1.complete"
needs_database R1 yes && echo "R1 no replay: load"
needs_database R1 no || echo "R1 not replayed here: skip"
: > "$SD/replays/INF-R1.replayed"
needs_database R1 yes || echo "R1 all done: skip"
"""
    out = _sh(script, tmp_path).stdout.splitlines()
    assert out == [
        "R1 no run: load",
        "R1 no replay: load",
        "R1 not replayed here: skip",
        "R1 all done: skip",
    ]


def test_the_resumable_stages_load_through_the_pending_check() -> None:
    for name in ("p1b.sh", "p1c.sh", "p1g.sh"):
        lines = _text("stages", name).splitlines()
        assert any("needs_database" in line for line in lines)
        assert not [ln for ln in lines if ln.strip() in ("neo4j_load_a", "neo4j_load_b")]


def test_require_frozen_also_asks_git_about_files_the_hash_list_does_not_know() -> None:
    text = _text("lib_runs.sh")
    assert "git status --porcelain -- $FROZEN_PATHS" in text
    assert 'git diff --name-only "$(cat "$PREREG/E10.commit")" HEAD' in text


def test_a_money_shortfall_in_p1g_skips_it_and_the_launcher_goes_on() -> None:
    p1g, lib = _text("stages", "p1g.sh"), _text("lib_runs.sh")
    assert "SOFT_MONEY=yes" in p1g and "stop_run topup" not in p1g
    assert "SHORTFALL" in lib and "exit 0" in lib  # money_stop ends only the stage
    assert 'money_stop "$pr_id reached its spend cap' in lib  # a run's own cap too
