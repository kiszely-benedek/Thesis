"""U5, the exchanger train (design 7.2, pid-vocabulary 13.3): variants, utilities, the outlet loop.

Each test builds one train on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
"""

from __future__ import annotations

import networkx as nx
import pytest
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    flow_graph,
    nodes_of_class,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from test_column import letters, sensor_location
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.heat import build_exchanger_train
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.graph.schema import EQUIPMENT_CLASSES

_STEAM = {"U5.utility": ("steam",)}
_WATER = {"U5.utility": ("cooling_water",)}
_NO_HEATER = {"U5.trim_heater": ("absent",)}
_PLAIN = {"condensate_mode_weights": {"trap": 1.0}}  # no drain pot: keeps `LV` and pots out


def train(
    cards: dict[str, tuple[str, ...]] | None = None, seed: int = 0, **sections: dict[str, object]
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one train; `sections` override knob groups (`density={...}`)."""
    sections.setdefault("trims", _PLAIN)
    h = PatternHarness(seed, config_with(**sections), deck_cards=cards)
    instance = build_exchanger_train(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def exchangers(instance: PatternInstance) -> list[str]:
    """The utility exchangers, in flow order (the electric heater has its own role)."""
    return [
        e.node_id for e in instance.plan.equipment if instance.plan.roles[e.node_id] == "exchanger"
    ]


def services_into(graph: nx.DiGraph[str], node_id: str) -> set[str]:
    """The fluid codes of the lines that enter `node_id`."""
    return {d.get("fluid_code", "") for _, _, d in graph.in_edges(node_id, data=True)}


# ---- variants -----------------------------------------------------------------------------------


@pytest.mark.parametrize("count", ["2", "3", "4"])
def test_exchanger_count_variant_gives_that_many_exchangers_in_series(count: str) -> None:
    _, instance, graph = train({"U5.exchanger_count": (count,), **_NO_HEATER})
    chain = exchangers(instance)
    flow = flow_graph(graph)
    assert len(chain) == int(count)
    assert nx.has_path(flow, instance.port("cold").node_id, chain[0])
    assert all(nx.has_path(flow, a, b) for a, b in zip(chain, chain[1:], strict=False))
    assert nx.has_path(flow, chain[-1], instance.port("heated").node_id)


@pytest.mark.parametrize("node_class", ["TubularHeatExchanger", "PlateHeatExchanger"])
def test_exchanger_class_variant(node_class: str) -> None:
    _, instance, graph = train({"U5.exchanger": (node_class,)})
    assert {graph.nodes[e]["node_class"] for e in exchangers(instance)} == {node_class}


def test_the_electric_trim_heater_comes_last_and_has_no_utility_line() -> None:
    _, instance, graph = train(
        {"U5.trim_heater": ("ElectricHeater",), "U5.exchanger_count": ("2",)}
    )
    (heater,) = ids_with_role(instance.plan, "trim_heater")
    assert graph.nodes[heater]["node_class"] == "ElectricHeater"
    assert services_into(graph, heater) <= {"P", ""}  # only the process line enters it
    assert nx.has_path(flow_graph(graph), exchangers(instance)[-1], heater)
    assert nx.has_path(flow_graph(graph), heater, instance.port("heated").node_id)


def test_without_the_trim_heater_there_is_no_electric_heater() -> None:
    _, instance, graph = train(_NO_HEATER)
    assert not nodes_of_class(graph, "ElectricHeater")


def test_the_ports_are_cold_in_and_heated_out_of_liquid() -> None:
    _, instance, graph = train()
    assert instance.port_names == ["cold", "heated"]
    assert (instance.port("cold").direction, instance.port("cold").phase) == (
        PortDirection.IN,
        Phase.LIQUID,
    )
    assert (instance.port("heated").direction, instance.port("heated").phase) == (
        PortDirection.OUT,
        Phase.LIQUID,
    )
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[instance.port("cold").line_number].src_id is None
    assert lines[instance.port("heated").line_number].dst_id is None


# ---- utilities ----------------------------------------------------------------------------------


def test_every_steam_exchanger_has_steam_in_with_a_gauge_and_condensate_out() -> None:
    _, instance, graph = train(_STEAM)
    for exchanger in exchangers(instance):
        assert "LPS" in services_into(graph, exchanger)
        outgoing = {d.get("fluid_code") for _, _, d in graph.out_edges(exchanger, data=True)}
        assert "CD" in outgoing  # L15: condensate leaves through its own line
    assert len(ids_with_role(instance.plan, "steam_supply_pi")) == len(exchangers(instance))


def test_every_cooling_water_exchanger_has_a_thermal_relief_on_its_return() -> None:
    """L12: the safety valve sits on the `CWR` line between the cooler and the block valve."""
    _, instance, graph = train(_WATER)
    for exchanger in exchangers(instance):
        assert "CWS" in services_into(graph, exchanger)
    reliefs = ids_with_role(instance.plan, "thermal_relief_valve")
    assert len(reliefs) == len(exchangers(instance))
    assert all(graph.nodes[r]["node_class"].endswith("SafetyValve") for r in reliefs)


def _steam_source(graph: nx.DiGraph[str], pot: str) -> str:
    """The exchanger whose condensate line (`CD`) leads to `pot`: walk the line back."""
    current = pot
    while graph.nodes[current]["node_class"] not in EQUIPMENT_CLASSES or current == pot:
        current = next(
            s for s, _, d in graph.in_edges(current, data=True) if d.get("fluid_code") == "CD"
        )
    return current


def test_drain_pot_condensate_belongs_to_the_group_of_its_exchanger() -> None:
    _, instance, graph = train(
        {**_STEAM, "U5.exchanger_count": ("4",), "U5.trim_heater": ("ElectricHeater",)},
        trims={"condensate_mode_weights": {"drain_pot": 1.0}},
    )
    pots = ids_with_role(instance.plan, "condensate_drain_pot")
    assert len(pots) == len(exchangers(instance)) and nodes_with_letters(graph, "CSHH")
    for pot in pots:  # four exchangers and a heater: two groups, so a wrong group would show
        owner = _steam_source(graph, pot)
        assert instance.drawing_group_of[pot] == instance.drawing_group_of[owner]
    assert {instance.drawing_group_of[p] for p in pots} == {"G1", "G2"}


# ---- the outlet temperature loop ----------------------------------------------------------------


def test_a_steam_train_moves_the_steam_valve_of_the_last_exchanger() -> None:
    """`TT` on the outlet -> `TIC` -> `TV` in the last exchanger's steam line; no bypass."""
    _, instance, graph = train({**_STEAM, **_NO_HEATER})
    (valve,) = nodes_with_letters(graph, "TV")
    last = exchangers(instance)[-1]
    assert sensor_location(graph, valve) == ("TIC", last)
    assert nx.has_path(flow_graph(graph), valve, last)
    assert not ids_with_role(instance.plan, "bypass_split_tee")


def test_a_cooling_water_train_moves_a_valve_on_a_bypass_around_the_last_exchanger() -> None:
    _, instance, graph = train({**_WATER, **_NO_HEATER})
    (valve,) = nodes_with_letters(graph, "TV")
    last = exchangers(instance)[-1]
    (split,) = ids_with_role(instance.plan, "bypass_split_tee")
    (merge,) = ids_with_role(instance.plan, "bypass_merge_tee")
    paths = list(nx.all_simple_paths(flow_graph(graph), split, merge))
    assert len(paths) == 2 and sum(valve in path for path in paths) == 1  # valve on one path only
    assert sum(last in path for path in paths) == 1  # the other goes through the exchanger
    assert sensor_location(graph, valve) == ("TIC", last)


def test_with_a_trim_heater_the_outlet_sensor_sits_on_the_heater() -> None:
    _, instance, graph = train({**_WATER, "U5.trim_heater": ("ElectricHeater",)})
    (valve,) = nodes_with_letters(graph, "TV")
    (heater,) = ids_with_role(instance.plan, "trim_heater")
    assert sensor_location(graph, valve) == ("TIC", heater)
    (split,) = ids_with_role(instance.plan, "bypass_split_tee")  # around the last *exchanger*
    assert nx.has_path(flow_graph(graph), split, exchangers(instance)[-1])


# ---- instruments and sheets ---------------------------------------------------------------------


def test_a_thermometer_follows_every_exchanger_and_gauges_mark_the_inlet_and_outlet() -> None:
    _, instance, graph = train({"U5.trim_heater": ("ElectricHeater",)})
    count = len(instance.plan.equipment) - len(ids_with_role(instance.plan, "condensate_drain_pot"))
    assert len(ids_with_role(instance.plan, "exchanger_outlet_ti")) == count
    for role in ("inlet_pi", "outlet_pi"):
        (gauge,) = ids_with_role(instance.plan, role)
        assert letters(graph, gauge) == "PI"


@pytest.mark.parametrize(("chance", "expected"), [(1.0, 1), (0.0, 0)])
def test_the_inlet_flow_indicator_follows_p_optional_instrument(
    chance: float, expected: int
) -> None:
    _, _, graph = train(density={"p_optional_instrument": chance})
    assert len(nodes_with_letters(graph, "FT")) == expected == len(nodes_with_letters(graph, "FI"))


def test_the_safety_valve_on_an_exchanger_shell_is_reachable_when_drawn() -> None:
    drawn = []
    for seed in range(12):
        _, instance, graph = train(seed=seed)
        for exchanger in exchangers(instance):
            has_valve = any(
                graph.nodes[n]["node_class"].endswith("SafetyValve")
                for n in graph.successors(exchanger)
                if graph.nodes[n]["node_class"] != "PipeTee"
            )
            drawn.append(has_valve)
            assert not has_valve or reaches_a_safety_device(graph, exchanger)
    assert any(drawn) and not all(drawn)  # an optional item at even odds


@pytest.mark.parametrize(
    ("count", "heater"), [("2", "absent"), ("4", "absent"), ("4", "ElectricHeater")]
)
def test_a_train_of_at_most_four_is_one_group_and_a_longer_one_is_cut_at_the_midpoint(
    count: str, heater: str
) -> None:
    _, instance, _ = train({"U5.exchanger_count": (count,), "U5.trim_heater": (heater,)})
    units = int(count) + (heater != "absent")
    names = sorted(set(instance.drawing_group_of.values()))
    assert names == (["G1"] if units <= 4 else ["G1", "G2"])
    if units > 4:
        main = [n for n, r in instance.plan.roles.items() if r in {"exchanger", "trim_heater"}]
        assert sum(instance.drawing_group_of[n] == "G1" for n in main) == units // 2


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = train()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


@pytest.mark.parametrize("seed", range(8))
def test_only_generated_equipment_classes_appear(seed: int) -> None:
    _, instance, _ = train(seed=seed)
    classes = {e.node_class for e in instance.plan.equipment}
    assert classes <= GENERATED_EQUIPMENT_CLASSES and "SpiralHeatExchanger" not in classes


def test_every_variant_of_every_deck_appears_within_a_deck_cycle() -> None:
    h = PatternHarness(config=config_with())
    labels = [build_exchanger_train(h.pctx).variant for _ in range(6)]
    assert {int(v.split("exchangers=")[1][0]) for v in labels} == {2, 3, 4}
    assert any("PlateHeatExchanger" in v for v in labels)
    assert any("TubularHeatExchanger" in v for v in labels)
    assert any("steam" in v for v in labels) and any("cooling_water" in v for v in labels)
    assert {"trim_heater=True", "trim_heater=False"} <= {
        part for v in labels for part in v.split("|")
    }
