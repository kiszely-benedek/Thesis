"""The V2T tuning protocol as data: plants, seeds, run ids and spend caps (no model, no DB)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.ingest.headline_v2 import TEST_SEED_RANGE
from plantgraph.qa.exp0007 import caps as caps_module
from plantgraph.qa.exp0007 import cli
from plantgraph.qa.exp0007.neo4j_tmp import require_droppable
from plantgraph.qa.exp0007.tune_plan import (
    TUNING_PLANT,
    VALIDATION_PLANTS,
    final_caps,
    require_corpus,
    round_total_usd,
    tuning_caps,
)


def test_the_tuning_plant_is_always_allowed_and_no_seed_is_a_test_seed() -> None:
    assert require_corpus("X100g2s211", final_v=False) == TUNING_PLANT
    for plant in (TUNING_PLANT, *VALIDATION_PLANTS):
        assert plant.seed not in TEST_SEED_RANGE


@pytest.mark.parametrize("corpus_id", ["X100g2s212", "X1000g2s213"])
def test_validation_plants_are_refused_without_final_v(corpus_id: str) -> None:
    with pytest.raises(ValueError, match="pass --final-v"):
        require_corpus(corpus_id, final_v=False)
    assert require_corpus(corpus_id, final_v=True).role == "validation"


def test_an_unknown_or_test_plant_is_refused() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        require_corpus("H100g2", final_v=True)  # a sealed test plant (seed 5002)


def test_caps_follow_the_formula_on_the_upper_estimates() -> None:
    caps = tuning_caps(163)
    by_id = {e.run_id: e for e in caps.entries}

    # 1.3 x 163 x 0.00086 = 0.182 -> 0.20 ; 1.3 x 163 x 0.0025 = 0.530 -> 0.55 (design 7.5)
    assert by_id["T7R1-CYP-A-X100g2s211"].cap_usd == 0.20
    assert by_id["T7R1-CYP-B-X100g2s211"].cap_usd == 0.20
    assert by_id["T7R1-AG-X100g2s211"].cap_usd == 0.55
    assert by_id["T7S-AG-X100g2s211"].cap_usd == 0.02
    assert round_total_usd(caps, 1) == 0.95 + 0.04  # one agent, two Cypher runs, two smokes
    assert round_total_usd(caps, 2) == 0.95


def test_final_caps_cover_v2t_both_settings_and_f1_on_both_validation_plants() -> None:
    caps = final_caps({"X100g2s212": 163, "X1000g2s213": 163})
    by_id = {e.run_id: e for e in caps.entries}

    assert len(caps.entries) == 10
    assert by_id["V7F1-AG-X100g2s212"].cap_usd == 0.20  # F1 mean 0.000866: 1.3 x 163 x c = 0.18
    assert by_id["V7F1-CYP-X1000g2s213"].cap_usd == 0.15  # x1.1 margin: 0.111
    assert by_id["V7-AG-X1000g2s213"].cap_usd == 0.60  # 1.3 x 163 x 0.00275 = 0.583


def test_a_cap_file_is_written_once_and_hash_verified(tmp_path: Path) -> None:
    path = tmp_path / "caps.json"
    digest = caps_module.write_cap_file(path, tuning_caps(10))

    assert caps_module.load_verified(path, digest).stage == "tune"
    with pytest.raises(FileExistsError):
        caps_module.write_cap_file(path, tuning_caps(10))
    with pytest.raises(ValueError, match="to hash to"):
        caps_module.load_verified(path, "0" * 64)


def test_the_cli_prints_the_plant_and_refuses_v_without_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["tune-corpus", "--corpus-id", "X100g2s211"])
    assert stopped.value.code == 0 and capsys.readouterr().out.split() == ["100", "211"]
    with pytest.raises(SystemExit) as refused:
        cli.main(["tune-corpus", "--corpus-id", "X1000g2s213"])
    assert refused.value.code == 1 and "--final-v" in capsys.readouterr().err


def test_make_tune_caps_writes_the_file_and_prints_round_sums(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    questions = tmp_path / "questions.jsonl"
    questions.write_text("\n".join(json.dumps({"id": i}) for i in range(163)) + "\n")
    out = tmp_path / "caps_tune.json"

    with pytest.raises(SystemExit) as stopped:
        cli.main(
            ["make-tune-caps", "--stage", "tune", "--questions", str(questions), "--out", str(out)]
        )

    text = capsys.readouterr().out
    assert stopped.value.code == 0 and "round 1: sum of caps $0.99" in text and "sha256" in text


@pytest.mark.parametrize("name", ["neo4j", "system"])
def test_the_users_and_the_admin_database_are_never_dropped(name: str) -> None:
    with pytest.raises(ValueError, match="only a temporary database"):
        require_droppable(name)
    assert require_droppable("e7tune") == "e7tune"
