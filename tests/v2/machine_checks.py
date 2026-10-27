"""Checks for motor-driven machines: S19, S20 and the agitator (pid-vocabulary section 8).

Not a test module (no `test_` prefix). `check_s19` reads a graph; `check_s20` reads an instance.
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.sheets import assign_unit_sheets
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

_AEF = "ActuatingElectricalFunction"


def check_s19(graph: nx.DiGraph[str]) -> int:
    """S19: control into equipment comes from an AEF; each AEF has one target and a signal source.

    Returns the number of AEFs checked.
    """
    for source, target, data in graph.edges(data=True):
        into_equipment = graph.nodes[target]["node_class"] in EQUIPMENT_CLASSES
        if data["relation"] == Relation.CONTROL.value and into_equipment:
            assert graph.nodes[source]["node_class"] == _AEF, f"{source} controls machine {target}"
    actuators = [n for n, d in graph.nodes(data=True) if d["node_class"] == _AEF]
    for actuator in actuators:
        controls = _relations(graph.out_edges(actuator, data=True), Relation.CONTROL)
        feeds = _relations(graph.in_edges(actuator, data=True), Relation.SEND_SIGNAL_TO)
        assert len(controls) == 1, f"{actuator} controls {len(controls)} machines"
        assert feeds, f"{actuator} has no signal source"
    return len(actuators)


def _relations(
    edges: Iterable[tuple[str, str, dict[str, object]]], relation: Relation
) -> list[tuple[str, str]]:
    return [(s, t) for s, t, d in edges if d["relation"] == relation.value]


def check_s20(instance: PatternInstance, unit_no: int = 1) -> int:
    """S20: no `has_agitator` edge and no AEF `control` edge crosses a sheet of the unit.

    Uses the planner's sheet assignment for the instance. Returns the number of edges checked.
    """
    sheets = assign_unit_sheets(unit_no, instance, SheetKnobs()).sheet_of
    aefs = {i.node_id for i in instance.plan.instruments if i.node_class == _AEF}
    checked = 0
    for link in instance.plan.links:
        is_agitator = link.relation is Relation.HAS_AGITATOR
        is_machine_control = link.relation is Relation.CONTROL and link.source_id in aefs
        if is_agitator or is_machine_control:
            assert sheets[link.source_id] == sheets[link.target_id], f"{link} crosses sheets"
            checked += 1
    return checked
