"""`run_e2e.sh` and `e2e_lib.sh`: refusals, the E8 and pre-registration checks, dry-run commands.

All offline. The refusals stop before anything is touched; the freeze checks run in a throw-away git
repository; the command tests replace python with a script that only records its command line.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "runs"
E2E = RUNS / "exp0004"


def _sh(
    script: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def _libs() -> str:
    """Shell text that sources the helper files `run_e2e.sh` sources."""
    names = [RUNS / "exp0007" / n for n in ("lib.sh", "tune_lib.sh", "v2t_lib.sh")]
    return " ".join(f". '{p.as_posix()}';" for p in [*names, E2E / "e2e_lib.sh"])


def _script(*args: str) -> subprocess.CompletedProcess[str]:
    return _sh(f"sh data/runs/exp0004/run_e2e.sh {' '.join(args)}", ROOT, dict(os.environ))


# ---- refusals before anything is touched --------------------------------------------------------


def test_an_unknown_arm_or_mode_is_refused() -> None:
    assert "unknown arm 'd1'" in _script("dry", "d1").stderr
    assert "usage:" in _script("fly", "d0").stderr
    assert "usage:" in _script().stderr


def test_paid_mode_refuses_without_the_flag_and_without_a_cap() -> None:
    no_flag = _script("paid", "d0", "--max-spend-usd", "0.1")
    no_cap = _script("paid", "d0", "--allow-paid-calls")

    assert no_flag.returncode == 1 and "pass --allow-paid-calls" in no_flag.stderr
    assert no_cap.returncode == 1 and "--max-spend-usd X is required" in no_cap.stderr


def test_dry_mode_takes_no_paid_option() -> None:
    done = _script("dry", "d0", "--allow-paid-calls")

    assert done.returncode == 1 and "dry mode takes no option" in done.stderr
    assert "unknown option --bogus" in _script("dry", "d0", "--bogus").stderr


# ---- the E8 freeze and the pre-registration, in a throw-away repository -------------------------


@pytest.fixture
def frozen(tmp_path: Path) -> Path:
    """A repo whose `system/` is the V2T system, `exp/inputs/` its inputs and `e/` the E8 record."""
    steps = (
        "git init -q", "git config user.email t@t", "git config user.name t",
        "mkdir -p system exp/inputs e/prereg", "echo 1 > system/a.py; echo 1 > exp/inputs/p.json",
        "echo 1 > e/prereg/PREREG.md; echo V2T-A > e/E8.system",
        "git add -A; git commit -q -m base",
        "git rev-parse HEAD > e/E8.commit",
        "sha256sum system/a.py exp/inputs/p.json e/E8.system > e/E8.sha256",
        "sha256sum e/prereg/PREREG.md > e/prereg/PREREG.sha256",
        "git add -A; git commit -q -m freeze",
    )  # fmt: skip
    for step in steps:
        assert _sh(step, tmp_path).returncode == 0, step
    return tmp_path


def _call(repo: Path, function: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "E7_ROOT": "exp", "V2T_FROZEN_FILES": "system"}
    return _sh(f"{_libs()} E=e; {function}", repo, env)


def test_the_e8_freeze_holds_on_an_unchanged_system(frozen: Path) -> None:
    done = _call(frozen, "require_e8_freeze")

    assert done.returncode == 0 and "frozen system: V2T-A at E8" in done.stdout


def test_a_system_file_changed_after_e8_breaks_the_freeze_committed_or_not(frozen: Path) -> None:
    (frozen / "system" / "a.py").write_text("2\n")
    assert "differs from E8" in _call(frozen, "require_e8_freeze").stderr
    assert _sh("git add -A; git commit -q -m change", frozen).returncode == 0
    assert _call(frozen, "require_e8_freeze").returncode == 1


def test_a_new_file_in_a_frozen_path_breaks_the_freeze(frozen: Path) -> None:
    (frozen / "system" / "b.py").write_text("new\n")

    assert "differs from E8" in _call(frozen, "require_e8_freeze").stderr


def test_a_changed_hashed_file_breaks_the_freeze(frozen: Path) -> None:
    (frozen / "e" / "E8.system").write_text("F1\n")

    assert "E8 froze 'F1'" in _call(frozen, "require_e8_freeze").stderr


def test_a_missing_e8_record_is_refused(frozen: Path) -> None:
    (frozen / "e" / "E8.sha256").unlink()

    assert "no E8 freeze file" in _call(frozen, "require_e8_freeze").stderr


def test_the_preregistration_must_hold_and_be_committed(frozen: Path) -> None:
    assert _call(frozen, "require_prereg_holds").returncode == 0
    (frozen / "e" / "prereg" / "PREREG.md").write_text("2\n")
    assert "a pre-registered file changed" in _call(frozen, "require_prereg_holds").stderr


def test_the_real_repository_passes_both_checks() -> None:
    env = {**os.environ}
    done = _sh(f"{_libs()} E=data/runs/exp0004; require_e8_freeze; require_prereg_holds", ROOT, env)

    assert done.returncode == 0, done.stderr


# ---- the commands of the dry mode (python replaced by a recorder) -------------------------------

FAKE_PYTHON = """#!/bin/sh
echo "$@" >> "$FAKE_LOG"
"""


def _recorder(fake: Path) -> str:
    """Shell text that makes python, and the exp0007 command line built on it, the recorder."""
    return f"P='sh {fake.as_posix()}'; EX=\"$P -m plantgraph.qa.exp0007\"; X=data/runs/exp0007;"


def _record(tmp_path: Path, call: str) -> str:
    """Run one helper against the recording python; return every command line it recorded."""
    fake = tmp_path / "fake_python"
    fake.write_text(FAKE_PYTHON)
    log = tmp_path / "log.txt"
    base = tmp_path.as_posix()
    script = (
        f"{_libs()} {_recorder(fake)} E=data/runs/exp0004; A={base}/a; S=$A/dry; "
        "CYP_CORPORA=$S/corpora; AG_CORPORA=$S/corpora; QROOT=$A/questions; "
        "CACHE=$S/cache_copy.sqlite; EXPERIMENT=EXP-TEST; DEADLINE_S=120; ARM=d2; "
        f"NEO4J_DATABASE=e7tune; mkdir -p $S/logs $CYP_CORPORA; {call}"
    )
    done = _sh(script, ROOT, {**os.environ, "FAKE_LOG": str(log)})
    assert done.returncode == 0, done.stderr + done.stdout
    return log.read_text()


def test_the_dry_tier_runs_the_wrapper_on_the_cache_copy_and_passes_no_paid_flag(
    tmp_path: Path,
) -> None:
    for arm, strategy in (("CYP-A", "cypher_rag_lines"), ("AG", "graph_agent_lines")):
        command = _record(tmp_path, f"e2e_dry_tier {arm} E2E-DRY-{arm}")

        assert "-m plantgraph.exp0004.e2e_dry_run" in command
        assert f"--strategy {strategy} " in command and "--corpus H1000g2V:test" in command
        assert (
            "--cache-path " + (tmp_path / "a" / "dry" / "cache_copy.sqlite").as_posix() in command
        )
        assert "--allow-paid-calls" not in command and "--max-spend-usd" not in command
        assert "--concurrency 1" in command and "--question-deadline-s 120" in command


def test_the_load_is_r5s_plus_the_variant_flags_and_the_arms_links(tmp_path: Path) -> None:
    links = "data/runs/exp0004/test/H1000g2V/links/d2.json"
    command = _record(tmp_path, f"e2e_load {links}")

    assert "-m plantgraph.ingest synthetic --headline-v2 --target-sheets 1000" in command
    assert "--tag-variants --variant-families format naming" in command
    assert f"--identity-links {links}" in command
    assert "--store-profile plant_lines --corpus-id H1000g2V --fresh-database" in command
    assert "--headline-duplication-rate" not in command  # R5's H1000g2 uses the preset 0.25


def test_the_rehome_reads_the_sealed_files_and_writes_beside_the_arm(tmp_path: Path) -> None:
    command = _record(tmp_path, "e2e_rehome")

    sealed = "data/runs/exp0007/sealed"
    assert f"--source {sealed}/questions/H1000g2/questions.jsonl" in command
    assert f"--sealed-ingest {sealed}/corpora/H1000g2/ingest.json" in command
    assert (
        "--out " + (tmp_path / "a" / "questions" / "H1000g2V" / "questions.jsonl").as_posix()
        in command
    )
    assert "--proof " + (tmp_path / "a" / "rehome_proof.json").as_posix() in command


def test_the_live_tiers_use_the_split_caps_and_r5s_costs(tmp_path: Path) -> None:
    fake = tmp_path / "fake_python"
    fake.write_text(FAKE_PYTHON)
    log = tmp_path / "log.txt"
    script = (
        f"{_libs()} {_recorder(fake)} E=data/runs/exp0004; S={tmp_path.as_posix()}/s; "
        "CYP_CORPORA=/cyp; AG_CORPORA=/ag; QROOT=/q; CACHE=/c.sqlite; "
        "EXPERIMENT=EXP-TEST; E2E_CAP_CYP=0.05; E2E_CAP_AG=0.07; mkdir -p $S/logs; "
        "E2E_CORPUS=H1000g2V; v2t_run CYP-A E2E-CYP-H1000g2V-d0 H1000g2V full 120; "
        "v2t_run AG E2E-AG-H1000g2V-d0 H1000g2V full 120"
    )
    # EX is the recorder too, so the `health` check after each run is a recorded no-op
    done = _sh(script, ROOT, {**os.environ, "FAKE_LOG": str(log)})

    assert done.returncode == 0, done.stderr
    harness = [x for x in log.read_text().splitlines() if "plantgraph.qa.harness" in x]
    cyp, ag = harness
    assert "--max-spend-usd 0.05" in cyp and "--cost-per-question-usd 0.00075" in cyp
    assert "--max-spend-usd 0.07" in ag and "--cost-per-question-usd 0.00189" in ag


def test_a_cap_above_the_dry_runs_total_is_refused(tmp_path: Path) -> None:
    caps = tmp_path / "caps.json"
    caps.write_text(
        '{"arm":"d0","n_misses":{"cyp":1,"ag":1},"cost_per_question_usd":{},'
        '"cap_usd":{"cyp":0.01,"ag":0.02},"total_cap_usd":0.03,"basis":"t"}'
    )
    py = Path(sys.executable).as_posix()
    split = f"{_libs()} P='{py}'; e2e_split_caps {caps.as_posix()}"

    ok = _sh(
        f"{split} 0.03; echo $E2E_CAP_CYP $E2E_CAP_AG", ROOT, {**os.environ, "PYTHONPATH": "src"}
    )
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip().splitlines()[-1] == "0.01 0.02"
    bad = _sh(f"{split} 0.04", ROOT, {**os.environ, "PYTHONPATH": "src"})
    assert bad.returncode == 1 and "at most 0.03" in bad.stderr
