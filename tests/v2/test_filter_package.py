"""U7, the filter package (design 7.2, pid-vocabulary 13.6): parallel filters, valves, gauges.

Each test builds the package on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
"""

from __future__ import annotations

import networkx as nx
import pytest
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    nodes_with_letters,
)
from pattern_harness import PatternHarness, config_with
from trim_harness import all_send_to_paths, ids_with_role, send_to_path

from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.vocabulary import SpareNaming


def _package(
    seed: int = 0,
    density: dict[str, object] | None = None,
    naming: SpareNaming = SpareNaming.SUFFIX,
    dp: str | None = None,
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one package; `dp` (`pair` / `per_filter`) searches the seeds for that variant."""
    for attempt in range(seed, seed + 30):
        h = PatternHarness(attempt, config_with(density=density or {}), spare_naming=naming)
        instance = build_filter_package(h.pctx)
        if dp is None or f"dp={dp}" in instance.variant:
            instance.plan.write(h.builder)
            return h, instance, assert_pattern_invariants(h)
    raise AssertionError(f"no seed from {seed} to {seed + 30} gave the variant dp={dp}")


def _filters(instance: PatternInstance) -> list[str]:
    return [e.node_id for e in instance.plan.equipment]


def test_there_are_two_identical_filters_with_a_shared_number_and_suffixes() -> None:
    _, instance, graph = _package()
    first, second = _filters(instance)
    assert {graph.nodes[f]["node_class"] for f in (first, second)} == {"LiquidFilter"}
    assert {instance.plan.roles[f] for f in (first, second)} == {"filter"}
    tags = [graph.nodes[f]["tag"] for f in (first, second)]
    assert tags[0].endswith("A") and tags[1] == tags[0][:-1] + "B"


def test_consecutive_naming_numbers_the_filters_one_after_the_other() -> None:
    _, instance, graph = _package(naming=SpareNaming.CONSECUTIVE)
    numbers = [parse_tag(graph.nodes[f]["tag"]).sequence for f in _filters(instance)]  # type: ignore[union-attr]
    assert numbers[1] == numbers[0] + 1


def test_s11_the_filters_are_parallel_between_the_split_and_the_merge_tee() -> None:
    _, instance, graph = _package()
    first, second = _filters(instance)
    (split,) = ids_with_role(instance.plan, "filter_split_tee")
    (merge,) = ids_with_role(instance.plan, "filter_merge_tee")
    paths = all_send_to_paths(graph, split, merge)
    assert sorted(len({first, second} & set(path)) for path in paths) == [1, 1]
    assert {f for path in paths for f in path if f in (first, second)} == {first, second}


def test_every_filter_has_a_block_valve_on_its_inlet_and_its_outlet() -> None:
    _, instance, graph = _package()
    (split,) = ids_with_role(instance.plan, "filter_split_tee")
    (merge,) = ids_with_role(instance.plan, "filter_merge_tee")
    for filter_id in _filters(instance):
        into = [instance.plan.roles.get(n) for n in send_to_path(graph, split, filter_id)]
        out_of = [instance.plan.roles.get(n) for n in send_to_path(graph, filter_id, merge)]
        assert "filter_inlet_block" in into and "filter_outlet_block" in out_of


def test_every_filter_has_a_vent_and_a_drain() -> None:
    _, instance, graph = _package()
    for role in ("vessel_vent_valve", "vessel_drain_valve"):
        valves = ids_with_role(instance.plan, role)
        assert (
            sorted(v for f in _filters(instance) for v in graph.successors(f) if v in valves)
            == valves
        )
    assert len(ids_with_role(instance.plan, "vessel_vent_valve")) == 2
    assert len(ids_with_role(instance.plan, "vessel_drain_valve")) == 2


def test_the_pressure_drop_is_read_across_each_filter() -> None:
    _, instance, graph = _package(dp="per_filter")
    assert len(nodes_with_letters(graph, "PDT")) == len(nodes_with_letters(graph, "PDI")) == 2
    assert len(ids_with_role(instance.plan, "filter_dp_tee")) == 2


def test_the_pressure_drop_is_read_once_across_the_pair() -> None:
    _, instance, graph = _package(dp="pair")
    assert len(nodes_with_letters(graph, "PDT")) == len(nodes_with_letters(graph, "PDI")) == 1
    assert len(ids_with_role(instance.plan, "filter_dp_tee")) == 1


def test_there_is_a_pressure_gauge_on_the_inlet_and_on_the_outlet() -> None:
    _, instance, graph = _package()
    assert len(ids_with_role(instance.plan, "inlet_pi")) == 1
    assert len(ids_with_role(instance.plan, "outlet_pi")) == 1
    assert len(nodes_with_letters(graph, "PI")) >= 2


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_the_flow_controller_on_the_outlet_follows_its_chance(
    chance: float, expected: bool
) -> None:
    _, instance, graph = _package(density={"p_optional_instrument": chance})
    assert bool(nodes_with_letters(graph, "FIC")) is expected
    if expected:
        (valve,) = nodes_with_letters(graph, "FV")
        assert nx.has_path(nx.DiGraph(graph.edges), valve, instance.port("filtered").node_id)


def test_the_ports_are_a_liquid_feed_in_and_a_liquid_out_and_both_lines_are_open() -> None:
    _, instance, graph = _package()
    assert [(p.name, p.direction, p.phase) for p in instance.ports] == [
        ("feed", PortDirection.IN, Phase.LIQUID),
        ("filtered", PortDirection.OUT, Phase.LIQUID),
    ]
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[instance.port("feed").line_number].src_id is None
    assert lines[instance.port("filtered").line_number].dst_id is None
    assert instance.port("filtered").node_id in graph


def test_the_package_is_one_group_with_nothing_pinned_and_its_own_unit() -> None:
    """Pid-vocabulary 13.6 rule 3: U7 is one group and never joins another unit's group."""
    _, instance, _ = _package()
    assert set(instance.drawing_group_of.values()) == {"G1"}
    assert instance.system_code == "FIL" and instance.pattern == "U7"


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = _package()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


def test_both_pressure_drop_variants_appear_among_the_seeds() -> None:
    labels = set()
    for seed in range(10):
        h = PatternHarness(seed)
        labels.add(build_filter_package(h.pctx).variant.split("|")[0])
    assert labels == {"dp=per_filter", "dp=pair"}
