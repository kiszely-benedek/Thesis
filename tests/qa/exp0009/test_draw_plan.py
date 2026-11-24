"""The EXP-0009 draw: targets, size refusal, tagging allocation, ids, never overwriting."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from plantgraph.ingest.seed_plan import PLANTS_PER_SIZE, SeedPlan
from plantgraph.qa.exp0008.draw_seeds import draw_seed_plan
from plantgraph.qa.exp0009 import draw
from plantgraph.qa.exp0009.plan import Role, a_id_of, b_id_of, plant_id

PRIOR = json.dumps({"tag": {"majority": "NO"}, "descriptor": {"majority": "NO"}})


def _sizer(target: int, seed: int) -> tuple[int, int]:
    return target // 10, target + 1


def _flags(n_units: int, seed: int) -> tuple[bool, ...]:
    return (True,) * (1 if n_units < 20 else 10)


def _seeds(tmp_path: Path) -> SeedPlan:
    return draw_seed_plan(7, frozenset(), tmp_path)


def test_ids_use_the_nominal_scale() -> None:
    assert plant_id(Role.SEALED, 100, 3) == "H100g22p3"
    assert plant_id(Role.VALIDATION, 1000) == "VAL1000g22"
    assert plant_id(Role.DEV, 100) == "D100g22"
    assert b_id_of("H100g22p3") == "H100g22p3B" and a_id_of("H100g22p3B") == "H100g22p3"
    with pytest.raises(ValueError, match="scale"):
        plant_id(Role.DEV, 50)
    with pytest.raises(ValueError, match="B corpus id"):
        a_id_of("H100g22p3")


def test_targets_reproduce_and_stay_in_band() -> None:
    first = draw.draw_targets(3)
    assert first == draw.draw_targets(3) and first != draw.draw_targets(4)
    assert all(90 <= t <= 110 for k, t in first.items() if "1000" not in k)
    assert all(900 <= t <= 1100 for k, t in first.items() if "1000" in k)


@pytest.mark.parametrize(("n", "expected"), [(8, 6), (9, 7), (10, 8), (11, 9), (12, 10)])
def test_round_half_up_allocation(n: int, expected: int) -> None:
    assert draw.untagged_document_count(n) == expected
    assert draw.round_half_up(Fraction(5, 2)) == 3


def test_tagging_allocation_rules() -> None:
    docs = {plant_id(r, s, i): 1 for r, s, i in draw._DRAWN_SLOTS}
    docs["H1000g22p2"] = 10
    docs["VAL1000g22"] = 9
    flags = draw.allocate_tagging(1, docs)
    assert flags["VAL100g22"] == (True,)
    assert sum(flags[f"H100g22p{k}"][0] for k in range(1, 6)) == 4
    assert sum(flags["H1000g22p2"]) == 8 and sum(flags["VAL1000g22"]) == 7
    assert flags == draw.allocate_tagging(1, docs)


def test_plan_has_every_plant_and_flag_count(tmp_path: Path) -> None:
    plan = draw.draw_plan(5, _seeds(tmp_path), _sizer, _flags, PRIOR)
    assert len(plan.plants) == 2 + 2 + 2 * PLANTS_PER_SIZE
    assert plan.majority_code == {"descriptor": "NO", "tag": "NO"}
    assert all(p.n_documents == len(p.document_untagged) for p in plan.plants)
    assert plan.plant("D1000g22").document_untagged == (True,) * 10
    assert "H100g22p1" in draw.render_tables(_seeds(tmp_path), plan)


def test_size_beyond_five_sheets_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="within 5 sheets"):
        draw.draw_plan(5, _seeds(tmp_path), lambda t, s: (3, t + 6), _flags, PRIOR)


def test_draw_never_overwrites(tmp_path: Path) -> None:
    seeds = _seeds(tmp_path)
    plan = draw.draw_plan(5, seeds, _sizer, _flags, PRIOR)
    out = tmp_path / "prereg"
    draw.write_draw(out, seeds, plan, PRIOR)
    with pytest.raises(FileExistsError):
        draw.write_draw(out, seeds, plan, PRIOR)
    assert (out / "position_prior.json").read_bytes() == PRIOR.encode()
