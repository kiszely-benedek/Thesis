"""F10: refuses a dirty tree, a change outside the allowed list and wrong B files; writes once."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.qa.exp0009 import freeze, prereg_b
from plantgraph.qa.exp0009.gates import GateResult

NAMED = "a" * 40
HEAD = "b" * 40


def test_named_head_and_clean_tree() -> None:
    assert freeze.named_head(f"x\nPart A code commit: `{NAMED}`\n") == NAMED
    with pytest.raises(freeze.FreezeRefused, match="Part A code commit"):
        freeze.named_head("nothing here")
    freeze.check_clean("")
    with pytest.raises(freeze.FreezeRefused, match="changed path"):
        freeze.check_clean(" M src/plantgraph/qa/final_answer.py\n")


def test_only_the_allowed_paths_may_change_since_part_a() -> None:
    allowed = [
        "src/plantgraph/qa/v2tb/strategies_b.py", "tests/v2tb/test_x.py",
        "data/runs/exp0009/prereg/PREREG_A.md", "docs/private/x.md",
    ]  # fmt: skip
    freeze.check_head(HEAD, NAMED, allowed)
    freeze.check_head(
        NAMED, NAMED, ["src/plantgraph/qa/final_answer.py"]
    )  # HEAD is the named commit
    with pytest.raises(freeze.FreezeRefused, match="final_answer"):
        freeze.check_head(HEAD, NAMED, [*allowed, "src/plantgraph/qa/final_answer.py"])


def test_b_files_must_equal_the_chosen_round() -> None:
    chosen = {"a.py": "1", "policy:cascade_v4_iso_b": "p"}
    freeze.check_b_files(chosen, dict(chosen), "round 2")
    with pytest.raises(freeze.FreezeRefused, match="a.py"):
        freeze.check_b_files(chosen, {**chosen, "a.py": "2"}, "round 2")


def test_b_code_hash_file_has_the_policy_line_and_is_written_once(tmp_path: Path) -> None:
    out = tmp_path / "b_code.sha256"
    freeze.write_b_code_sha256(out)
    hashes = freeze.read_hash_file(out)
    assert (
        freeze.POLICY_LINE_NAME in hashes
        and hashes[freeze.POLICY_LINE_NAME] == freeze.policy_digest()
    )
    assert any(name.endswith("strategies_b.py") for name in hashes)
    with pytest.raises(FileExistsError):
        freeze.write_b_code_sha256(out)


def test_hash_files_are_written_once(tmp_path: Path) -> None:
    files = tmp_path / "f.txt"
    files.write_text("x", encoding="utf-8")
    assert freeze.write_e10(tmp_path, HEAD, [files]) == 1
    with pytest.raises(FileExistsError):
        freeze.write_e10(tmp_path, HEAD, [files])
    freeze.write_b_files_hash(tmp_path)
    with pytest.raises(FileExistsError):
        freeze.write_b_files_hash(tmp_path)
    for name in ("PREREG_A.md", "PREREG_B.md", "seeds.json", "plan.json", "position_prior.json"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    assert freeze.write_prereg_sha(tmp_path, []) == 8
    with pytest.raises(FileExistsError):
        freeze.write_prereg_sha(tmp_path, [])


def test_part_b_renders_and_the_best_round_wins_ties_to_the_earlier() -> None:
    rounds = [
        prereg_b.TuningRound(number=1, change="start", b_dev_accuracy=0.8, b_minus_a2_on_r=0.0),
        prereg_b.TuningRound(number=2, change="prompt", b_dev_accuracy=0.8, b_minus_a2_on_r=0.01),
        prereg_b.TuningRound(number=3, change="item", b_dev_accuracy=0.7, b_minus_a2_on_r=0.0),
    ]
    assert prereg_b.choose_round(rounds).number == 1
    part = prereg_b.PartB(
        code_commit=HEAD, gates=[GateResult(gate="G1", passed=True, detail="ok")], b_sealed=False,
        a2_cells={"p": {"F": (1, 2)}}, b_cells={"p": {"F": (2, 2)}}, rounds=rounds, chosen_round=1,
        replay_verdicts={"V9-AG-x": "identical"}, cost_per_question_usd={"A2-ag-100": 0.0016},
        sealed_caps_usd={"S9-AG-x": 0.5}, val1000_pool_peak_gib=None, e10_files=3,
        e10_sha256_file_sha256="0" * 64,
    )  # fmt: skip
    text = prereg_b.render_part_b(part)
    assert "G1: **PASS**" in text and "A2 alone runs sealed" in text and "| 1 | start |" in text
    with pytest.raises(ValueError, match="at least one"):
        prereg_b.choose_round([])


def test_the_policy_digest_does_not_depend_on_the_hash_seed() -> None:
    import os
    import subprocess
    import sys

    code = "from plantgraph.qa.exp0009 import freeze; print(freeze.policy_digest())"
    seen = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout  # fmt: skip
        for seed in ("1", "2", "3")
    }
    assert len(seen) == 1
