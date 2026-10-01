"""RU-T5: question reach is uncapped, and enumeration samples before it builds.

Chain toy plants make the reach hand-checkable: node `i` sends to node `i+1`
and every node is its own sheet, so every edge is cut and `k` equals hops.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.models import Question
from plantgraph.qa.questions.availability import KBin, k_bin_of
from plantgraph.qa.questions.evidence import Evidence, SheetIndex, evidence_sheets
from plantgraph.qa.questions.families_flow import flow_path_candidates
from plantgraph.qa.questions.families_isolation import upstream_isolation_candidates

_CORPUS = "chain"
_HOPS = 12


def _chain(classes: list[NodeClass]) -> tuple[nx.DiGraph[str], list[SheetGraph], SplitManifest]:
    """Nodes `N0 -> N1 -> ...`, one sheet each, every edge cut; tags are `T-1-<i>`."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for i, node_class in enumerate(classes):
        plant.add_node(f"N{i}", node_class=node_class.value, tag=f"T-1-{i:02d}", unit_id="1")
    edges = [(f"N{i}", f"N{i + 1}") for i in range(len(classes) - 1)]
    for source, target in edges:
        plant.add_edge(source, target, relation=Relation.SEND_TO.value)
    sheets = [
        SheetGraph(sheet_id=f"S{i}", graph=plant.subgraph([f"N{i}"]).copy())
        for i in range(len(classes))
    ]
    manifest = SplitManifest(
        source="chain",
        sheet_files=[sheet.sheet_id for sheet in sheets],
        connector_pairs=[
            ConnectorPair(from_key=f"o{i}", to_key=f"i{i}", original_edge=edge)
            for i, edge in enumerate(edges)
        ],
    )
    return plant, sheets, manifest


def _flow(
    plant: nx.DiGraph[str], sheets: list[SheetGraph], manifest: SplitManifest
) -> list[Question]:
    return flow_path_candidates(plant, manifest, sheets, corpus_id=_CORPUS, seed=0)


def test_a_12_hop_chain_yields_a_candidate_the_old_6_hop_cap_would_have_dropped() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))

    # The k >= 3 bin holds targets 3..12 hops away and one is drawn per source and seed,
    # so look across seeds for a draw beyond the old cap.
    ks = [
        q.k
        for seed in range(10)
        for q in flow_path_candidates(plant, manifest, sheets, corpus_id=_CORPUS, seed=seed)
        if q.anchors[0] == "T-1-00" and q.k is not None
    ]

    assert max(ks) > 6
    assert max(ks) <= _HOPS


def test_at_most_one_flow_path_question_per_source_and_bin() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))

    questions = _flow(plant, sheets, manifest)

    per_cell = Counter((q.anchors[0], k_bin_of(q)) for q in questions)
    assert max(per_cell.values()) == 1
    # T-1-00 reaches k = 1, 2 and 3..12: three bins, hence three questions.
    assert per_cell[("T-1-00", KBin.K1)] == per_cell[("T-1-00", KBin.K3_PLUS)] == 1
    assert sum(1 for source, _ in per_cell if source == "T-1-00") == 3


def test_flow_path_draw_depends_on_the_seed_only() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))

    first = [q.model_dump_json() for q in _flow(plant, sheets, manifest)]
    second = [q.model_dump_json() for q in _flow(plant, sheets, manifest)]

    assert first == second


def test_isolation_walk_reaches_a_valve_beyond_6_hops() -> None:
    # GV (operated) -> 10 check valves (passed through) -> vessel: 11 hops upstream.
    classes = [NodeClass.GLOBE_VALVE, *[NodeClass.CHECK_VALVE] * 10, NodeClass.PRESSURE_VESSEL]
    plant, sheets, manifest = _chain(classes)

    questions = upstream_isolation_candidates(plant, manifest, sheets, corpus_id=_CORPUS, seed=0)

    assert [q.reference for q in questions] == [["T-1-00"]]
    assert questions[0].k == len(classes) - 1


def _old_evidence_sheets(evidence: Evidence, sheets: list[SheetGraph]) -> list[str]:
    """The scan `SheetIndex` replaced: test every sheet for an overlap."""
    return sorted(s.sheet_id for s in sheets if not evidence.nodes.isdisjoint(s.graph.nodes))


def test_sheet_index_equals_the_old_scan_on_three_seeds() -> None:
    for seed in range(3):
        corpus = build_synthetic_corpus(
            GeneratorConfig(n_units=6, seed=seed), SplitConfig(sheet_equipment_budget=8, seed=seed)
        )
        index = SheetIndex.from_sheets(corpus.sheets)
        node_ids = sorted(corpus.plant.nodes)
        for start in range(0, len(node_ids), 7):
            evidence = Evidence(nodes=frozenset(node_ids[start : start + 5]), edges=frozenset())
            assert evidence_sheets(evidence, index) == _old_evidence_sheets(evidence, corpus.sheets)
