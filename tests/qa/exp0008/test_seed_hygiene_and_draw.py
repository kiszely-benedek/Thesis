"""Seed hygiene, the seed draw and the v2.1 corpus ids (F12, ADR-0065)."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.exp0004.corpus import corpus_id_for
from plantgraph.ingest.headline_v2 import headline_corpus_id_v2
from plantgraph.ingest.seed_plan import RETIRED_TEST_SEEDS, SeedPlan, load_seed_plan
from plantgraph.qa.exp0008.draw_seeds import draw_seed_plan, main, write_seed_plan
from plantgraph.qa.exp0008.hygiene import (
    recorded_test_seeds,
    require_fresh_test_seed,
    retired_seeds,
)
from plantgraph.qa.questions.sealed_set import require_test_corpus

_OLD_RECORDED = {5777, 5888, 5999}


def _runs_with_old_seeds(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    (runs / "a").mkdir(parents=True, exist_ok=True)
    (runs / "a" / "ingest.json").write_text('{"config": {"generator": {"seed": 5777}}}')
    (runs / "a" / "availability.json").write_text('{"seed":5888, "seed_chars": 5270, "x_seed": 7}')
    (runs / "a" / "rows.jsonl").write_text('{"sample_seed": 5999}\n{"seed": 12}\n')
    return runs


def _plan(tmp_path: Path, draw_seed: int = 7) -> SeedPlan:
    runs = _runs_with_old_seeds(tmp_path)
    return draw_seed_plan(draw_seed, retired_seeds(runs), runs)


def test_recorded_seeds_come_from_seed_fields_in_the_test_range_only(tmp_path: Path) -> None:
    assert set(recorded_test_seeds(_runs_with_old_seeds(tmp_path))) == _OLD_RECORDED


def test_retired_seeds_include_the_registered_ones(tmp_path: Path) -> None:
    retired = retired_seeds(_runs_with_old_seeds(tmp_path))
    assert {5100, 5001, 5002, 5003, 212, 213} | _OLD_RECORDED <= retired


def test_a_retired_seed_is_refused_for_a_test_role() -> None:
    with pytest.raises(ValueError, match="5002"):
        require_fresh_test_seed(5002, RETIRED_TEST_SEEDS)
    require_fresh_test_seed(5500, RETIRED_TEST_SEEDS)


def test_the_draw_is_reproducible_and_avoids_every_retired_seed(tmp_path: Path) -> None:
    first, again = _plan(tmp_path), _plan(tmp_path)
    assert first.all_seeds() == again.all_seeds()
    assert first.all_seeds() != _plan(tmp_path, draw_seed=8).all_seeds()
    assert not set(first.all_seeds()) & (RETIRED_TEST_SEEDS | _OLD_RECORDED)
    assert len(set(first.all_seeds())) == len(first.all_seeds()) == 43
    assert first.draw.draw_seed == 7 and "sample" in first.draw.method


def test_writing_refuses_to_overwrite(tmp_path: Path) -> None:
    plan, out = _plan(tmp_path), tmp_path / "prereg" / "seeds.json"
    write_seed_plan(plan, out)
    assert load_seed_plan(out) == plan
    with pytest.raises(FileExistsError, match="never redrawn"):
        write_seed_plan(plan, out)


def test_main_writes_once_and_prints_a_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runs, out = _runs_with_old_seeds(tmp_path), tmp_path / "seeds.json"
    args = ["--draw-seed", "3", "--runs-root", str(runs), "--out", str(out)]
    assert main(args) == 0
    assert "sealed 1000 sheets, plant p5" in capsys.readouterr().out
    with pytest.raises(FileExistsError):
        main(args)


def test_a_plan_with_a_retired_seed_is_invalid(tmp_path: Path) -> None:
    broken = _plan(tmp_path).model_dump() | {"ladder_seed": 5002}
    with pytest.raises(ValueError, match="fresh seeds"):
        SeedPlan.model_validate(broken)


def test_a_missing_seed_file_means_not_drawn_yet(tmp_path: Path) -> None:
    assert load_seed_plan(tmp_path / "nothing.json") is None


def test_ids_follow_the_g21_scheme(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    s100, s1000 = plan.sealed[100], plan.sealed[1000]
    assert headline_corpus_id_v2(100, 1) == "D100g21"
    assert headline_corpus_id_v2(100, 211) == "X100g21s211"
    assert headline_corpus_id_v2(100, s100[0], seed_plan=plan) == "H100g21p1"
    assert headline_corpus_id_v2(1000, s1000[4], seed_plan=plan) == "H1000g21p5"
    assert headline_corpus_id_v2(100, s100[0], 0.0, plan) == "H100g21p1d0"
    assert headline_corpus_id_v2(100, s100[0], 0.5, plan) == "H100g21p1d50"
    assert headline_corpus_id_v2(30, plan.ladder_seed, seed_plan=plan) == "H30g21"
    assert headline_corpus_id_v2(1, plan.single_sheet_candidates[0], seed_plan=plan) == "H1g21"
    assert headline_corpus_id_v2(1000, plan.validation[1000], seed_plan=plan) == "VAL1000g21"


def test_test_ids_pass_the_sealed_set_check_and_dev_ids_do_not() -> None:
    for corpus_id in ("H100g21p1", "H1000g21p3d50", "H30g21", "H1g21", "H100g2d0", "H100"):
        require_test_corpus(corpus_id)
    for corpus_id in (headline_corpus_id_v2(100, 1), "VAL100g21", "X100g21s211"):
        with pytest.raises(ValueError, match="test corpus id"):
            require_test_corpus(corpus_id)


def test_ids_refuse_retired_undrawn_and_wrong_size_seeds(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with pytest.raises(ValueError, match="retired"):
        headline_corpus_id_v2(100, 5002, seed_plan=plan)
    with pytest.raises(ValueError, match="in the drawn seed plan"):
        headline_corpus_id_v2(100, plan.sealed[1000][0])
    with pytest.raises(ValueError, match="for 100 sheets"):
        headline_corpus_id_v2(100, plan.sealed[1000][0], seed_plan=plan)


def test_exp0004_ids_extend_the_plant_id(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    seed = plan.sealed[1000][1]
    assert corpus_id_for(100, 1, 1.0, ["format"]) == "D100g21d100Vf"
    assert corpus_id_for(1000, seed, 0.25, ["naming", "format"], plan) == "H1000g21p2V"
    assert corpus_id_for(1000, seed, 1.0, ["format", "naming"], plan) == "H1000g21p2d100V"
