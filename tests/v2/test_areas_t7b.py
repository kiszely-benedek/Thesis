"""Task T7b (design 17.14 N2, N3): headers per area, interarea only between areas, relief ties.

An **area** is a run of `trains_per_area` consecutive trains. The plants are the 30-sheet plants of
`t9_support`, planned with a small `trains_per_area` so a 30-sheet plant has several areas.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import replace
from typing import Any

import pytest
from network_support import view_one_train_per_area
from t9_support import SEEDS, units_for_30_sheets

from plantgraph.benchmark.v2 import planner
from plantgraph.benchmark.v2.composition_kinds import sheets_per_area
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.documents import DocumentRecord
from plantgraph.benchmark.v2.network_models import (
    INTERAREA,
    area_of_train,
    first_train_of_area,
    network_unit_no,
)
from plantgraph.benchmark.v2.network_units import joins_between_trains
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.relief_ends import assert_no_open_relief
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.registry import resolve_check
from plantgraph.benchmark.v2.streams import handbook_train_rng, train_rng
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.vocabulary import draw_train_conventions


def _plan(seed: int, trains_per_area: int, capacity: int = 16) -> PlantPlanV2:
    knobs = HandbookKnobs(trains_per_area=trains_per_area, max_tie_ins_per_network_sheet=capacity)
    config = GeneratorConfigV22(seed=seed, n_units=units_for_30_sheets(seed), handbook=knobs)
    return plan_plant(config)


def _train_of_node(plan: PlantPlanV2) -> dict[str, int]:
    return {n: u.slot.train_no for u in plan.units for n in u.sheets.sheet_of}


# ---- areas and numbering ------------------------------------------------------------------


def test_the_area_of_a_train_depends_on_the_train_alone() -> None:
    assert [area_of_train(t, 10) for t in (1, 10, 11, 20, 21)] == [1, 1, 2, 2, 3]
    assert first_train_of_area(1, 10) == 1
    assert first_train_of_area(3, 10) == 21


def test_unit_numbers_are_9000_plus_10_area_plus_the_service_index() -> None:
    assert network_unit_no(1, "FL") == 9010
    assert network_unit_no(2, "CHD") == 9021
    assert network_unit_no(12, "FG") == 9127
    assert network_unit_no(0, INTERAREA) == 9008  # the plant interarea unit: area slot 0


@pytest.mark.parametrize("seed", SEEDS)
def test_a_header_unit_serves_the_trains_of_its_area_only(seed: int) -> None:
    plan = _plan(seed, 2)
    train_of = _train_of_node(plan)
    headers = [u for u in plan.network_units if not u.is_interarea]
    assert len({(u.area_no, u.service) for u in headers}) == len(headers)  # one per (area, service)
    for unit in headers:
        assert unit.train_no == first_train_of_area(unit.area_no, 2)
        tied = [n for line in unit.plan.lines for n in (line.src_id, line.dst_id) if n in train_of]
        assert tied
        assert {area_of_train(train_of[n], 2) for n in tied} == {unit.area_no}


def test_a_plant_of_one_area_has_no_interarea_sheet() -> None:
    plan = _plan(1, 10)
    assert plan.network_units and all(not u.is_interarea for u in plan.network_units)
    assert {u.area_no for u in plan.network_units} == {1}


# ---- interarea -------------------------------------------------------------------------------


def _direct_joins(plan: PlantPlanV2) -> set[tuple[int, int]]:
    """(source train, destination train) of every join still drawn as a direct process line."""
    train_of = _train_of_node(plan)
    found = set()
    for unit in plan.units:
        for line in unit.instance.plan.lines:
            if line.src_id in train_of and line.items:
                destination = train_of.get(line.items[0].node_id)
                if destination is not None and train_of[line.src_id] != destination:
                    found.add((train_of[line.src_id], destination))
    return found


@pytest.mark.parametrize("seed", SEEDS)
def test_only_a_line_between_areas_passes_the_plant_interarea_unit(seed: int) -> None:
    plan = _plan(seed, 2)
    (interarea,) = [u for u in plan.network_units if u.is_interarea]
    assert interarea.unit_no == 9008 and interarea.area_no == 0
    train_of = _train_of_node(plan)
    carried = {
        (train_of[line.src_id or ""], train_of[line.dst_id or ""]) for line in interarea.plan.lines
    }
    assert carried and all(area_of_train(a, 2) != area_of_train(b, 2) for a, b in carried)
    # a join inside one area is still a direct process line, as v2.1 drew it
    direct = _direct_joins(plan)
    assert direct and all(area_of_train(a, 2) == area_of_train(b, 2) for a, b in direct)


def test_with_one_train_per_area_every_join_between_trains_is_an_interarea_line() -> None:
    plan = _plan(3, 1)
    (interarea,) = [u for u in plan.network_units if u.is_interarea]
    assert len(interarea.plan.lines) == max(u.slot.train_no for u in plan.units) - 1
    assert _direct_joins(plan) == set()


def test_an_interarea_sheet_holds_at_most_the_capacity_and_the_rest_goes_on() -> None:
    plan = _plan(1, 1, capacity=2)
    (interarea,) = [u for u in plan.network_units if u.is_interarea]
    per_sheet = Counter(
        interarea.sheets.sheet_of[line.items[0].node_id] for line in interarea.plan.lines
    )
    assert interarea.sheets.sheet_count > 1
    assert max(per_sheet.values()) <= 2


def test_after_the_pass_only_joins_inside_an_area_are_left_between_trains() -> None:
    plan = _plan(2, 2)
    instances = [u.instance for u in plan.units]
    left = joins_between_trains(instances, [u.slot.train_no for u in plan.units])
    assert left and all(
        area_of_train(j.source_train, 2) == area_of_train(j.destination_train, 2) for j in left
    )


# ---- relief devices (N3) ---------------------------------------------------------------------


def _relief_plan(
    fluid: str, role: str = "psv", node_class: str = "SpringLoadedGlobeSafetyValve"
) -> TrimPlan:
    line = LineSpec(
        line_number=f"4-{fluid}-10001-A1A-N",
        fluid_code=fluid,
        unit_no=1,
        src_id="vessel",
        dst_id=None,
        items=(LineItemSpec(node_id="relief", node_class=node_class),),
    )
    return TrimPlan(lines=(line,), roles={"relief": role})


def test_a_relief_device_ending_open_on_a_hydrocarbon_line_is_an_error() -> None:
    with pytest.raises(ValueError, match="found 1 that end open"):
        assert_no_open_relief([_relief_plan("FL")])
    with pytest.raises(ValueError, match="found 1 that end open"):
        assert_no_open_relief([_relief_plan("FL", "reactor_rupture_disc", "RuptureDisc")])


def test_a_water_or_steam_relief_may_end_open() -> None:
    assert_no_open_relief([_relief_plan("CWR"), _relief_plan("MPS", "psv_outlet_block")])


def test_a_relief_end_that_a_line_of_another_plan_continues_is_not_open() -> None:
    feeder = LineSpec(
        line_number="4-FL-10002-A1A-N", fluid_code="FL", unit_no=1, src_id="relief", dst_id="tee"
    )
    assert_no_open_relief([_relief_plan("FL"), TrimPlan(lines=(feeder,))])


def test_every_rupture_disc_is_in_the_relief_set_of_tog32() -> None:
    """With the flare header cut away, TOG32 reports each rupture disc: it is in its relief set."""
    seen = 0
    for seed in SEEDS:
        view = view_one_train_per_area(seed)
        discs = {n for n, r in view.roles.items() if r == "reactor_rupture_disc"}
        flare = {
            n
            for u in view.plan.network_units
            if u.service == "FL"
            for n, r in u.plan.roles.items()
            if r == "header_tee"
        }
        graph = view.graph.copy()
        graph.remove_nodes_from(flare)
        cut = resolve_check(rule_by_id("TOG32-NETWORK-SHEETS"))(replace(view, graph=graph))
        assert discs <= {v.node_id for v in cut.violations}
        seen += len(discs)
    assert seen, "no plant of seeds 1-5 has a reactor rupture disc"


# ---- process draws and the size search -------------------------------------------------------

#: sha256 of the process plans before the network pass; recorded on the T7 commit (d8914f8)
_PRE_TIE_DIGESTS = {
    (1, 20): "885f6d7625d77d93e141662c5405e911b9c959539d35fe2ed15876e49cf6f3c2",
    (7, 60): "00dd5863a1b289770535894da200e1adb1c0d16f114e9db55ade3ee5124557fc",
}


def _legacy_documents(config: GeneratorConfigV22, n_trains: int) -> tuple[DocumentRecord, ...]:
    """What T7 drew per train, as one document per train: its own letter, naming and PV coin."""
    return tuple(
        DocumentRecord(
            document_no=train,
            first_train=train,
            last_train=train,
            conventions=draw_train_conventions(train_rng(config.seed, train)),
            manual_valves_untagged=False,
            pv_without_bypass=handbook_train_rng(config.seed, train, "pv_no_bypass").random() < 0.5,
        )
        for train in range(1, n_trains + 1)
    )


@pytest.mark.parametrize(("seed", "n_units"), sorted(_PRE_TIE_DIGESTS))
def test_the_process_draws_other_than_the_document_ones_are_those_of_t7(
    seed: int, n_units: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T6 changes only the per-document draws and the reducer weight; give those T7's values back
    (one document per train, no untagging, `p_pump_reducers` 0.5) and every plan is T7's."""
    captured: list[str] = []

    def grab(
        config: Any, slots: Any, instances: Any, trims: Any, trains: Any, documents: Any, decks: Any
    ) -> Any:
        captured.extend(i.plan.model_dump_json() for i in instances)
        return list(instances), []

    monkeypatch.setattr(planner, "add_networks", grab)
    monkeypatch.setattr(planner, "draw_documents", _legacy_documents)
    knobs = HandbookKnobs(trains_per_area=1, p_pump_reducers=0.5)
    plan_plant(GeneratorConfigV22(seed=seed, n_units=n_units, handbook=knobs))
    digest = hashlib.sha256("\n".join(captured).encode()).hexdigest()
    assert digest == _PRE_TIE_DIGESTS[seed, n_units]


def test_the_sheets_of_the_areas_add_up_to_the_plant_less_its_interarea_sheets() -> None:
    plan = _plan(4, 2)
    interarea = sum(u.sheets.sheet_count for u in plan.network_units if u.is_interarea)
    assert sum(sheets_per_area(plan, 2).values()) == plan.sheet_count - interarea
