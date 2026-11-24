"""The launcher commands: smoke draw, plan lists, caps, estimates, gates, tuning, G0f, readiness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.qa.exp0009 import launcher, readiness
from plantgraph.qa.exp0009.plan import Exp0009Plan


def _run(*argv: str) -> int:
    return launcher.main(list(argv))


@pytest.fixture
def prereg(tmp_path: Path) -> Path:
    folder = tmp_path / "prereg"
    assert _run("draw", "--smoke", "--prereg", str(folder)) == 0
    return folder


def test_smoke_draw_writes_a_plan_with_every_plant(prereg: Path) -> None:
    plan = Exp0009Plan.model_validate_json((prereg / "plan.json").read_text(encoding="utf-8"))
    assert len(plan.plants) == 14 and len(plan.sealed_ids()) == 10


def test_plan_list_prints_the_plants_of_a_role(
    prereg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run("plan-list", "sealed", "--prereg", str(prereg)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[0] == "H100g22p1" and lines[-1].split()[0] == "H1000g22p5"


def test_estimate_and_run_cap(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        _run("estimate", "--stage", "P1c", "--root", str(tmp_path), "--balance-usd", "37.11") == 0
    )
    assert "step ceiling $21.09" in capsys.readouterr().out
    questions = tmp_path / "q.jsonl"
    questions.write_text("x\n" * 100, encoding="utf-8")
    argv = [
        "run-cap",
        "--questions",
        str(questions),
        "--tier",
        "ag",
        "--scale",
        "100",
        "--arm",
        "A2",
    ]
    argv += ["--step", "P1c", "--root", str(tmp_path), "--step-dir", str(tmp_path)]
    assert _run(*argv) == 0
    assert float(capsys.readouterr().out.strip()) == pytest.approx(100 * 0.001588 * 1.5, abs=1e-4)


def test_a_failing_command_prints_error_and_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run("estimate", "--stage", "P0", "--root", str(tmp_path)) == 1
    assert "ERROR:" in capsys.readouterr().err


def _cells(folder: Path, fail: str | None) -> list[str]:
    plants = ["VAL100g22", "VAL1000g22"]
    extra = ["--fail", fail] if fail else []
    assert (
        _run(
            "smoke-cells",
            *sum((["--plant", p] for p in plants), []),
            "--out-dir",
            str(folder),
            *extra,
        )
        == 0
    )
    pairs = [f"{p}={folder}/{p}_{arm}.json" for p in plants for arm in ("a2", "b")]
    return [
        x
        for p in plants
        for x in (
            "--a2",
            pairs[0 if p == plants[0] else 2],
            "--b",
            pairs[1 if p == plants[0] else 3],
        )
    ]


def test_validation_gates_branch_on_b_but_stop_on_a2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "p1b.json"
    assert _run("validation-gates", *_cells(tmp_path / "ok", None), "--out", str(out)) == 0
    assert "b_sealed=yes" in capsys.readouterr().out
    assert (
        _run("validation-gates", *_cells(tmp_path / "b", "g1b"), "--out", str(tmp_path / "b.json"))
        == 0
    )
    assert "b_sealed=no" in capsys.readouterr().out
    assert (
        _run(
            "validation-gates", *_cells(tmp_path / "b2", "g1b2"), "--out", str(tmp_path / "b2.json")
        )
        == 0
    )
    assert "b_sealed=no" in capsys.readouterr().out
    assert (
        _run("validation-gates", *_cells(tmp_path / "a", "g1"), "--out", str(tmp_path / "a.json"))
        == 1
    )


def test_tuning_round_one_then_refuses_unchanged_b_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "root"
    cells = tmp_path / "cells"
    assert _run("smoke-cells", "--plant", "D100g22", "--out-dir", str(cells)) == 0
    assert _run("tuning-check", "--root", str(root), "--round", "1") == 0
    argv = ["tuning-round", "--root", str(root), "--round", "1", "--change", "start"]
    argv += [
        "--b-report",
        str(cells / "D100g22_b.json"),
        "--a2-report",
        str(cells / "D100g22_a2.json"),
    ]
    assert _run(*argv) == 0
    assert "next_round=yes" in capsys.readouterr().out
    assert _run("tuning-check", "--root", str(root), "--round", "2") == 1  # B files unchanged
    assert "changed B files" in capsys.readouterr().err
    assert _run("tuning-check", "--root", str(root), "--round", "4") == 1
    assert _run("finish-tuning", "--root", str(root)) == 0
    assert (root / "tune" / "chosen_round.txt").read_text(encoding="utf-8").strip() == "1"
    assert _run("tuning-check", "--root", str(root), "--round", "2") == 1  # tuning is finished


def test_g0f_is_empty_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("g0f") == 0
    assert json.loads(capsys.readouterr().out) == []


def test_readiness_refuses_a_fill_marker_and_an_uncommitted_part_a(prereg: Path) -> None:
    (prereg / "PREREG_A.md").write_text("Part A code commit: <<FILL>>\n", encoding="utf-8")
    check = readiness.check_prereg_a(prereg)
    assert check.status == "FAIL"
    assert "<<FILL" in check.detail and "tracked" in check.detail
    assert readiness.check_prereg_a(prereg / "missing").status == "FAIL"
