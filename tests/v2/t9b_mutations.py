"""Plants broken on purpose for the T9b rule changes (TOG295 exceptions); see `t9_mutations.py`."""

from __future__ import annotations

from collections.abc import Callable

from t9_mutations import Broken, _copy, _with_graph

from plantgraph.benchmark.v2.rules.checks_inventory import check_inventory_once
from plantgraph.benchmark.v2.rules.control_graph import (
    LEVEL,
    PRESSURE,
    PRESSURE_DEPENDENT_ROLES,
    controllers_on,
    sensors_on,
)
from plantgraph.benchmark.v2.rules.view import RuleView


def break_farm_tank_without_level_transmitter(view: RuleView) -> Broken:
    """Remove the level transmitters of a tank that has no level loop: nobody watches it now."""
    graph, _ = _copy(view)
    for node, data in sorted(view.graph.nodes(data=True)):
        sensors = sensors_on(graph, node, LEVEL)
        if data["node_class"] == "Tank" and sensors and not controllers_on(graph, node, LEVEL):
            graph.remove_nodes_from(sensors)
            return _with_graph(view, graph), node
    raise AssertionError("no atmospheric tank with a level transmitter and no level loop found")


def _without_pressure_loop(view: RuleView, container: str) -> RuleView:
    graph, _ = _copy(view)
    graph.remove_nodes_from(controllers_on(graph, container, PRESSURE))
    return _with_graph(view, graph)


def break_flash_drum_without_pressure_loop(view: RuleView) -> Broken:
    """Remove the pressure controller of a pressure-dependent drum that floats on no neighbour."""
    for node in sorted(n for n, r in view.roles.items() if r in PRESSURE_DEPENDENT_ROLES):
        if not controllers_on(view.graph, node, PRESSURE):
            continue
        broken = _without_pressure_loop(view, node)
        if any(v.node_id == node for v in check_inventory_once(broken).violations):
            return broken, node
    raise AssertionError("no pressure-dependent drum with its own pressure loop found")


ALL: list[Callable[[RuleView], Broken]] = [
    break_farm_tank_without_level_transmitter,
    break_flash_drum_without_pressure_loop,
]
