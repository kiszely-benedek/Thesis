"""The item graph built from the resolver's output, and the API-01 check against the gold plant."""

from __future__ import annotations

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.graph import schema
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.api_fidelity import compare_edges_by_tag
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.model import UNRESOLVED_CONNECTOR_CLASS, ItemEdge, ItemFilter
from plantgraph.resolution.localize import localize
from plantgraph.resolution.resolver import resolve
from qa_plant_api_toy import toy_graph
from qa_routing_toy import ToyCorpus, key


def _edges_by_tag(graph: ItemGraph) -> set[tuple[str, str, str]]:
    return {
        (graph.item(e.source).tag or "?", e.relation, graph.item(e.target).tag or "?")
        for e in graph.edges
    }


def test_a_stub_pair_contracts_to_one_edge_that_remembers_its_stubs() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S2", "b", "TB")
    toy.cut("S1", "a", "S2", "b", "c1")

    graph = build_item_graph(toy.view())

    assert [item.tag for item in map(graph.item, graph.all_ids())] == ["TA", "TB"]  # no stubs
    assert graph.edges == (
        ItemEdge(
            source=key("S1", "a"),
            target=key("S2", "b"),
            relation="send_to",
            via=(key("S1", "out_c1"), key("S2", "in_c1")),
        ),
    )


def test_a_repeated_drawing_merges_into_its_home_and_keeps_both_sheets() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S2", "p", "P-1")
    toy.cut("S1", "a", "S2", "p", "c1")
    toy.item("S3", "p_ref", "P-1")
    toy.item("S3", "t", "TT")
    toy.flow("S3", "p_ref", "t")
    toy.identity("P-1", home=("S2", "p"), references=[("S3", "p_ref")])

    graph = build_item_graph(toy.view())
    pump = graph.item(graph.ids_for_tag("p-1")[0])

    assert len(graph.ids_for_tag("P-1")) == 1
    assert pump.item_id == key("S2", "p")  # the home drawing's key is the item id
    assert pump.sheets == ("S2", "S3")
    assert pump.occurrence_keys == (key("S2", "p"), key("S3", "p_ref"))
    assert _edges_by_tag(graph) == {("TA", "send_to", "P-1"), ("P-1", "send_to", "TT")}


def test_an_unpaired_stub_becomes_a_pseudo_item_a_walk_can_reach() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.dangling_stub("S1", "a", "x")

    graph = build_item_graph(toy.view())
    (stub,) = (graph.item(i) for i in graph.all_ids() if graph.item(i).tag is None)

    assert stub.node_class == UNRESOLVED_CONNECTOR_CLASS
    assert stub.labels == (UNRESOLVED_CONNECTOR_CLASS,)
    assert [(e.source, e.target) for e in graph.edges] == [(key("S1", "a"), stub.item_id)]
    assert graph.select(ItemFilter(label=UNRESOLVED_CONNECTOR_CLASS)) == [stub.item_id]


def test_a_stub_is_never_found_by_tag() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.dangling_stub("S1", "a", "x")

    assert build_item_graph(toy.view()).ids_for_tag("out_x") == []


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_item_edges_equal_the_gold_plants_edges_by_tag(duplication_rate: float) -> None:
    gold, view = _split_corpus(duplication_rate)

    graph = build_item_graph(view)
    fidelity = compare_edges_by_tag(graph, gold)

    assert fidelity.n_gold > 50
    assert (fidelity.precision, fidelity.recall) == (1.0, 1.0), fidelity
    assert any(edge.via for edge in graph.edges)  # the corpus does cross sheets


def test_duplicated_drawings_merge_into_the_same_items_as_the_plain_split() -> None:
    _, plain = _split_corpus(0.0)
    _, duplicated = _split_corpus(0.5)

    n_plain = len(build_item_graph(plain).all_ids())
    n_duplicated = len(build_item_graph(duplicated).all_ids())

    assert _n_drawings(plain) == n_plain  # nothing is drawn twice
    assert _n_drawings(duplicated) > n_duplicated  # some items are drawn on two sheets
    assert n_duplicated == n_plain  # ... and merging gives back the same plant


def test_api_01_reports_a_missing_and_an_extra_edge() -> None:
    graph = toy_graph()
    gold: nx.DiGraph[str] = nx.DiGraph()
    for source, relation, target in sorted(_edges_by_tag(graph)):
        gold.add_node(source, tag=source)
        gold.add_node(target, tag=target)
        gold.add_edge(source, target, relation=relation)
    gold.remove_edge("T1", "BV1")
    gold.add_edge("T1", "V2", relation="send_to")

    fidelity = compare_edges_by_tag(graph, gold)

    assert (fidelity.n_gold, fidelity.n_item_graph, fidelity.n_matched) == (11, 11, 10)
    assert fidelity.missing_sample == (("T1", "send_to", "V2"),)
    assert fidelity.extra_sample == (("T1", "send_to", "BV1"),)
    assert fidelity.precision == fidelity.recall == 10 / 11


def _n_drawings(view: NetworkxGraphView) -> int:
    """Occurrences that are not connector stubs."""
    return sum(1 for o in view.items() if o.node_class not in schema.CONNECTOR_CLASSES)


def _split_corpus(duplication_rate: float) -> tuple[nx.DiGraph[str], NetworkxGraphView]:
    """The gold plant of a 4-unit generated corpus, and the view built from its split sheets."""
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=duplication_rate)
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return builder.graph, NetworkxGraphView("toy", localized, resolve(localized))
