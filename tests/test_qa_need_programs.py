"""The fixed program of each need label, by hand on the plant-API toy (design §4.1)."""

from __future__ import annotations

import pytest

from plantgraph.qa.anchors import Anchors, TagAnchor, UnitAnchor
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.programs import NeedPreconditionError, NeedSelection, run_program
from plantgraph.qa.plant_api.primitives import PlantApi
from qa_plant_api_toy import NC, build_graph, toy_graph

# The toy: T1 -> BV1 ~ P1 -> CHV -> V1 ~ BV1 (a cycle), P1 -> GV2 ~ V2; signals T1 .. FV -> BV1.
# BV1 and GV2 are operated valves; unit 1 holds everything but GV2 and V2 (unit 2).


def _anchors(*tags: str, units: tuple[str, ...] = ()) -> Anchors:
    return Anchors(
        tags=tuple(TagAnchor(text=tag, position=i, occurrences=()) for i, tag in enumerate(tags)),
        units=tuple(UnitAnchor(unit_id=unit, position=i) for i, unit in enumerate(units)),
    )


def _run(label: NeedLabel, anchors: Anchors) -> NeedSelection:
    return run_program(label, anchors, PlantApi(toy_graph(), max_items=10**9))


def _tags(selection: NeedSelection) -> list[str | None]:
    return [selected.item.tag for selected in selection.items]


def _distance(selection: NeedSelection) -> dict[str | None, int]:
    return {selected.item.tag: selected.distance for selected in selection.items}


def test_item_selects_nothing_beyond_the_anchors() -> None:
    selection = _run(NeedLabel.ITEM, _anchors("P1"))

    assert selection.items == () and selection.edges == () and selection.program == ()


def test_neighbours_follow_one_flow_hop_in_the_named_direction() -> None:
    down = _run(NeedLabel.NEIGHBOURS_DOWNSTREAM, _anchors("P1"))
    up = _run(NeedLabel.NEIGHBOURS_UPSTREAM, _anchors("P1"))

    assert set(_tags(down)) == {"P1", "CHV", "GV2"}  # the anchor itself is a start item
    assert set(_tags(up)) == {"P1", "BV1"}
    assert down.program == ('neighbours("P1", downstream, flow)',)


def test_the_signal_chain_stops_after_three_hops() -> None:
    selection = _run(NeedLabel.SIGNAL_CHAIN, _anchors("T1"))

    # T1 -measured_by-> FT -> FIC -> FV is three hops; FV -control-> BV1 would be a fourth
    assert _distance(selection) == {"T1": 0, "FT": 1, "FIC": 2, "FV": 3}


def test_path_lists_the_route_and_ranks_its_middle_as_farthest() -> None:
    selection = _run(NeedLabel.PATH, _anchors("T1", "V2"))

    assert _tags(selection) == ["T1", "V2", "BV1", "GV2", "P1"]  # nearest an end first
    assert _distance(selection) == {"T1": 0, "V2": 0, "BV1": 1, "GV2": 1, "P1": 2}
    assert selection.program == ('path("T1", "V2")',)


def test_path_tries_the_other_direction_when_flow_only_goes_that_way() -> None:
    selection = _run(NeedLabel.PATH, _anchors("V2", "T1"))

    assert selection.program == ('path("V2", "T1")', 'path("T1", "V2")')
    assert set(_tags(selection)) == {"T1", "BV1", "P1", "GV2", "V2"}


def test_path_with_no_route_either_way_selects_nothing() -> None:
    selection = _run(NeedLabel.PATH, _anchors("FT", "V2"))  # FT has signal edges only

    assert selection.items == ()
    assert len(selection.program) == 2


def test_upstream_to_the_first_valve_includes_the_valve_and_goes_no_further() -> None:
    selection = _run(NeedLabel.UPSTREAM_TO_FIRST_VALVE, _anchors("V1"))

    # V1 <- CHV <- P1 <- BV1 (operated: included, not expanded, so T1 and the cycle stay out)
    assert _distance(selection) == {"V1": 0, "CHV": 1, "P1": 2, "BV1": 3}


def test_downstream_to_the_first_valve_stops_at_each_branch_valve() -> None:
    selection = _run(NeedLabel.DOWNSTREAM_TO_FIRST_VALVE, _anchors("P1"))

    # the branch through GV2 stops at GV2; V2 beyond it is not reached
    assert set(_tags(selection)) == {"P1", "CHV", "V1", "BV1", "GV2"}


def test_everything_downstream_is_restricted_to_the_unit_when_one_is_named() -> None:
    free = _run(NeedLabel.DOWNSTREAM_ALL, _anchors("P1"))
    inside = _run(NeedLabel.DOWNSTREAM_ALL, _anchors("P1", units=("1",)))

    assert {"GV2", "V2"} <= set(_tags(free))
    assert set(_tags(inside)) == {"P1", "CHV", "V1", "BV1"}  # unit 2 is never entered
    assert "walk_only={unit: 1}" in inside.program[0]


def test_everything_upstream_walks_back_to_the_sources() -> None:
    selection = _run(NeedLabel.UPSTREAM_ALL, _anchors("V2"))

    assert _distance(selection)["T1"] == 4  # V2 <- GV2 <- P1 <- BV1 <- T1


def test_unit_scope_is_the_unit_plus_the_lines_crossing_its_boundary() -> None:
    selection = _run(NeedLabel.UNIT_SCOPE, _anchors(units=("2",)))

    assert _distance(selection) == {"GV2": 0, "V2": 0, "P1": 1}  # P1 feeds GV2 from unit 1


@pytest.mark.parametrize(
    "label",
    [
        NeedLabel.NEIGHBOURS_DOWNSTREAM,
        NeedLabel.SIGNAL_CHAIN,
        NeedLabel.UPSTREAM_TO_FIRST_VALVE,
        NeedLabel.DOWNSTREAM_ALL,
    ],
)
def test_a_traversal_without_a_tag_anchor_fails_its_precondition(label: NeedLabel) -> None:
    with pytest.raises(NeedPreconditionError, match="at least 1 tag anchor"):
        _run(label, _anchors(units=("1",)))


def test_path_with_one_tag_and_unit_scope_without_a_unit_fail_their_preconditions() -> None:
    with pytest.raises(NeedPreconditionError, match="at least 2 tag anchor"):
        _run(NeedLabel.PATH, _anchors("T1"))
    with pytest.raises(NeedPreconditionError, match="at least 1 unit anchor"):
        _run(NeedLabel.UNIT_SCOPE, _anchors("T1"))


def test_a_plant_without_operated_valves_fails_the_first_valve_precondition() -> None:
    items = {"T1": (NC.TANK.value, "1", ("S1",)), "P1": (NC.CENTRIFUGAL_PUMP.value, "1", ("S1",))}
    api = PlantApi(build_graph(items, [("T1", "send_to", "P1", ())]))

    with pytest.raises(NeedPreconditionError, match="OperatedValve"):
        run_program(NeedLabel.UPSTREAM_TO_FIRST_VALVE, _anchors("P1"), api)


def test_generic_has_no_program() -> None:
    with pytest.raises(ValueError, match="need label with a program"):
        _run(NeedLabel.GENERIC, _anchors("T1"))
