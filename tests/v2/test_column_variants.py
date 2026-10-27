"""U1 variants (design 7.2, pid-vocabulary 5.2 and 13.3): vacuum devices, condensate, sheet layouts.

Same method as `test_column.py`: one column per test, the DEXPI round trip and the invariants S4,
S7, S8, S9, S22 through `column(...)`, then the rule the test names. S11 is the A/B ejector pairs.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources
from pattern_checks import flow_graph, located_on, nodes_of_class, nodes_with_letters
from pattern_harness import PatternHarness, config_with
from test_column import column, letters, one
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.patterns.column import build_distillation_column
from plantgraph.benchmark.v2.sheets import assign_unit_sheets
from plantgraph.graph.schema import Relation

_AIR = {"U1.vacuum": ("air_ejector",)}
_RING = {"U1.vacuum": ("liquid_ring",)}
_NO_PREHEATER = {"U1.feed_preheater": ("absent",)}  # one steam exchanger: the reboiler


def _inbound_services(graph: nx.DiGraph[str], node_id: str) -> set[str]:
    return {d.get("fluid_code", "") for _, _, d in graph.in_edges(node_id, data=True)}


def _tee_next_to(graph: nx.DiGraph[str], node_id: str, downstream: bool) -> str:
    """Walk the vapour piping (service `PG`) from `node_id` to the tee that splits or joins."""
    current = node_id
    while True:
        edges = (
            graph.out_edges(current, data=True)
            if downstream
            else graph.in_edges(current, data=True)
        )
        (current,) = [
            (target if downstream else source)
            for source, target, data in edges
            if data["relation"] == Relation.SEND_TO.value and data.get("fluid_code") == "PG"
        ]
        if graph.nodes[current]["node_class"] == "PipeTee":
            return current


# ---- air ejector --------------------------------------------------------------------------------


def test_s11_the_air_ejectors_are_two_spared_pairs_between_one_split_and_one_merge_tee() -> None:
    _, instance, graph = column(_AIR)
    ejectors = nodes_of_class(graph, "AirEjector")
    assert len(ejectors) == 4
    tags = sorted(graph.nodes[e]["tag"] for e in ejectors)
    assert [t[-1] for t in tags] == ["A", "B", "A", "B"] and tags[0][:-1] == tags[1][:-1]
    by_number: dict[str, list[str]] = {}
    for ejector in ejectors:
        by_number.setdefault(graph.nodes[ejector]["tag"][:-1], []).append(ejector)
    for first, second in by_number.values():
        for downstream in (False, True):
            assert _tee_next_to(graph, first, downstream) == _tee_next_to(graph, second, downstream)
    assert {instance.plan.roles[e] for e in ejectors} == {"air_ejector"}


def test_the_ejectors_have_no_motor_and_each_has_a_motive_steam_stub_with_a_relief_valve() -> None:
    h, instance, graph = column(_AIR)
    ejectors = nodes_of_class(graph, "AirEjector")
    assert not any(sources(graph, e, Relation.CONTROL) for e in ejectors)  # no AEF: no motor
    for ejector in ejectors:
        assert "MPS" in _inbound_services(graph, ejector)
    reliefs = [
        n
        for n, role in instance.plan.roles.items()
        if role == "steam_stub_psv" and graph.nodes[n]["node_class"].endswith("SafetyValve")
    ]
    assert len(reliefs) == 4
    assert all(graph.out_degree(r) == 0 for r in reliefs)  # open end: relief to the atmosphere
    assert {d["fluid_code"] for _, _, d in graph.in_edges(reliefs[0], data=True)} == {"MPS"}


def test_the_vapour_passes_stage_one_the_intercondenser_and_stage_two_then_a_silencer() -> None:
    _, instance, graph = column(_AIR)
    ejectors = sorted(nodes_of_class(graph, "AirEjector"))
    first, second = ejectors[0], ejectors[2]
    cooler = one(instance, "intercondenser")
    (pressure_valve,) = nodes_with_letters(graph, "PV")
    (silencer,) = nodes_of_class(graph, "Silencer")
    flow = flow_graph(graph)
    assert nx.has_path(flow, pressure_valve, first) and nx.has_path(flow, first, cooler)
    assert nx.has_path(flow, cooler, second) and nx.has_path(flow, second, silencer)
    assert graph.out_degree(silencer) == 0  # the exhaust ends open
    assert graph.nodes[cooler]["node_class"] == "TubularHeatExchanger"
    assert "CWS" in _inbound_services(graph, cooler)


def test_the_air_ejector_system_is_drawn_with_the_condenser_and_the_drum() -> None:
    _, instance, graph = column(_AIR, patterns={"p_column_combined": 0.0})
    group = instance.drawing_group_of
    for role in ("air_ejector", "intercondenser"):
        assert {group[n] for n in ids_with_role(instance.plan, role)} == {
            group[one(instance, "reflux_drum")]
        }


# ---- liquid-ring pump ---------------------------------------------------------------------------


def test_the_liquid_ring_pump_is_a_motor_driven_rotary_compressor_with_its_trims() -> None:
    _, instance, graph = column(_RING, density={"p_motor_current": 1.0})
    (pump,) = nodes_of_class(graph, "RotaryCompressor")
    assert not nodes_of_class(graph, "AirEjector")
    (actuator,) = sources(graph, pump, Relation.CONTROL)  # HS -> AEF -> machine
    assert graph.nodes[actuator]["node_class"] == "ActuatingElectricalFunction"
    assert any(letters(graph, s) == "IT" for s in located_on(graph, pump))
    assert nodes_of_class(graph, "ConicalStrainer") and nodes_of_class(graph, "CheckValve")
    (pressure_valve,) = nodes_with_letters(graph, "PV")
    assert nx.has_path(flow_graph(graph), pressure_valve, pump)
    assert (
        instance.drawing_group_of[pump] == instance.drawing_group_of[one(instance, "reflux_drum")]
    )


# ---- condensate (the reboiler's steam return) ---------------------------------------------------


def test_trap_mode_returns_condensate_through_one_steam_trap_and_no_drain_pot() -> None:
    _, instance, graph = column(_NO_PREHEATER, trims={"condensate_mode_weights": {"trap": 1.0}})
    assert len(nodes_of_class(graph, "SteamTrap")) == 1
    assert not ids_with_role(instance.plan, "condensate_drain_pot")


def test_trap_station_mode_puts_the_trap_between_two_blocks_with_a_bypass() -> None:
    _, instance, graph = column(
        _NO_PREHEATER, trims={"condensate_mode_weights": {"trap_station": 1.0}}
    )
    assert len(nodes_of_class(graph, "SteamTrap")) == 1
    (tee_in,) = ids_with_role(instance.plan, "trap_tee_in")
    (tee_out,) = ids_with_role(instance.plan, "trap_tee_out")
    assert len(list(nx.all_simple_paths(flow_graph(graph), tee_in, tee_out))) == 2  # trap, bypass


def test_drain_pot_mode_adds_a_pot_with_a_level_loop_a_leak_trip_and_a_conductivity_gauge() -> None:
    _, instance, graph = column(
        cards=_NO_PREHEATER,
        trims={"condensate_mode_weights": {"drain_pot": 1.0}},
    )
    pot = one(instance, "condensate_drain_pot")
    assert instance.drawing_group_of[pot] == instance.drawing_group_of[one(instance, "reboiler")]
    on_pot = {letters(graph, s) for s in located_on(graph, pot)}
    assert {"LT", "CT"} <= on_pot
    assert nodes_with_letters(graph, "CSHH") and nodes_with_letters(graph, "CI")


# ---- sheet layouts ------------------------------------------------------------------------------


def _groups(instance: object) -> dict[str, set[str]]:
    """Group name -> the roles it holds."""
    result: dict[str, set[str]] = {}
    plan = instance.plan  # type: ignore[attr-defined]
    for node, group in instance.drawing_group_of.items():  # type: ignore[attr-defined]
        result.setdefault(group, set()).add(plan.roles[node])
    return result


def test_two_sheet_layout_puts_the_column_and_reboiler_apart_from_the_condenser_and_drum() -> None:
    _, instance, _ = column(_NO_PREHEATER, patterns={"p_column_combined": 0.0})
    groups = _groups(instance)
    assert groups["G1"] == {"column", "reboiler", "bottoms_pump"}
    assert {"condenser", "reflux_drum", "reflux_pump"} <= groups["G2"]
    assert "layout=two_sheets" in instance.variant and not instance.pinned_groups


def test_combined_layout_is_one_group_and_one_sheet() -> None:
    _, instance, _ = column({"U1.vacuum": ("none",)}, patterns={"p_column_combined": 1.0})
    assert set(instance.drawing_group_of.values()) == {"G1"}
    assert "layout=combined" in instance.variant
    assert assign_unit_sheets(1, instance, SheetKnobs()).sheet_count == 1


def test_a_combined_column_with_too_much_equipment_falls_back_to_two_sheets() -> None:
    """Three pumps per set, a preheater, two drain pots and a two-stage ejector exceed 16 items."""
    _, instance, _ = column(
        {**_AIR, "U1.feed_preheater": ("present",)},
        patterns={"p_column_combined": 1.0, "p_triple_pump_set": 1.0, "p_single_pump": 0.0},
        trims={"condensate_mode_weights": {"drain_pot": 1.0}},
    )
    assert len(instance.plan.equipment) > 16
    assert set(instance.drawing_group_of.values()) == {"G1", "G2"}
    assert "layout=two_sheets" in instance.variant


@pytest.mark.parametrize("combined", [0.0, 1.0])
def test_own_sheet_pump_sets_get_pinned_groups_after_the_column_groups(combined: float) -> None:
    _, instance, _ = column(
        {"pump_set.group": ("own_sheet",), "U1.vacuum": ("none",)},
        patterns={"p_column_combined": combined},
    )
    groups = _groups(instance)
    first_pump_group = 2 if combined else 3
    assert groups[f"G{first_pump_group}"] == {"reflux_pump"}
    assert groups[f"G{first_pump_group + 1}"] == {"bottoms_pump"}
    assert instance.pinned_groups == {f"G{first_pump_group}", f"G{first_pump_group + 1}"}


# ---- decks --------------------------------------------------------------------------------------


def _axis(variant: str, name: str) -> str:
    head = variant.split("|reflux[")[0]
    return dict(part.split("=", 1) for part in head.split("|"))[name]


def test_every_variant_of_every_deck_appears_within_one_deck_cycle() -> None:
    """Decks of 4 cards (vacuum), 3 (condenser) and 2 (preheater, sight glass) cycle once in 4."""
    h = PatternHarness(config=config_with())
    labels = [build_distillation_column(h.pctx).variant for _ in range(4)]
    assert {_axis(v, "vacuum") for v in labels} == {"none", "air_ejector", "liquid_ring"}
    assert {_axis(v, "condenser") for v in labels} == {"TubularHeatExchanger", "AirCoolingSystem"}
    assert {_axis(v, "preheater") for v in labels} == {"True", "False"}
    assert {_axis(v, "sight_glass") for v in labels} == {"True", "False"}
