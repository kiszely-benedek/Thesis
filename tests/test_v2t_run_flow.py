"""run_ladder.sh and run_sealed.sh end to end over a recording fake of every Python command.

The scripts run for real in a throw-away git repository (copy of the scripts and inputs, a frozen
`system/` folder, real cap files from `v2t_caps`); only `$P` is replaced, by a script that logs
its arguments and writes the files the scripts expect. So these tests prove the order of the runs,
the options of each arm, which store profile each load uses, and what the two optional flags
(`--with-ctx-small`, `--with-f1-baseline`) add. No model, database or network is touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from exp0007_fakes import (
    write_e1_ctx_runs,
    write_prompt_sizes,
    write_questions,
    write_v7_runs,
)
from plantgraph.qa.exp0007.caps import sha256_of, write_cap_file
from plantgraph.qa.exp0007.v2t_caps import r4_v2t_caps, r5_v2t_caps, read_validation_costs

ROOT = Path(__file__).resolve().parents[1]
RUNS = "data/runs/exp0007"

FAKE_PYTHON = r"""#!/bin/sh
# Stand-in for the project's Python: logs every call and writes what the scripts look for next.
echo "$*" >> "$FAKE_LOG"
arg_after() {  # arg_after <option> <args...>: the word after the option
  want=$1; shift
  while [ $# -gt 1 ]; do if [ "$1" = "$want" ]; then echo "$2"; return; fi; shift; done
}
case "$*" in
  "-c "*) sed -n 's/.*"n_sheets": *\([0-9]*\).*/\1/p' "$3" | head -1 ;;
  *"exp0007 cap-of"*)  # the real command is tested elsewhere; here: the id must be in the cap file
    id=$(arg_after --run-id "$@"); file=$(arg_after --cap-file "$@")
    grep -q "\"run_id\": \"$id\"" "$file" || { echo "no cap for $id" >&2; exit 1; }
    if [ "$(arg_after --field "$@")" = cost ]; then echo 0.001; else echo 0.25; fi ;;
  *"exp0007 check-neo4j-target"*) echo scratch_db ;;
  *"exp0007 test-seed"*) echo 5000 ;;
  *"exp0007 setting-deadline"*) echo 120 ;;
  *"exp0007 head-questions"*)
    out=$(arg_after --out "$@"); mkdir -p "$(dirname "$out")"; echo '{}' > "$out" ;;
  *"qa.harness"*)
    id=$(arg_after --run-id "$@"); root=$(arg_after --runs-root "$@")
    mkdir -p "$root/$id"; echo '{"outcome": "ANSWERED"}' > "$root/$id/answers.jsonl" ;;
  *"plantgraph.ingest"*)
    out=$(arg_after --out "$@"); n=$(arg_after --target-sheets "$@")
    mkdir -p "$out"; echo "{\"counts\": {\"n_sheets\": $n}}" > "$out/ingest.json" ;;
esac
exit 0
"""

LADDER = ("H1g2", "H3g2", "H10g2", "H30g2")
SEALED = ("H100g2", "H1000g2", "H100g2d0", "H100g2d50")
SHEETS = {"H1g2": 1, "H3g2": 3, "H10g2": 10, "H30g2": 30, "H100g2": 100, "H1000g2": 1000}


def _sh(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", "-c", script], cwd=cwd, env=env, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The scripts in a git repo, frozen at E7, with both cap files written and hashed."""
    repo = tmp_path / "repo"
    scripts = repo / RUNS
    scripts.mkdir(parents=True)
    for name in ("lib.sh", "tune_lib.sh", "v2t_lib.sh", "run_ladder.sh", "run_sealed.sh"):
        shutil.copy(ROOT / RUNS / name, scripts / name)
    shutil.copytree(ROOT / RUNS / "inputs", scripts / "inputs")
    (repo / "system").mkdir()
    (repo / "system" / "a.py").write_text("1\n")
    fake = tmp_path / "fake_python"
    fake.write_bytes(FAKE_PYTHON.encode())
    fake.chmod(0o755)
    _write_inputs_and_caps(repo, tmp_path)
    return repo


def _write_inputs_and_caps(repo: Path, tmp_path: Path) -> None:
    costs = read_validation_costs(write_v7_runs(tmp_path / "v7"))
    x = repo / RUNS
    for corpus, sheets in SHEETS.items():
        ingest = x / ("ladder" if corpus in LADDER else "sealed") / "corpora" / corpus
        ingest.mkdir(parents=True)
        (ingest / "ingest.json").write_text(f'{{"counts": {{"n_sheets": {sheets}}}}}\n')
    for corpus in ("H100g2d0", "H100g2d50"):
        (x / "sealed" / "corpora" / corpus).mkdir(parents=True)
        (x / "sealed" / "corpora" / corpus / "ingest.json").write_text(
            '{"counts": {"n_sheets": 100}}\n'
        )
    for corpus in LADDER:
        write_questions(tmp_path / "lq", corpus, 92)
    for corpus in SEALED:
        write_questions(tmp_path / "sq", corpus, 560)
    write_questions(tmp_path / "c1", "H1000g2", 46)
    ladder = r4_v2t_caps(
        costs,
        tmp_path / "lq",
        write_prompt_sizes(tmp_path / "p.json"),
        write_e1_ctx_runs(tmp_path / "e1"),
    )
    write_cap_file(x / "caps_r4.json", ladder)
    write_cap_file(x / "caps_r5.json", r5_v2t_caps(costs, tmp_path / "sq", tmp_path / "c1"))
    git = "git init -q; git config user.email t@t; git config user.name t; git add -A; "
    assert _sh(git + "git commit -q -m base", repo, dict(os.environ)).returncode == 0
    freeze = (
        f". '{RUNS}/lib.sh'; . '{RUNS}/tune_lib.sh'; . '{RUNS}/v2t_lib.sh'; "
        f"git rev-parse HEAD > {RUNS}/E7.commit; echo V2T-A > {RUNS}/E7.system; "
        f"{{ sha256sum {RUNS}/E7.commit {RUNS}/E7.system {RUNS}/inputs/* {RUNS}/caps_r4.json; "
        f"v2t_system_hashes; }} > {RUNS}/E7.sha256; "
        f"sha256sum {RUNS}/caps_r5.json > {RUNS}/T7.sha256"
    )
    done = _sh(freeze, repo, {**os.environ, "V2T_FROZEN_FILES": "system"})
    assert done.returncode == 0, done.stderr


def _run(repo: Path, script: str, *flags: str, paid: bool = True) -> tuple[str, list[str]]:
    """Run a script; return its stdout and the fake's log lines."""
    caps = "caps_r4.json" if script == "run_ladder.sh" else "caps_r5.json"
    cap_args = ""
    if paid:
        digest = sha256_of(repo / RUNS / caps)
        cap_args = f"--allow-paid-calls --cap-file {RUNS}/{caps} --cap-sha256 {digest}"
    log = repo.parent / "fake.log"
    env = {
        **os.environ,
        "E7_PYTHON": (repo.parent / "fake_python").as_posix(),
        "FAKE_LOG": log.as_posix(),
        "V2T_FROZEN_FILES": "system",
        "E7_NEO4J_DATABASE": "scratch_db",
    }
    log.write_text("")
    done = _sh(f"sh {RUNS}/{script} {cap_args} {' '.join(flags)}", repo, env)
    assert done.returncode == 0, done.stderr + done.stdout
    return done.stdout, log.read_text().splitlines()


def _paid_runs(lines: list[str]) -> list[str]:
    """Run ids of the paid harness calls, in order (a replay has no --allow-paid-calls)."""
    ids = []
    for line in lines:
        words = line.split()
        if "qa.harness" in line and "--allow-paid-calls" in words:
            ids.append(words[words.index("--run-id") + 1])
    return ids


def _line_of(lines: list[str], run_id: str) -> str:
    harness = [line for line in lines if "qa.harness" in line]
    return next(line for line in harness if f"--run-id {run_id} " in line + " ")


V2T_LADDER_RUNS = [
    "E7-CYP-H1g2-SMOKE", "E7-CYP-H1g2", "E7-CYP-H3g2", "E7-CYP-H10g2", "E7-CYP-H30g2",
    "E7-AG-H1g2-SMOKE", "E7-AG-H1g2", "E7-AG-H3g2", "E7-AG-H10g2", "E7-AG-H30g2",
]  # fmt: skip
CTX_RUNS = ["E7-CTXH-H1g2-SMOKE", "E7-CTXH-H1g2", "E7-CTXH-H3g2", "E7-CTXH-H10g2"]


def test_r4_runs_the_two_v2t_tiers_and_nothing_else_by_default(repo: Path) -> None:
    out, lines = _run(repo, "run_ladder.sh")

    assert _paid_runs(lines) == V2T_LADDER_RUNS
    assert not any("E7-CTXH" in line for line in lines)
    assert all(
        "--store-profile plant_lines" in line for line in lines if "plantgraph.ingest" in line
    )
    assert len([line for line in lines if "plantgraph.ingest" in line]) == 4
    cyp = _line_of(lines, "E7-CYP-H3g2")
    assert "--strategy cypher_rag_lines" in cyp and "--question-deadline-s 120" in cyp
    assert "params_cypher_v2t_a.json" in cyp and "--corpora-root" in cyp
    agent = _line_of(lines, "E7-AG-H3g2")
    assert "--strategy graph_agent_lines" in agent and "params_agent_v2t.json" in agent
    assert "ContextRAG small ladder: no" in out
    assert any("exp0001 report --edition v2 --system v2t" in line for line in lines)
    assert any("cascade report --no-baselines --setting A" in line for line in lines)
    assert len([line for line in lines if "tune-report" in line]) == 4


def test_r4_with_the_flag_adds_contextrag_on_the_three_small_sizes_only(repo: Path) -> None:
    _, lines = _run(repo, "run_ladder.sh", "--with-ctx-small")

    assert _paid_runs(lines) == V2T_LADDER_RUNS + CTX_RUNS  # smoke first, no H30g2
    smoke = _line_of(lines, "E7-CTXH-H1g2-SMOKE")
    assert "--strategy context_rag" in smoke and "pin_agent_luna_final_high.json" in smoke
    assert "--question-deadline-s 300" in smoke and "--strategy-params-json" not in smoke
    assert "--questions-root" in smoke and "questions_smoke" in smoke
    replays = [line for line in lines if "--run-id INF-E7-CTXH-" in line]
    assert len(replays) == 3 and all("--allow-paid-calls" not in line for line in replays)
    health = [line for line in lines if "exp0007 health" in line and "E7-CTXH" in line]
    assert len(health) == 4 and all("--kind ctx" in line for line in health)
    assert all(
        "--kind tier" in line for line in lines if "exp0007 health" in line and "CTXH" not in line
    )
    assert any(
        "--footnote ContextRAG was run on H1g2, H3g2 and H10g2 only" in line for line in lines
    )


def test_a_second_start_of_r4_runs_nothing_again(repo: Path) -> None:
    _run(repo, "run_ladder.sh", "--with-ctx-small")

    out, lines = _run(repo, "run_ladder.sh", "--with-ctx-small")

    assert _paid_runs(lines) == [] and "skip cypher_H3g2 (done)" in out


def test_r4_free_mode_shows_the_caps_and_calls_no_harness(repo: Path) -> None:
    out, lines = _run(repo, "run_ladder.sh", paid=False)

    assert "checked only: nothing was paid" in out and "E7-CTXH-H10g2" in out
    assert not any("qa.harness" in line or "plantgraph.ingest" in line for line in lines)


SEALED_RUNS = [
    "S7-CYP-H100g2-SMOKE", "S7-CYP-H100g2", "S7-CYP-H1000g2", "S7-CYP-H100g2d0", "S7-CYP-H100g2d50",
    "S7-AG-H100g2-SMOKE", "S7-AG-H100g2", "S7-AG-H1000g2", "S7-AG-H100g2d0", "S7-AG-H100g2d50",
    "S7-AG-H1000g2-C1",
]  # fmt: skip


def test_r5_runs_v2t_on_the_four_corpora_and_the_control_by_default(repo: Path) -> None:
    out, lines = _run(repo, "run_sealed.sh")

    assert _paid_runs(lines) == SEALED_RUNS
    loads = [line for line in lines if "plantgraph.ingest" in line]
    assert len(loads) == 4 and all("--store-profile plant_lines" in line for line in loads)
    assert sum("--headline-duplication-rate" in line for line in loads) == 2  # d0 and d50
    c1 = _line_of(lines, "S7-AG-H1000g2-C1")
    assert "--concurrency 1" in c1 and "cache_s7_c1.sqlite" in c1
    assert "F1 baseline: no" in out
    claims = next(line for line in lines if "--sealed-claims" in line)
    assert "--claims v2t --setting A" in claims and "cascade_v4_iso.json" in claims
    assert not any("--claims f1" in line for line in lines)
    assert any("duplication-report --system v2t" in line for line in lines)


def test_r5_with_the_baseline_flag_adds_f1_on_h100g2_and_h1000g2_only(repo: Path) -> None:
    _, lines = _run(repo, "run_sealed.sh", "--with-f1-baseline")

    paid = _paid_runs(lines)
    f1 = [r for r in paid if r.startswith("S7F1-")]
    assert f1 == ["S7F1-CYP-H100g2", "S7F1-CYP-H1000g2", "S7F1-AG-H100g2", "S7F1-AG-H1000g2"]
    assert [r for r in paid if not r.startswith("S7F1-")] == SEALED_RUNS
    # F1's Cypher run reads the plain plant profile, loaded right before it
    at = next(i for i, line in enumerate(lines) if "--run-id S7F1-CYP-H100g2 " in line + " ")
    previous_load = next(line for line in reversed(lines[:at]) if "plantgraph.ingest" in line)
    assert "--store-profile plant " in previous_load + " " and "plant_lines" not in previous_load
    cyp, agent = _line_of(lines, "S7F1-CYP-H1000g2"), _line_of(lines, "S7F1-AG-H1000g2")
    assert "--strategy cypher_rag_plant" in cyp and "params_cypher_plant.json" in cyp
    assert "--strategy graph_agent_low_steps" in agent and "params_agent_low.json" in agent
    assert "--question-deadline-s 120" in cyp and "--question-deadline-s 120" in agent
    replays = [line for line in lines if "--run-id INF-S7F1-" in line]
    assert len(replays) == 4 and all("--allow-paid-calls" not in line for line in replays)
    f1_report = next(line for line in lines if "--claims f1" in line)
    assert "cascade_v3.json" in f1_report and "S7F1-AG-H1000g2" in f1_report
    assert "--cutoff-s 120" in f1_report and "report_f1_baseline" in f1_report
    loads = [line for line in lines if "plantgraph.ingest" in line]
    assert sum("--store-profile plant " in line + " " for line in loads) == 2


def test_r5_free_mode_lists_the_baseline_caps_and_the_flag_state(repo: Path) -> None:
    out, lines = _run(repo, "run_sealed.sh", "--with-f1-baseline", paid=False)

    assert "F1 baseline: yes" in out and "S7F1-AG-H1000g2" in out
    assert not any("qa.harness" in line for line in lines)


def test_the_baseline_flag_is_the_only_extra_option_r5_knows(repo: Path) -> None:
    python = (repo.parent / "fake_python").as_posix()
    env = {**os.environ, "E7_PYTHON": python, "FAKE_LOG": "/dev/null", "V2T_FROZEN_FILES": "system"}

    done = _sh(f"sh {RUNS}/run_sealed.sh --with-ctx-small", repo, env)

    assert done.returncode == 1 and "unknown option --with-ctx-small" in done.stderr
