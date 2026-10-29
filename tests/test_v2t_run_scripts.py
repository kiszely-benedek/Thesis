"""R4 / R5 scripts for V2T-A: the E7 freeze check, the refusals and each arm's harness command.

Everything runs offline: the freeze tests use a throw-away git repository, the refusal tests stop
before any model or database is touched, and the arm tests replace the harness with a script that
only records its command line.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from plantgraph.qa.exp0007.caps import CapEntry, CapFile, sha256_of, write_cap_file

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs" / "exp0007"


def _sh(
    script: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _env(**extra: str) -> dict[str, str]:
    return {**os.environ, **extra}


def _libs() -> str:
    """Shell text that sources the three helper files the run scripts source."""
    return " ".join(
        f". '{(RUNS / n).as_posix()}';" for n in ("lib.sh", "tune_lib.sh", "v2t_lib.sh")
    )


# ---- the freeze check, in a throw-away repository -------------------------------------------


@pytest.fixture
def frozen(tmp_path: Path) -> Path:
    """A repo whose `system/` is the V2T system and `exp/inputs/` its inputs, frozen at E7."""
    steps = (
        "git init -q",
        "git config user.email t@t",
        "git config user.name t",
        "mkdir -p system exp/inputs data",
        "echo 1 > system/a.py; echo 1 > exp/inputs/p.json; echo 1 > exp/inputs/listing_E7.json",
        "echo 1 > data/q.jsonl",
        "git add -A; git commit -q -m base",
    )
    for step in steps:
        assert _sh(step, tmp_path).returncode == 0, step
    write_e7 = (
        f"{_libs()} git rev-parse HEAD > exp/E7.commit; echo V2T-A > exp/E7.system; "
        "{ sha256sum exp/E7.commit exp/E7.system exp/inputs/* data/q.jsonl; "
        "v2t_system_hashes; } > exp/E7.sha256"
    )
    done = _sh(write_e7, tmp_path, _env(E7_ROOT="exp", V2T_FROZEN_FILES="system"))
    assert done.returncode == 0, done.stderr
    return tmp_path


def _check(repo: Path) -> subprocess.CompletedProcess[str]:
    env = _env(E7_ROOT="exp", V2T_FROZEN_FILES="system")
    return _sh(f"{_libs()} require_v2t_freeze", repo, env)


def test_the_hashes_cover_every_tracked_system_file(frozen: Path) -> None:
    hashes = (frozen / "exp" / "E7.sha256").read_text()

    assert "system/a.py" in hashes and "exp/inputs/p.json" in hashes


def test_the_freeze_holds_while_nothing_of_the_system_changes(frozen: Path) -> None:
    assert _check(frozen).returncode == 0
    # the user commits the generated data after E7: the commit moves on, the system does not
    commit = "echo x > data/questions.jsonl; git add -A; git commit -q -m data"
    assert _sh(commit, frozen).returncode == 0
    done = _check(frozen)
    assert done.returncode == 0 and "frozen system: V2T-A" in done.stdout


def test_a_changed_system_file_breaks_the_freeze_committed_or_not(frozen: Path) -> None:
    (frozen / "system" / "a.py").write_text("2\n")
    assert "differs from E7" in _check(frozen).stderr
    assert _sh("git add -A; git commit -q -m change", frozen).returncode == 0
    assert _check(frozen).returncode == 1


def test_a_new_file_in_a_frozen_path_breaks_the_freeze(frozen: Path) -> None:
    (frozen / "system" / "b.py").write_text("new\n")

    assert "differs from E7" in _check(frozen).stderr


def test_a_changed_input_breaks_the_freeze_but_the_listing_is_judged_by_its_hash(
    frozen: Path,
) -> None:
    listing = frozen / "exp" / "inputs" / "listing_E7.json"
    listing.write_bytes(b"{}\n")  # bytes: write_text would turn "\n" into "\r\n" on Windows
    # not "differs from E7" (the listing is excluded from the git check): only its hash counts
    assert "E7.sha256 changed" in _check(frozen).stderr
    listing.write_bytes(b"1\n")
    assert _check(frozen).returncode == 0
    (frozen / "exp" / "inputs" / "p.json").write_text("2\n")
    assert "differs from E7" in _check(frozen).stderr


def test_a_changed_question_file_breaks_the_freeze(frozen: Path) -> None:
    (frozen / "data" / "q.jsonl").write_bytes(b"0\n")

    done = _check(frozen)
    assert done.returncode == 1 and "E7.sha256 changed" in done.stderr


def test_a_freeze_of_another_system_is_refused(frozen: Path) -> None:
    (frozen / "exp" / "E7.system").write_text("F1\n")

    assert "E7 froze 'F1'" in _check(frozen).stderr


# ---- refusals of the scripts, before anything is touched ------------------------------------


def _script(name: str, *args: str, root: Path) -> subprocess.CompletedProcess[str]:
    return _sh(f"sh data/runs/exp0007/{name} {' '.join(args)}", ROOT, _env(E7_ROOT=str(root)))


@pytest.mark.parametrize("name", ["run_ladder.sh", "run_sealed.sh", "make_test_set.sh"])
def test_the_run_scripts_need_the_freeze_file(name: str, tmp_path: Path) -> None:
    done = _script(name, root=tmp_path)

    assert done.returncode == 1 and "no E7 freeze file" in done.stderr


def test_run_sealed_accepts_the_baseline_flag_but_still_needs_the_freeze(tmp_path: Path) -> None:
    done = _script("run_sealed.sh", "--with-f1-baseline", root=tmp_path)

    assert "unknown option" not in done.stderr and "no E7 freeze file" in done.stderr
    assert "unknown option --bogus" in _script("run_sealed.sh", "--bogus", root=tmp_path).stderr


def test_make_set_names_the_system_it_freezes_and_never_overwrites(tmp_path: Path) -> None:
    assert "pass --system-label V2T-A" in _script("make_set.sh", root=tmp_path).stderr
    other = _script("make_set.sh", "--system-label", "F1", root=tmp_path)
    assert "pass --system-label V2T-A" in other.stderr and "found 'F1'" in other.stderr
    (tmp_path / "E7.sha256").write_text("x\n")
    assert (
        "never overwrite" in _script("make_set.sh", "--system-label", "V2T-A", root=tmp_path).stderr
    )


def test_make_set_needs_the_finished_validation_step(tmp_path: Path) -> None:
    done = _script("make_set.sh", "--system-label", "V2T-A", root=tmp_path)

    assert "tune/final/DONE is missing" in done.stderr


def test_make_test_set_never_overwrites_t7(tmp_path: Path) -> None:
    (tmp_path / "T7.sha256").write_text("x\n")

    assert "T7.sha256 exists" in _script("make_test_set.sh", root=tmp_path).stderr


# ---- the harness command of each arm ---------------------------------------------------------


FAKE_HARNESS = """#!/bin/sh
# records its command line and writes one healthy answer row where the run directory is expected
echo "$@" >> "$FAKE_LOG"
run_id=; runs_root=
while [ $# -gt 0 ]; do
  case $1 in --run-id) run_id=$2 ;; --runs-root) runs_root=$2 ;; esac
  shift
done
mkdir -p "$runs_root/$run_id"
echo '{"outcome": "ANSWERED"}' > "$runs_root/$run_id/answers.jsonl"
"""


def _cap_file(path: Path, run_id: str) -> str:
    entry = CapEntry(
        run_id=run_id, tier="cyp", n_questions=10, v1_cost_per_question_usd=0.001, correction=1.0,
        cost_per_question_usd=0.001, cap_usd=0.25, basis="test",
    )  # fmt: skip
    write_cap_file(path, CapFile(stage="test", entries=[entry]))
    return sha256_of(path)


def _run_arm(tmp_path: Path, arm: str) -> str:
    """Run `v2t_run` for one arm against the recording harness; return the recorded command line."""
    fake = tmp_path / "fake_python"
    fake.write_text(FAKE_HARNESS)
    log = tmp_path / "log.txt"
    digest = _cap_file(tmp_path / "caps.json", "R-1")
    script = (
        f"{_libs()} P='sh {fake.as_posix()}'; S='{tmp_path.as_posix()}/s'; mkdir -p $S/logs; "
        f"CAP_FILE='{tmp_path.as_posix()}/caps.json'; CAP_SHA={digest}; EXPERIMENT=EXP-TEST; "
        "CYP_CORPORA=/cyp; AG_CORPORA=/ag; QROOT=/q; CACHE=/cache.sqlite; "
        f"v2t_run {arm} R-1 H100g2 full 120"
    )
    done = _sh(script, ROOT, _env(FAKE_LOG=str(log)))
    assert done.returncode == 0, done.stderr + done.stdout
    return log.read_text()


#: arm -> (strategy, params file, pin file, corpora root the arm reads)
ARMS = {
    "CYP-A": ("cypher_rag_lines", "params_cypher_v2t_a.json", "pin_cypher_luna_low.json", "/cyp"),
    "AG": ("graph_agent_lines", "params_agent_v2t.json", "pin_agent_luna_final_high.json", "/ag"),
    "F1-CYP": ("cypher_rag_plant", "params_cypher_plant.json", "pin_cypher_luna_low.json", "/cyp"),
    "F1-AG": (
        "graph_agent_low_steps",
        "params_agent_low.json",
        "pin_agent_luna_final_high.json",
        "/ag",
    ),
}


@pytest.mark.parametrize("arm", sorted(ARMS))
def test_each_arm_runs_its_strategy_params_pin_and_120_s_deadline(tmp_path: Path, arm: str) -> None:
    strategy, params, pin, corpora = ARMS[arm]
    command = _run_arm(tmp_path, arm)

    assert f"--strategy {strategy} " in command
    assert f"/inputs/{params} " in command and f"/inputs/{pin}" in command
    assert f"--corpora-root {corpora} " in command
    assert "--corpus H100g2:test" in command and "--question-deadline-s 120" in command
    assert "--max-spend-usd 0.25" in command and "--cost-per-question-usd 0.001" in command
    assert "--allow-paid-calls" in command and "--questions-root /q " in command


def test_a_full_run_that_hits_its_cap_stops_the_script(tmp_path: Path) -> None:
    done = _sh(f"{_libs()} S={tmp_path.as_posix()}; finish x 3 full", ROOT)

    assert done.returncode == 1 and "reached its spend cap" in done.stderr


def test_setting_a_is_what_the_scripts_ask_python_for() -> None:
    done = _sh(f"{_libs()} setting_a_deadline", ROOT)

    assert done.returncode == 0 and done.stdout.strip() == "120"


def test_the_f1_freeze_helper_is_gone_from_the_scripts() -> None:
    assert "require_freeze()" not in (RUNS / "lib.sh").read_text()
    for name in ("run_ladder.sh", "run_sealed.sh", "make_test_set.sh", "make_set.sh"):
        text = (RUNS / name).read_text().replace("require_v2t_freeze", "")
        assert "require_freeze" not in text
