"""The plant plan, the replay comparison, the memory probe and the launcher's command line (F15)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from plantgraph.qa.exp0008 import launcher, memory_probe, replay
from plantgraph.qa.exp0008.plan import KINDS, Plan, SeedTable


def _ids(plants: list) -> list[str]:  # type: ignore[type-arg]
    return [p.corpus_id for p in plants]


def test_the_smoke_plan_lists_every_kind_with_tiny_plants_and_no_test_seed() -> None:
    plan = Plan(SeedTable.smoke(), smoke=True)
    for kind in KINDS:
        plants = plan.by_kind(kind)
        assert plants and all(p.sheets <= 10 and p.seed < 1000 for p in plants)


def test_the_plan_has_five_sealed_plants_per_size_and_the_registered_p3_set() -> None:
    plan = Plan(SeedTable.smoke(), smoke=True)
    assert _ids(plan.sealed()) == [f"H{n}g21p{k}" for n in (100, 1000) for k in range(1, 6)]
    assert _ids(plan.p3())[:4] == ["H100g21p1V", "H100g21p1d100V", "H1000g21p1V", "H1000g21p1d100V"]
    assert _ids(plan.p3())[4:] == [f"H1000g21p{k}V" for k in range(2, 6)]
    assert _ids(plan.p4()) == [f"H1000g21p{k}V" for k in range(1, 6)]
    assert _ids(plan.descriptive()) == ["H100g21p1d0", "H100g21p1d50"]
    assert _ids(plan.demo()) == ["H1000g21p1"]


def test_variants_share_the_seed_of_their_plant_and_carry_the_v_flag() -> None:
    plan = Plan(SeedTable.smoke(), smoke=True)
    sealed = {p.corpus_id: p for p in plan.sealed()}
    for variant in plan.p4():
        assert variant.variant and variant.seed == sealed[variant.corpus_id.removesuffix("V")].seed


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        Plan(SeedTable.smoke(), smoke=True).by_kind("everything")


def _rows(path: Path, rows: list[dict]) -> Path:  # type: ignore[type-arg]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _row(qid: str, answer: str = "a", cached: bool = False, run: str = "run") -> dict:  # type: ignore[type-arg]
    return {"run_id": run, "question_id": qid, "answer": answer, "latency_s": 2.0,
            "trace": {"from_cache": cached}}  # fmt: skip


def test_a_replay_that_differs_only_in_id_cache_flag_and_time_is_identical(tmp_path: Path) -> None:
    original = _rows(tmp_path / "o.jsonl", [_row("q1"), _row("q2")])
    replayed = _rows(
        tmp_path / "r.jsonl",
        [_row("q1", cached=True, run="INF-run"), _row("q2", cached=True, run="INF-run")],
    )
    assert replay.compare(replayed, original, allow_prefix=False) == "identical"


def test_a_cypher_replay_may_stop_early_but_a_different_row_is_never_accepted(
    tmp_path: Path,
) -> None:
    original = _rows(tmp_path / "o.jsonl", [_row("q1"), _row("q2"), _row("q3")])
    short = _rows(tmp_path / "s.jsonl", [_row("q1", cached=True)])
    assert replay.compare(short, original, allow_prefix=True) == "prefix_equal: 1 of 3 rows"
    with pytest.raises(ValueError, match="a replay must be complete"):
        replay.compare(short, original, allow_prefix=False)
    wrong = _rows(tmp_path / "w.jsonl", [_row("q1", answer="DIFFERENT")])
    with pytest.raises(ValueError, match="1 differ"):
        replay.compare(wrong, original, allow_prefix=True)


def test_the_memory_probe_reports_peak_memory_and_the_exit_code() -> None:
    ok = memory_probe.probe([sys.executable, "-c", "x = bytearray(30_000_000); print(len(x))"])
    assert ok.passed and ok.peak_rss_bytes > 0
    bad = memory_probe.probe([sys.executable, "-c", "raise SystemExit(3)"])
    assert bad.return_code == 3 and not bad.passed
    too_big = memory_probe.probe(
        [sys.executable, "-c", "x = bytearray(60_000_000)"], limit_bytes=1000
    )
    assert not too_big.passed


def test_the_launcher_prints_the_smoke_plan_and_a_failure_as_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert launcher.main(["plan", "validation", "--smoke"]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("VAL100g21 10 ")
    missing = tmp_path / "no_seeds.json"
    assert launcher.main(["plan", "sealed", "--seed-file", str(missing)]) == 1
    assert "ERROR: expected the drawn seeds" in capsys.readouterr().err


def test_the_launcher_balance_command_uses_the_fake_in_the_smoke_and_refuses_a_short_balance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert launcher.main(["balance", "--needed", "5", "--fake-balance", "100"]) == 0
    assert "balance $100.00" in capsys.readouterr().out
    assert launcher.main(["balance", "--needed", "50", "--fake-balance", "10"]) == 1
    assert "ERROR: expected a balance of at least $50.00" in capsys.readouterr().err


def test_the_launcher_stops_a_stage_with_a_resume_command(tmp_path: Path) -> None:
    args = [
        "stopped",
        "--dir",
        str(tmp_path),
        "--stage",
        "M6a",
        "--reason",
        "cap",
        "--resume",
        "sh x --from M6a",
    ]
    assert launcher.main(args) == 0
    assert "resume: sh x --from M6a" in (tmp_path / "STOPPED").read_text(encoding="utf-8")


def test_the_plan_composes_the_same_ids_as_the_corpus_id_function_of_f12() -> None:
    from plantgraph.ingest.seed_plan import DrawRecord, SeedPlan
    from plantgraph.qa.exp0008.plan import checked_id

    fixture = SeedPlan(  # arbitrary fixture seeds in the test range, not a draw
        validation={100: 5201, 1000: 5202},
        ladder_seed=5203,
        single_sheet_candidates=(5204,),
        sealed={100: tuple(range(5210, 5215)), 1000: tuple(range(5220, 5225))},
        draw=DrawRecord(draw_seed=0, method="fixture", pool="-", retired=(), retired_sources="-",
                        drawn_at_utc="-", python_version="-"),
    )  # fmt: skip
    plan = Plan(SeedTable.from_plan(fixture))
    plain = [*plan.sealed(), *plan.descriptive(), *plan.validation()]
    assert len(plain) == 14
    for spec in plain:
        assert checked_id(spec, fixture) == spec.corpus_id
