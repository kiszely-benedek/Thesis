"""The instrument helpers: reading and renumbering plan parts, switch letters, cascade loop tags."""

from __future__ import annotations

import networkx as nx
import pytest
from trim_harness import STYLE, TrimHarness, convention

from plantgraph.adapters.pydexpi_loop_tags import assign_loop_tags
from plantgraph.benchmark.v2 import trims_valves
from plantgraph.benchmark.v2.instrument_draft import (
    node_with_role,
    parsed_tag_of,
    part_of,
    parts_of,
    with_part_number,
)
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind

_PSGF = "ProcessSignalGeneratingFunction"
_PCF = "ProcessControlFunction"


def test_part_of_finds_a_part_in_the_run_and_in_the_lines_of_a_closed_plan() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0))
    plan = trims_valves.control_valve(h.ctx, STYLE, "F")
    body = part_of(plan, "body")
    assert body.node_id in parts_of(plan)
    closed = h.write(plan, h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK"))
    assert part_of(closed, "body") == body


def test_part_of_names_the_ports_it_knows_when_the_port_is_missing() -> None:
    plan = trims_valves.bare_control_valve(TrimHarness().ctx, STYLE, "F")
    with pytest.raises(ValueError, match=r"expected a port in \['body'\], got 'valve'"):
        part_of(plan, "valve")


def test_with_part_number_changes_the_number_and_keeps_the_letters() -> None:
    h = TrimHarness()
    plan = trims_valves.flow_element(h.ctx, STYLE, "liquid")
    element = part_of(plan, "element")
    renamed = with_part_number(plan, element.node_id, 77)
    assert part_of(renamed, "element").tag == "FE-1077"
    assert part_of(plan, "element").tag == element.tag  # the plan is frozen: a copy was made


def test_with_part_number_also_renames_a_part_inside_a_closed_line() -> None:
    h = TrimHarness()
    plan = h.write(
        trims_valves.flow_element(h.ctx, STYLE, "gas"),
        h.equipment("PressureVessel", "V"),
        h.equipment("Tank", "TK"),
    )
    element = part_of(plan, "element")
    assert part_of(with_part_number(plan, element.node_id, 5), "element").tag == "FE-1005"


def test_with_part_number_refuses_an_unknown_id_and_an_untagged_part() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0, p_cv_reducers=1.0))
    plan = trims_valves.control_valve(h.ctx, STYLE, "F")
    with pytest.raises(ValueError, match="expected an inline part"):
        with_part_number(plan, "nope", 1)
    reducer = node_with_role_first(plan, "cv_reducer")
    with pytest.raises(ValueError, match="expected a loop tag"):
        with_part_number(plan, reducer, 1)


def node_with_role_first(plan: TrimPlan, role: str) -> str:
    return sorted(node_id for node_id, r in plan.roles.items() if r == role)[0]


def test_parsed_tag_of_refuses_a_part_of_another_unit_or_without_a_tag() -> None:
    part = LineItemSpec(node_id="x", node_class="BallValve", tag="XV-2001")
    with pytest.raises(ValueError, match="in unit 2, expected unit 1"):
        parsed_tag_of(part, 1)
    with pytest.raises(ValueError, match="expected a loop tag"):
        parsed_tag_of(LineItemSpec(node_id="y", node_class="PipeTee"), 1)


def test_node_with_role_needs_exactly_one_node() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0, p_cv_reducers=1.0))
    plan = trims_valves.control_valve(h.ctx, STYLE, "L")
    assert node_with_role(plan, "control_valve_body") == plan.ports["body"]
    with pytest.raises(ValueError, match="exactly one node with role 'cv_reducer'"):
        node_with_role(plan, "cv_reducer")  # a station has two reducers
    with pytest.raises(ValueError, match="exactly one node with role 'absent'"):
        node_with_role(plan, "absent")


@pytest.mark.parametrize("letters", ["LSH", "LSL", "PSHH", "CSHH"])
def test_a_switch_element_is_a_valid_sensor(letters: str) -> None:
    """Point-level and trip switches (`LSH`) are sensors that also switch."""
    assert item_kind(_PSGF, letters) is ItemKind.SWITCH


def test_a_sensor_with_unfit_letters_is_still_refused() -> None:
    with pytest.raises(ValueError, match="a sensor's letters end in T, E, I or G"):
        item_kind(_PSGF, "LIC")


def test_cascade_master_and_slave_keep_their_own_loop_tags_in_either_id_order() -> None:
    """`assign_loop_tags` must not let one controller overwrite the other (S22 depends on it)."""
    for master_id, slave_id in (("a-master", "z-slave"), ("z-master", "a-slave")):
        graph: nx.DiGraph[str] = nx.DiGraph()
        for node_id, node_class, tag in (
            (master_id, _PCF, "TIC-1001"),
            (slave_id, _PCF, "FIC-1002"),
            ("mt", _PSGF, "TT-1001"),
            ("st", _PSGF, "FT-1002"),
        ):
            graph.add_node(node_id, node_class=node_class, tag=tag)
        graph.add_edges_from([("mt", master_id), (master_id, slave_id), ("st", slave_id)])
        assign_loop_tags(graph)
        assert graph.nodes[master_id]["loop_tag"] == "TIC-1001"
        assert graph.nodes[slave_id]["loop_tag"] == "FIC-1002"
        assert graph.nodes["mt"]["loop_tag"] == "TIC-1001"
        assert graph.nodes["st"]["loop_tag"] == "FIC-1002"
