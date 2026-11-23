"""Task T9c: a U3+U2 core closes its recycle-gas loop, and TOG295 finds a partner downstream.

Design 17.12. The loop tests run on the 30-sheet plants of seeds 1-5 (seeds 3 and 5 hold a core);
the partner search is tested on small hand-built graphs, so each rule of the search has a test of
its own and none needs a 1,000-sheet plant.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import networkx as nx
import pytest
from t9_support import SEEDS, units_for_30_sheets, view_v21, view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import GeneratedPlantV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.rules.checks_closure import check_stream_closure
from plantgraph.benchmark.v2.rules.checks_inventory import _floats_downstream
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import Relation


def _cores(plan: PlantPlanV2) -> list[tuple[str, str]]:
    """(compressor out-port part, reactor `recycle_gas` part) for every U3+U2 core of the plan."""
    pairs = []
    for before, unit in zip(plan.units, plan.units[1:], strict=False):
        if unit.instance.pattern == "U2" and before.instance.pattern == "U3":
            pairs.append(
                (
                    unit.instance.port("compressed").node_id,
                    before.instance.port("recycle_gas").node_id,
                )
            )
    return pairs


def _all_cores() -> list[tuple[int, str, str]]:
    return [(seed, *pair) for seed in SEEDS for pair in _cores(view_v22(seed).plan)]


# ---- the loop is closed (v2.2, handbook on) -----------------------------------------------------


def test_the_five_seeds_hold_cores_to_close() -> None:
    assert len(_all_cores()) >= 2


@pytest.mark.parametrize(("seed", "compressed", "recycle_gas"), _all_cores())
def test_the_compressor_gas_flows_into_the_reactor_recycle_port(
    seed: int, compressed: str, recycle_gas: str
) -> None:
    piping = view_v22(seed).piping
    assert piping.has_edge(compressed, recycle_gas)


@pytest.mark.parametrize(("seed", "compressed", "recycle_gas"), _all_cores())
def test_neither_end_of_a_closed_loop_is_an_open_end(
    seed: int, compressed: str, recycle_gas: str
) -> None:
    ends = {v.node_id for v in check_stream_closure(view_v22(seed)).violations}
    assert not ends & {compressed, recycle_gas}


def test_a_cut_recycle_loop_is_an_open_end_again() -> None:
    seed, compressed, recycle_gas = _all_cores()[0]
    view = view_v22(seed)
    graph = view.graph.copy()
    graph.remove_edge(compressed, recycle_gas)
    ends = {v.node_id for v in check_stream_closure(replace(view, graph=graph)).violations}
    assert recycle_gas in ends


# ---- nothing else moves: v2.1, the knobs off, the draws -----------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_v21_plant_leaves_the_compressor_port_open(seed: int) -> None:
    view = view_v21(seed)
    for compressed, recycle_gas in _cores(view.plan):
        assert not view.piping.has_edge(compressed, recycle_gas)


def test_the_v21_seeds_hold_cores_too_so_the_gate_test_is_not_vacuous() -> None:
    assert sum(len(_cores(view_v21(seed).plan)) for seed in SEEDS) >= 2


def test_with_the_handbook_off_a_v22_plant_equals_the_v21_plant() -> None:
    seed = 3
    n_units = units_for_30_sheets(seed)
    off = GeneratorConfigV22(seed=seed, n_units=n_units, handbook=HandbookKnobs.all_off())
    v21 = off.v21_equivalent()
    dump_off = plan_plant(off).model_dump(mode="json", exclude={"config"})
    dump_v21 = plan_plant(v21).model_dump(mode="json", exclude={"config"})
    assert dump_off == dump_v21


def test_closing_a_loop_makes_no_draw_so_the_unit_before_the_core_is_unchanged() -> None:
    """The reactor's own plan is not touched: only the later compressor's line carries the join."""
    seed = 3
    on = plan_plant(GeneratorConfigV22(seed=seed, n_units=units_for_30_sheets(seed)))
    for before, unit in zip(on.units, on.units[1:], strict=False):
        if unit.instance.pattern == "U2" and before.instance.pattern == "U3":
            line = next(
                line
                for line in unit.instance.plan.lines
                if line.line_number == unit.instance.port("compressed").line_number
            )
            assert line.dst_id == before.instance.port("recycle_gas").node_id


# ---- TOG295: the partner downstream -------------------------------------------------------------


def _chain_view(*parts: tuple[str, str, str]) -> tuple[RuleView, nx.DiGraph[str]]:
    """A view over a hand-built line `drum -> parts... -> end`, each part (id, class, tag).

    The last part gets a pressure loop (a transmitter and its controller); `_floats_downstream` is
    the only thing asked of it, so no plant is needed behind the view.
    """
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("drum", node_class="ScrubbingSeparator", tag="V-1")
    previous = "drum"
    for node_id, node_class, tag in parts:
        graph.add_node(node_id, node_class=node_class, tag=tag)
        graph.add_edge(previous, node_id, relation=Relation.SEND_TO.value, fluid_code="PG")
        previous = node_id
    graph.add_node("pt", node_class="PressureTransmitter", tag="PT-1", measured_variable="P")
    graph.add_node("pic", node_class="ProcessControlFunction", measured_variable="P")
    graph.add_edge(previous, "pt", relation=Relation.MEASURED_BY.value)
    graph.add_edge("pt", "pic", relation=Relation.SEND_SIGNAL_TO.value)
    view = RuleView(generated=cast(GeneratedPlantV2, None), graph=graph, roles={})
    return view, graph


_PIPE_VALVE = ("gate", "GateValve", "BV-1")
_SEPARATOR = ("sep", "Separator", "V-2")


def test_the_nearest_pressure_loop_downstream_is_the_partner() -> None:
    view, _ = _chain_view(_PIPE_VALVE, _SEPARATOR)
    assert _floats_downstream(view, "drum") == "sep"


def test_a_throttling_control_valve_cuts_the_route() -> None:
    view, _ = _chain_view(("hcv", "GlobeValve", "HCV-1"), _SEPARATOR)
    assert _floats_downstream(view, "drum") is None


def test_a_split_valve_is_not_a_throttle() -> None:
    view, _ = _chain_view(("tv", "GlobeValve", "HCV-2"), _SEPARATOR)
    view._memo["split_valves"] = frozenset({"tv"})
    assert _floats_downstream(view, "drum") == "sep"


def test_a_pump_sets_its_own_pressure_so_it_cuts_the_route() -> None:
    view, _ = _chain_view(("pump", "CentrifugalPump", "P-1"), _SEPARATOR)
    assert _floats_downstream(view, "drum") is None


def test_an_item_with_no_pressure_loop_of_its_own_is_passed_like_pipe() -> None:
    view, _ = _chain_view(("reactor", "PressureVessel", "R-1"), _SEPARATOR)
    assert _floats_downstream(view, "drum") == "sep"


def test_the_route_need_not_be_gas_all_the_way() -> None:
    view, graph = _chain_view(_PIPE_VALVE, _SEPARATOR)
    graph.edges["gate", "sep"]["fluid_code"] = "P"  # a liquid stretch passes the pressure too
    assert _floats_downstream(view, "drum") == "sep"


def test_a_utility_pipe_is_not_followed() -> None:
    view, graph = _chain_view(_PIPE_VALVE, _SEPARATOR)
    graph.edges["gate", "sep"]["fluid_code"] = "CWS"  # cooling water leads to another network
    assert _floats_downstream(view, "drum") is None


def test_a_pressure_loop_upstream_of_the_drum_is_not_found_by_the_downstream_search() -> None:
    view, graph = _chain_view(_PIPE_VALVE)
    graph.add_node("before", node_class="TubularHeatExchanger", tag="E-1")
    graph.add_edge("before", "drum", relation=Relation.SEND_TO.value, fluid_code="PG")
    graph.add_edge("before", "pt", relation=Relation.MEASURED_BY.value)  # the same loop, upstream
    graph.remove_edge("gate", "pt")  # so only the upstream exchanger carries the loop
    assert _floats_downstream(view, "drum") is None
