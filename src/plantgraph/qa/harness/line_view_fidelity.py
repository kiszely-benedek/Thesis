"""LINE-01: does the system's line view equal the gold's independent one?

The line view (`graph/line_view.py`) folds flow through untagged pipe parts into item-to-item
"line" edges. It is built from the resolved drawings, the only thing the Q&A system may see. The
gold side computes the same relation from the unsplit ground-truth plant
(`qa.questions.common.next_path_items`), with its own code. This check, free and with no model,
compares the two by tag: every line item and every line edge must agree (precision = recall = 1).

    uv run python -m plantgraph.qa.harness.line_view_fidelity --corpus-id D100g2 \
        --ingest-json data/runs/exp0007/dev_check/neo4jplant/D100g2/ingest.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph.line_view import LINE_ITEM_CLASSES, LineEdge, fold_line_edges
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.questions.common import is_path_item, next_path_items

#: `(from_tag, to_tag)`; both ends of a line edge are tagged line items.
TagPair = tuple[str, str]
_SAMPLE = 5


class LineFidelity(BaseModel):
    """Agreement of the system's line view with the gold's, by tag."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n_items_system: int
    n_items_gold: int
    items_only_in_system: tuple[str, ...]
    items_only_in_gold: tuple[str, ...]
    n_edges_system: int
    n_edges_gold: int
    n_matched: int
    missing_sample: tuple[TagPair, ...]
    extra_sample: tuple[TagPair, ...]
    #: Matched edges whose number of passed pipe parts differs (informational: the two sides
    #: break a tie between equally short routes with different ids).
    n_passed_count_differences: int

    @property
    def precision(self) -> float:
        """Share of the system's line edges that are gold edges."""
        return self.n_matched / self.n_edges_system if self.n_edges_system else 1.0

    @property
    def recall(self) -> float:
        """Share of the gold's line edges the system has."""
        return self.n_matched / self.n_edges_gold if self.n_edges_gold else 1.0

    @property
    def passed(self) -> bool:
        """The gate: same line items, precision = recall = 1."""
        return (
            not self.items_only_in_system
            and not self.items_only_in_gold
            and self.precision == 1.0
            and self.recall == 1.0
        )


def system_line_view(graph: ItemGraph) -> tuple[set[str], dict[TagPair, int]]:
    """The system's line items (tags) and line edges (tag pair -> passed-part count).

    Raises:
        ValueError: a line item has no tag, so it cannot be compared with the gold.
    """
    items = [graph.item(item_id) for item_id in graph.all_ids()]
    classes = {item.item_id: item.node_class for item in items}
    tags = {item.item_id: item.tag for item in items}
    untagged = [i for i, c in classes.items() if c in LINE_ITEM_CLASSES and not tags[i]]
    if untagged:
        raise ValueError(f"expected every line item to have a tag, found none on {untagged[:3]}")
    flow = [(e.source, e.target) for e in graph.edges if e.relation == "send_to"]
    edges = fold_line_edges(classes, tags, flow)
    line_item_tags = {str(tags[i]) for i, c in classes.items() if c in LINE_ITEM_CLASSES}
    return line_item_tags, {
        (str(tags[e.source]), str(tags[e.target])): _passed_count(e) for e in edges
    }


def _passed_count(edge: LineEdge) -> int:
    return len(edge.via_tags) + edge.n_fittings


def gold_line_view(plant: nx.DiGraph[str]) -> tuple[set[str], dict[TagPair, int]]:
    """The gold's line items (tags) and line edges, from `next_path_items` on the gold plant."""
    items: set[str] = set()
    edges: dict[TagPair, int] = {}
    for node_id in plant.nodes:
        if not is_path_item(plant, node_id):
            continue
        source_tag = str(plant.nodes[node_id]["tag"])
        items.add(source_tag)
        for hop in next_path_items(plant, node_id):
            edges[(source_tag, str(plant.nodes[hop.item_id]["tag"]))] = len(hop.via)
    return items, edges


def compare_line_views(
    corpus_id: str,
    system: tuple[set[str], dict[TagPair, int]],
    gold: tuple[set[str], dict[TagPair, int]],
) -> LineFidelity:
    """Compare two `(items, edges)` line views."""
    (items_s, edges_s), (items_g, edges_g) = system, gold
    matched = edges_s.keys() & edges_g.keys()
    return LineFidelity(
        corpus_id=corpus_id,
        n_items_system=len(items_s),
        n_items_gold=len(items_g),
        items_only_in_system=tuple(sorted(items_s - items_g)[:_SAMPLE]),
        items_only_in_gold=tuple(sorted(items_g - items_s)[:_SAMPLE]),
        n_edges_system=len(edges_s),
        n_edges_gold=len(edges_g),
        n_matched=len(matched),
        missing_sample=tuple(sorted(edges_g.keys() - edges_s.keys())[:_SAMPLE]),
        extra_sample=tuple(sorted(edges_s.keys() - edges_g.keys())[:_SAMPLE]),
        n_passed_count_differences=sum(edges_s[p] != edges_g[p] for p in matched),
    )


def run_line_view_fidelity(artifacts: CorpusArtifacts) -> LineFidelity:
    """LINE-01 for a rebuilt synthetic corpus.

    Raises:
        ValueError: the corpus has no gold plant (a real import).
    """
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(
            f"expected a synthetic corpus with a gold plant, found {artifacts.corpus_id!r}"
        )
    view = NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)
    return compare_line_views(
        artifacts.corpus_id, system_line_view(build_item_graph(view)), gold_line_view(plant)
    )


def render_report(result: LineFidelity) -> str:
    """The check's result as plain text."""
    lines = [
        f"LINE-01 {result.corpus_id}: {'PASS' if result.passed else 'FAIL'}",
        f"line items: system {result.n_items_system}, gold {result.n_items_gold}",
        f"line edges: system {result.n_edges_system}, gold {result.n_edges_gold}, "
        f"matched {result.n_matched} "
        f"(precision {result.precision:.4f}, recall {result.recall:.4f})",
        f"matched edges with a different number of passed parts: "
        f"{result.n_passed_count_differences}",
    ]
    lines += [f"  item only in system: {t}" for t in result.items_only_in_system]
    lines += [f"  item only in gold: {t}" for t in result.items_only_in_gold]
    lines += [f"  edge missing: {pair}" for pair in result.missing_sample]
    lines += [f"  edge extra: {pair}" for pair in result.extra_sample]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """Rebuild the corpus and print the LINE-01 report; exit 1 when it fails."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.harness.line_view_fidelity")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_line_view_fidelity(load_corpus_artifacts(args.corpus_id, args.ingest_json))
    print(render_report(result))
    if not result.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
