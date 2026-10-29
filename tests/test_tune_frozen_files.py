"""The final-V freeze check ignores benchmark-side changes and catches any V2T system change."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TUNE_LIB = ROOT / "data" / "runs" / "exp0007" / "tune_lib.sh"


def _sh(
    script: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _frozen_files() -> list[str]:
    out = _sh(f". '{TUNE_LIB.as_posix()}'; echo $V2T_FROZEN_FILES", ROOT)
    assert out.returncode == 0, out.stderr
    return out.stdout.split()


def test_every_listed_path_exists_and_none_is_benchmark_side() -> None:
    paths = _frozen_files()
    assert paths, "expected a non-empty V2T_FROZEN_FILES list"
    missing = [p for p in paths if not (ROOT / p).exists()]
    assert not missing, f"expected every listed path to exist, missing: {missing}"
    benchmark_side = ("qa/questions", "harness/gold.py", "harness/canonical_programs.py")
    assert not [p for p in paths if any(b in p for b in benchmark_side)]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for command in (
        "git init -q",
        "git config user.email t@t",
        "git config user.name t",
        "mkdir system gold inputs",
        "echo 1 > system/a.py; echo 1 > gold/g.py; echo 1 > inputs/p.json",
        "git add -A; git commit -q -m base",
    ):
        assert _sh(command, tmp_path).returncode == 0
    return tmp_path


def _changed(repo: Path) -> bool:
    script = f". '{TUNE_LIB.as_posix()}'; v2t_system_changed_since HEAD"
    env_script = f"V2T_FROZEN_FILES=system IN=inputs; {script}"
    return _sh(env_script, repo).returncode == 0


def test_a_gold_side_change_does_not_count(repo: Path) -> None:
    (repo / "gold" / "g.py").write_text("2\n")
    assert not _changed(repo)


def test_a_system_change_counts(repo: Path) -> None:
    (repo / "system" / "a.py").write_text("2\n")
    assert _changed(repo)


def test_an_inputs_change_counts(repo: Path) -> None:
    (repo / "inputs" / "p.json").write_text("2\n")
    assert _changed(repo)
