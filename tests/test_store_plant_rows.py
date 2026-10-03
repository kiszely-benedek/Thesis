"""Plant-layer rows: one item per physical thing, edges joined across connector pairs.

Every expectation is recomputed from the sheets and the resolution (or built
by hand), never read back from the rows under test.
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.resolution.merge import build_plant_graph
from plantgraph.resolution.models import Resolution, ResolutionReport
from plantgraph.store.neo4j_rows import RelationshipRow, uid
from plantgraph.store.plant_rows import (
    drawn_as_rows,
    item_uid,
    plant_node_rows,
    plant_relationship_rows,
)
from store_toy_corpus import toy_corpus

_CORPUS = "acme"
_PUMP = "CentrifugalPump"
_TANK = "Tank"
_OUT = "FlowOutPipeOffPageConnector"
_IN = "FlowInPipeOffPageConnector"
_TOPOLOGY = {relation.value for relation in schema.TOPOLOGY_RELATIONS}


def _sheet(
    sheet_id: str, nodes: dict[str, dict[str, str]], edges: list[tuple[str, str]]
) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attrs in nodes.items():
        graph.add_node(node_id, **attrs)
    for source, target in edges:
        graph.add_edge(source, target, relation="send_to", line_number="L1")
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def _resolution(
    sheets: list[SheetGraph], pairs: list[ConnectorPair], groups: list[IdentityGroup]
) -> Resolution:
    plant, _conflicts = build_plant_graph(sheets, pairs, groups)
    report = ResolutionReport(
        n_sheets=len(sheets),
        n_occurrences=0,
        n_connectors=0,
        pairs_by_rule={},
        unresolved_by_reason={},
        n_identity_groups=len(groups),
        ambiguous_tag_keys=0,
        edge_attribute_conflicts=0,
    )
    return Resolution(
        plant=plant, connector_pairs=pairs, identity_groups=groups, unresolved=[], report=report
    )


def _pump(tag: str = "P-1") -> dict[str, str]:
    return {"node_class": _PUMP, "tag": tag, "unit_id": "U1", "plant_id": "PL"}


def _stub(node_class: str) -> dict[str, str]:
    return {"node_class": node_class}


def _tank() -> dict[str, str]:
    return {"node_class": _TANK, "tag": "TK-1"}


def _edge_rows(rows: list[RelationshipRow]) -> list[RelationshipRow]:
    return [row for row in rows if row.rel_type in _TOPOLOGY]


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_item_and_edge_counts_equal_the_resolutions_plant(duplication_rate: float) -> None:
    sheets, resolution = toy_corpus(duplication_rate)
    nodes = plant_node_rows(_CORPUS, sheets, resolution)
    edges = _edge_rows(plant_relationship_rows(_CORPUS, sheets, resolution, "resolver"))

    assert {row.uid for row in nodes} == {item_uid(_CORPUS, key) for key in resolution.plant}
    expected = {
        (item_uid(_CORPUS, source), item_uid(_CORPUS, target), attrs["relation"])
        for source, target, attrs in resolution.plant.edges(data=True)
    }
    assert {(row.source_uid, row.target_uid, row.rel_type) for row in edges} == expected
    assert len(edges) == resolution.plant.number_of_edges()


def test_every_item_row_is_a_plant_item_with_clean_properties() -> None:
    sheets, resolution = toy_corpus(0.5)
    for row in plant_node_rows(_CORPUS, sheets, resolution):
        assert row.labels[:2] == ("CorpusNode", schema.PLANT_ITEM_LABEL)
        assert row.props["uid"] == row.uid
        assert row.props["corpus_id"] == _CORPUS
        assert all(value is not None for value in row.props.values())


def test_a_reference_merges_into_its_home_with_one_drawn_as_each() -> None:
    sheets, resolution = toy_corpus(0.5)
    rows = drawn_as_rows(_CORPUS, sheets, resolution, "resolver")
    nodes = {row.uid for row in plant_node_rows(_CORPUS, sheets, resolution)}

    group = resolution.identity_groups[0]
    targets = {row.target_uid for row in rows if row.source_uid == item_uid(_CORPUS, group.home)}
    assert targets == {uid(_CORPUS, key) for key in [group.home, *group.references]}
    assert all(item_uid(_CORPUS, reference) not in nodes for reference in group.references)


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_drawn_as_covers_every_unpaired_occurrence_exactly_once(duplication_rate: float) -> None:
    sheets, resolution = toy_corpus(duplication_rate)
    pairs = resolution.connector_pairs
    paired = {p.from_key for p in pairs} | {p.to_key for p in pairs}
    occurrences = [
        uid(_CORPUS, f"{sheet.sheet_id}:{node_id}")
        for sheet in sheets
        for node_id in sheet.graph.nodes
        if f"{sheet.sheet_id}:{node_id}" not in paired
    ]
    rows = drawn_as_rows(_CORPUS, sheets, resolution, "resolver")
    assert sorted(row.target_uid for row in rows) == sorted(occurrences)


def test_a_connector_pair_gives_one_edge_with_both_stub_uids_and_crossed_sheets() -> None:
    sheets, resolution = toy_corpus(0.0)  # no references, so no edge is also drawn whole
    edges = _edge_rows(plant_relationship_rows(_CORPUS, sheets, resolution, "resolver"))
    via_edges = [row for row in edges if "via_connector_uids" in row.props]

    assert len(via_edges) == len(resolution.connector_pairs)
    for pair in resolution.connector_pairs:
        out_uid, in_uid = uid(_CORPUS, pair.from_key), uid(_CORPUS, pair.to_key)
        (row,) = [r for r in via_edges if out_uid in r.props["via_connector_uids"]]  # type: ignore[operator]
        assert row.props["via_connector_uids"] == [out_uid, in_uid]
        assert row.props["crossed_sheets"] == [
            pair.from_key.split(":")[0],
            pair.to_key.split(":")[0],
        ]
    assert all("crossed_sheets" not in row.props for row in edges if row not in via_edges)


def _reference_sheets() -> list[SheetGraph]:
    """P-1 on S1 feeds T-1 on S2 through a pair; S2 also draws P-1 again, joined to T-1 whole."""
    s1 = _sheet("S1", {"p": _pump(), "o": _stub(_OUT)}, [("p", "o")])
    s2 = _sheet(
        "S2",
        {"i": _stub(_IN), "t": _tank(), "pr": {"node_class": _PUMP}},
        [("i", "t"), ("pr", "t")],
    )
    return [s1, s2]


def test_an_edge_also_drawn_whole_on_a_reference_sheet_has_no_crossed_sheets() -> None:
    sheets = _reference_sheets()
    pairs = [ConnectorPair(from_key="S1:o", to_key="S2:i")]
    groups = [IdentityGroup(tag="P-1", home="S1:p", references=["S2:pr"])]
    resolution = _resolution(sheets, pairs, groups)

    (row,) = _edge_rows(plant_relationship_rows(_CORPUS, sheets, resolution, "resolver"))

    assert row.props["via_connector_uids"] == [uid(_CORPUS, "S1:o"), uid(_CORPUS, "S2:i")]
    assert "crossed_sheets" not in row.props
    assert row.props["line_number"] == "L1"
    assert row.props["asserted_by"] == "resolver"


def test_an_unpaired_stub_becomes_an_unresolved_off_page_connector_item() -> None:
    s1 = _sheet("S1", {"p": _pump(), "o": _stub(_OUT)}, [("p", "o")])
    resolution = _resolution([s1], [], [])
    rows = {row.uid: row for row in plant_node_rows(_CORPUS, [s1], resolution)}

    stub = rows[item_uid(_CORPUS, "S1:o")]
    assert stub.labels[:3] == ("CorpusNode", "PlantItem", schema.UNRESOLVED_CONNECTOR_LABEL)
    assert stub.labels[3:] == schema.labels_for(_OUT)
    assert schema.UNRESOLVED_CONNECTOR_LABEL not in rows[item_uid(_CORPUS, "S1:p")].labels


def test_a_hand_built_stub_chain_raises() -> None:
    s1 = _sheet("S1", {"p": _pump(), "o1": _stub(_OUT)}, [("p", "o1")])
    s2 = _sheet("S2", {"i1": _stub(_IN), "o2": _stub(_OUT)}, [("i1", "o2")])
    s3 = _sheet("S3", {"i2": _stub(_IN), "t": _tank()}, [("i2", "t")])
    sheets = [s1, s2, s3]
    pairs = [
        ConnectorPair(from_key="S1:o1", to_key="S2:i1"),
        ConnectorPair(from_key="S2:o2", to_key="S3:i2"),
    ]
    resolution = _resolution(sheets, pairs, [])

    with pytest.raises(ValueError, match="chains of connector pairs"):
        plant_node_rows(_CORPUS, sheets, resolution)
    with pytest.raises(ValueError, match="chains of connector pairs"):
        plant_relationship_rows(_CORPUS, sheets, resolution, "resolver")


def test_sheets_that_disagree_with_the_plant_raise() -> None:
    sheets, resolution = toy_corpus(0.0)
    resolution.plant.add_node("S99:ghost", node_class=_PUMP)
    with pytest.raises(ValueError, match="disagree"):
        plant_node_rows(_CORPUS, sheets, resolution)
