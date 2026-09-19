"""A `plan_plant` topológia-döntéseinek invariánsai (`plant-generator.md` §3.3, §3.4).

A `GraphPlantBuilder` (`tests/graph_plant_builder.py`) végzi a felépítést — ez
az oracle-builder, amit a valódi pyDEXPI-backend majd lecserél, de a
topológiai szabályok ugyanazok maradnak (§3.4 invariánsok 1-8, a `DiGraph`
helyett itt közvetlenül a builder gráfján ellenőrizve).
"""

from __future__ import annotations

import random
import re

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark import generator
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GenerationRecord, GeneratorConfig, StreamKind
from plantgraph.graph import schema, validation

SEEDS = range(20)


def _build(config: GeneratorConfig) -> tuple[nx.DiGraph[str], GenerationRecord]:
    builder = GraphPlantBuilder(config.plant_id)
    record = plan_plant(config, builder)
    return builder.graph, record


def _sorted_nodes(graph: nx.DiGraph[str]) -> list[tuple[str, dict[str, object]]]:
    return sorted((node_id, dict(attrs)) for node_id, attrs in graph.nodes(data=True))


def _sorted_edges(graph: nx.DiGraph[str]) -> list[tuple[str, str, dict[str, object]]]:
    return sorted((source, target, dict(attrs)) for source, target, attrs in graph.edges(data=True))


# ---- invariáns 3: reprodukálhatóság ---------------------------------------------------------


def test_same_seed_produces_an_identical_graph_and_record() -> None:
    config = GeneratorConfig(seed=7)
    graph_a, record_a = _build(config)
    graph_b, record_b = _build(config)
    assert _sorted_nodes(graph_a) == _sorted_nodes(graph_b)
    assert _sorted_edges(graph_a) == _sorted_edges(graph_b)
    assert record_a == record_b


def test_seed_0_and_seed_1_differ() -> None:
    graph_0, record_0 = _build(GeneratorConfig(seed=0))
    graph_1, record_1 = _build(GeneratorConfig(seed=1))
    assert _sorted_nodes(graph_0) != _sorted_nodes(graph_1)
    assert record_0 != record_1


# ---- invariáns 4: a globális random modul érintetlen ------------------------------------------


def test_plan_plant_never_touches_the_global_random_module() -> None:
    state_before = random.getstate()
    _build(GeneratorConfig(seed=3))
    assert random.getstate() == state_before


# ---- invariáns 2: séma-érvényesség -------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_plant_is_schema_valid(seed: int) -> None:
    graph, _ = _build(GeneratorConfig(seed=seed))
    assert validation.validate_plant_graph(graph) == []


# ---- invariáns 1, 5: alapszerkezet ----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_plant_has_no_self_loops_and_is_weakly_connected(seed: int) -> None:
    graph, _ = _build(GeneratorConfig(seed=seed))
    assert nx.number_of_selfloops(graph) == 0
    assert nx.is_weakly_connected(graph)


@pytest.mark.parametrize("seed", SEEDS)
def test_unit_1s_first_equipment_has_in_degree_zero(seed: int) -> None:
    config = GeneratorConfig(seed=seed)
    graph, _ = _build(config)
    first_equipment = f"{config.plant_id}-u1-eq1"
    assert graph.in_degree(first_equipment) == 0


# ---- invariáns 6: legalább egy elágazás a seedek felett ---------------------------------------


def test_at_least_one_equipment_has_two_or_more_outgoing_streams_across_seeds() -> None:
    max_out_degree = 0
    for seed in SEEDS:
        graph, _ = _build(GeneratorConfig(seed=seed))
        for node_id, attrs in graph.nodes(data=True):
            if attrs["node_class"] not in schema.EQUIPMENT_CLASSES:
                continue
            out_degree = _send_to_out_degree(graph, node_id)
            max_out_degree = max(max_out_degree, out_degree)
    assert max_out_degree >= 2


def _send_to_out_degree(graph: nx.DiGraph[str], node_id: str) -> int:
    """Egy csomópont hány csővezetéket indít — csak a `send_to` éleket számolja."""
    return sum(
        1
        for _, _, attrs in graph.out_edges(node_id, data=True)
        if attrs["relation"] == schema.Relation.SEND_TO.value
    )


# ---- azonosító- és tag-formátumok ------------------------------------------------------------

_TAG_PATTERN = re.compile(r"^[A-Z]+-\d+-\d+$")


def test_node_ids_follow_the_plant_unit_kind_seq_pattern() -> None:
    config = GeneratorConfig(seed=4)
    graph, _ = _build(config)
    node_id_pattern = re.compile(rf"^{config.plant_id}-u\d+-(eq|va|in)\d+$")
    for node_id in graph.nodes:
        assert node_id_pattern.match(node_id), f"unexpected node id shape: {node_id!r}"


def test_equipment_and_valve_tags_follow_the_prefix_unit_seq_pattern() -> None:
    graph, _ = _build(GeneratorConfig(seed=4))
    tagged_classes = schema.EQUIPMENT_CLASSES | schema.VALVE_CLASSES
    for _, attrs in graph.nodes(data=True):
        if attrs["node_class"] in tagged_classes:
            assert _TAG_PATTERN.match(attrs["tag"]), f"unexpected tag shape: {attrs['tag']!r}"


# ---- szelepek egysége -------------------------------------------------------------------------


def _stream_source(graph: nx.DiGraph[str], node_id: str) -> str:
    """Visszasétál a szelepeken az adott csővezeték kiinduló berendezéséig."""
    while graph.nodes[node_id]["node_class"] in schema.VALVE_CLASSES:
        node_id = next(iter(graph.predecessors(node_id)))
    return node_id


def test_valves_take_the_source_equipments_unit() -> None:
    checked_a_valve = False
    for seed in range(5):
        graph, _ = _build(GeneratorConfig(seed=seed))
        for node_id, attrs in graph.nodes(data=True):
            if attrs["node_class"] not in schema.VALVE_CLASSES:
                continue
            checked_a_valve = True
            source = _stream_source(graph, node_id)
            assert attrs["unit_id"] == graph.nodes[source]["unit_id"]
    assert checked_a_valve, "no valve was generated across seeds 0-4 to check against"


# ---- stream_kind lefedettsége -------------------------------------------------------------


def test_every_streams_line_number_appears_in_the_generation_record() -> None:
    graph, record = _build(GeneratorConfig(seed=6))
    line_numbers = {
        attrs["line_number"]
        for _, _, attrs in graph.edges(data=True)
        if attrs["relation"] == schema.Relation.SEND_TO.value
    }
    assert line_numbers == set(record.stream_kind)


# ---- duplikált rendezett pár -------------------------------------------------------------------


def test_a_second_stream_on_the_same_ordered_pair_raises() -> None:
    # a nyilvános API-n (plan_plant) a véletlen döntések sosem hoznak létre
    # ütköző párt (a recycle és a cross_link szabálya kizárja) — ez az
    # invariáns ezért a belső _GenerationState-en ellenőrzött, direkt eset
    config = GeneratorConfig(seed=0, n_units=1)
    state = generator._GenerationState(config, GraphPlantBuilder(config.plant_id))
    state.add_sections()
    state.add_equipment()
    src, dst = state.units_equipment[0][:2]
    state._add_stream(src, dst, StreamKind.TREE)
    with pytest.raises(ValueError, match="duplicate stream"):
        state._add_stream(src, dst, StreamKind.TREE)


# ---- recycle és cross_link szabályai ------------------------------------------------------------

_EQ_SEQ = re.compile(r"-eq(\d+)$")


def _eq_seq(node_id: str) -> int:
    """A berendezés egységen belüli sorszáma a node_id-ból — a keletkezési sorrendet adja vissza."""
    match = _EQ_SEQ.search(node_id)
    assert match is not None, f"not an equipment node id: {node_id!r}"
    return int(match.group(1))


def _edges_by_line_number(graph: nx.DiGraph[str]) -> dict[str, list[tuple[str, str]]]:
    """A `send_to` éleket csővezeték (line_number) szerint csoportosítja.

    Egy csővezeték a szelepei miatt több szegmensből (élből) áll — a kind
    ellenőrzéshez a lánc valódi két végét kell tudni, nem az egyes szegmenseket.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for source, target, attrs in graph.edges(data=True):
        if attrs["relation"] != schema.Relation.SEND_TO.value:
            continue
        grouped.setdefault(attrs["line_number"], []).append((source, target))
    return grouped


def _stream_endpoints(edges: list[tuple[str, str]]) -> tuple[str, str]:
    """Egy csővezeték-lánc valódi két vége: ami sosem cél, illetve ami sosem forrás a láncban."""
    sources = {source for source, _ in edges}
    targets = {target for _, target in edges}
    return next(iter(sources - targets)), next(iter(targets - sources))


def test_recycle_streams_go_from_a_later_to_an_earlier_equipment_in_the_same_unit() -> None:
    checked_a_recycle = False
    for seed in SEEDS:
        graph, record = _build(GeneratorConfig(seed=seed))
        for line_number, edges in _edges_by_line_number(graph).items():
            if record.stream_kind.get(line_number) != StreamKind.RECYCLE:
                continue
            checked_a_recycle = True
            source, target = _stream_endpoints(edges)
            assert graph.nodes[source]["unit_id"] == graph.nodes[target]["unit_id"]
            assert _eq_seq(source) > _eq_seq(target) >= 1
    assert checked_a_recycle, "no recycle stream was generated across seeds 0-19 to check against"


def test_cross_link_streams_cross_units_and_never_target_a_units_first_equipment() -> None:
    checked_a_cross_link = False
    for seed in SEEDS:
        graph, record = _build(GeneratorConfig(seed=seed))
        for line_number, edges in _edges_by_line_number(graph).items():
            if record.stream_kind.get(line_number) != StreamKind.CROSS_LINK:
                continue
            checked_a_cross_link = True
            source, target = _stream_endpoints(edges)
            assert graph.nodes[source]["unit_id"] != graph.nodes[target]["unit_id"]
            assert _eq_seq(target) >= 2
    assert checked_a_cross_link, (
        "no cross_link stream was generated across seeds 0-19 to check against"
    )


# ---- szabályozókörök -----------------------------------------------------------------------


def test_control_loops_only_sit_on_operated_valves_with_at_most_one_loop_each() -> None:
    checked_a_loop = False
    for seed in SEEDS:
        graph, _ = _build(GeneratorConfig(seed=seed))
        targets = [
            target
            for _, target, attrs in graph.edges(data=True)
            if attrs["relation"] == schema.Relation.CONTROL.value
        ]
        checked_a_loop = checked_a_loop or bool(targets)
        for valve_id in targets:
            assert graph.nodes[valve_id]["node_class"] in schema.OPERATED_VALVE_CLASSES
        assert len(targets) == len(set(targets)), "a valve is controlled by more than one loop"
    assert checked_a_loop, "no control loop was generated across seeds 0-19 to check against"
