"""RU-T5: question reach is uncapped, and enumeration samples before it builds.

Chain toy plants make the reach hand-checkable: node `i` sends to node `i+1`
and every node is its own sheet, so every edge is cut and `k` equals hops.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx
import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.availability import BinTargets, KBin, k_bin_of, k_bin_of_k
from plantgraph.qa.questions.evidence import Evidence, SheetIndex, evidence_sheets
from plantgraph.qa.questions.families_flow import flow_path_candidates
from plantgraph.qa.questions.families_isolation import upstream_isolation_candidates
from plantgraph.qa.questions.sample import draw_sample

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


def test_a_12_hop_chain_yields_a_9_to_16_candidate_the_old_6_hop_cap_would_have_dropped() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))

    questions = _flow(plant, sheets, manifest)

    from_first = {k_bin_of(q) for q in questions if q.anchors[0] == "T-1-00"}
    assert KBin.K9_16 in from_first


def test_at_most_one_flow_path_question_per_source_and_bin() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))

    questions = _flow(plant, sheets, manifest)

    per_cell = Counter((q.anchors[0], k_bin_of(q)) for q in questions)
    assert max(per_cell.values()) == 1
    # T-1-00 reaches k = 1, 2, 3-4, 5-8 and 9-12: five bins, hence five questions.
    from_first = {k_bin for source, k_bin in per_cell if source == "T-1-00"}
    assert from_first == {KBin.K1, KBin.K2, KBin.K3_4, KBin.K5_8, KBin.K9_16}


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
        index = SheetIndex.from_sheets(corpus.sheets, corpus.manifest)
        node_ids = sorted(corpus.plant.nodes)
        for start in range(0, len(node_ids), 7):
            evidence = Evidence(nodes=frozenset(node_ids[start : start + 5]), edges=frozenset())
            assert evidence_sheets(evidence, index) == _old_evidence_sheets(evidence, corpus.sheets)


def test_k_bins_double_and_reject_a_negative_k() -> None:
    edges = {0: KBin.K0, 1: KBin.K1, 2: KBin.K2, 3: KBin.K3_4, 4: KBin.K3_4, 5: KBin.K5_8}
    edges |= {8: KBin.K5_8, 9: KBin.K9_16, 16: KBin.K9_16, 17: KBin.K17_32, 32: KBin.K17_32}
    edges |= {33: KBin.K33_PLUS, 500: KBin.K33_PLUS}
    for k, expected in edges.items():
        assert k_bin_of_k(k) is expected
    with pytest.raises(ValueError, match="k >= 0"):
        k_bin_of_k(-1)


def test_u_counts_evidence_edges_that_change_unit() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * 4)
    plant.nodes["N2"]["unit_id"] = "2"
    plant.nodes["N3"]["unit_id"] = "3"

    questions = _flow(plant, sheets, manifest)

    by_anchors = {tuple(q.anchors): q for q in questions}
    # T-1-00 -> T-1-03 walks N0-N1 (unit 1,1), N1-N2 (1,2), N2-N3 (2,3): two unit changes.
    assert by_anchors[("T-1-00", "T-1-03")].u == 2
    assert by_anchors[("T-1-00", "T-1-01")].u == 0


def test_powered_follows_the_97_rule() -> None:
    plant, sheets, manifest = _chain([NodeClass.TANK] * (_HOPS + 1))
    candidates = {QuestionFamily.FLOW_PATH: _flow(plant, sheets, manifest)}

    _, report = draw_sample(
        candidates, BinTargets(per_bin=1, unanswerable=0), corpus_id=_CORPUS, seed=0
    )

    # the chain has at most 13 candidates in any bin, so none can reach 97
    assert not any(report.powered.values())
    padded = {QuestionFamily.FLOW_PATH: candidates[QuestionFamily.FLOW_PATH] * 20}
    _, padded_report = draw_sample(
        padded, BinTargets(per_bin=1, unanswerable=0), corpus_id=_CORPUS, seed=0
    )
    assert padded_report.powered[KBin.K1] is (padded_report.candidates_per_bin[KBin.K1] >= 97)
    assert padded_report.powered[KBin.K1]
