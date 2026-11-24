"""LINE-01 for v2.2 plants: the frozen line-view check, with a name for every untagged valve.

The frozen check (`qa.harness.line_view_fidelity`) compares the system's line view with the gold's,
by tag, and raises on a line item that has no tag. A v2.2 document may print no tag on its manual
valves, so this gate makes the same comparison but **names an untagged line item by its place in
the flow graph**: its class and a structural colour (`structure_names.refine_colours`) that depends
on the tagged items around it and on what hangs off it (tees, blind flanges, other valves). Both
sides compute the name from their own flow graph, so a view that wires an untagged valve
differently shows up as a missing or extra line edge, as for a tagged one.

Two untagged items with the same name cannot be told apart by tag, so the comparison would not see
a swap between them. Those names are counted (`key_collisions`) and the gate requires 0.

On a plant whose line items all have tags, every name is the tag itself and the result equals the
frozen check's. Free, no model:

    uv run python -m plantgraph.qa.exp0009.line_view_gate --corpus-id D100g22 --ingest-json <file>
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph.line_view import LINE_ITEM_CLASSES, fold_line_edges
from plantgraph.graph.schema import Relation
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.exp0009.structure_names import refine_colours
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.line_view_fidelity import LineFidelity, LineView, compare_line_views
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.questions.common import is_path_item, next_path_items

#: `(source id, target id, number of pipe parts passed through)`, one per line edge.
IdLineEdge = tuple[str, str, int]
_PREFIX = "<untagged"
_SAMPLE = 5


class LineGateResult(BaseModel):
    """The frozen LINE-01 result, plus how many untagged items and how many names collide."""

    model_config = ConfigDict(frozen=True)

    fidelity: LineFidelity
    n_untagged_items: int
    #: Names carried by more than one untagged line item (a swap between them would go unseen).
    key_collisions: int
    collision_sample: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """The gate: the frozen conditions, and no two untagged items share a name."""
        return self.fidelity.passed and self.key_collisions == 0


@dataclass(frozen=True)
class LineSide:
    """One side's flow graph and line view, by id.

    `tags` and `line_edges` cover the line items only; `classes` and `flow` cover every node, so
    that the structure around an untagged valve (tees, flanges) can name it.
    """

    tags: dict[str, str | None]
    line_edges: list[IdLineEdge]
    classes: dict[str, str]
    flow: list[tuple[str, str]]

    def names(self) -> dict[str, str]:
        """Line item id -> its tag, or for an untagged one its class and structural colour."""
        initial = {n: self.tags.get(n) or c for n, c in self.classes.items()}
        colours = refine_colours(initial, self.flow)
        return {
            item: tag or f"{_PREFIX} {self.classes[item]} {colours[item]}>"
            for item, tag in self.tags.items()
        }

    def view(self, names: Mapping[str, str]) -> LineView:
        """The named line view: item names (repeats kept) and `(source, target)` name -> parts."""
        return list(names.values()), {(names[s], names[t]): n for s, t, n in self.line_edges}


def system_side(graph: ItemGraph) -> LineSide:
    """The system's flow graph, and its line view folded by the frozen `fold_line_edges`."""
    items = [graph.item(item_id) for item_id in graph.all_ids()]
    classes = {item.item_id: item.node_class for item in items}
    tags = {item.item_id: item.tag for item in items}
    flow = [(e.source, e.target) for e in graph.edges if e.relation == "send_to"]
    line_edges = [
        (e.source, e.target, len(e.via_tags) + e.n_fittings)
        for e in fold_line_edges(classes, tags, flow)
    ]
    line_items = [i for i, c in classes.items() if c in LINE_ITEM_CLASSES]
    return LineSide({i: tags[i] for i in line_items}, line_edges, classes, flow)


def gold_side(plant: nx.DiGraph[str]) -> LineSide:
    """The gold plant's flow graph, and its line view from `next_path_items`."""
    items = [n for n in plant.nodes if is_path_item(plant, n)]
    tags = {n: (str(plant.nodes[n]["tag"]) if plant.nodes[n].get("tag") else None) for n in items}
    classes = {n: str(data["node_class"]) for n, data in plant.nodes(data=True)}
    flow = [(s, t) for s, t, d in plant.edges(data=True) if d["relation"] == Relation.SEND_TO.value]
    line_edges = [
        (n, hop.item_id, len(hop.via)) for n in items for hop in next_path_items(plant, n)
    ]
    return LineSide(tags, line_edges, classes, flow)


def compare_sides(corpus_id: str, system: LineSide, gold: LineSide) -> LineGateResult:
    """Name both sides' untagged items, then compare as the frozen LINE-01 does."""
    system_names, gold_names = system.names(), gold.names()
    fidelity = compare_line_views(corpus_id, system.view(system_names), gold.view(gold_names))
    taken = Counter(name for name in system_names.values() if name.startswith(_PREFIX))
    shared = sorted(name for name, n in taken.items() if n > 1)
    return LineGateResult(
        fidelity=fidelity,
        n_untagged_items=sum(taken.values()),
        key_collisions=len(shared),
        collision_sample=tuple(shared[:_SAMPLE]),
    )


def run_line_view_gate(artifacts: CorpusArtifacts) -> LineGateResult:
    """The gate for a rebuilt synthetic corpus.

    Raises:
        ValueError: the corpus has no gold plant (a real import).
    """
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(
            f"expected a synthetic corpus with a gold plant, found {artifacts.corpus_id!r}"
        )
    view = NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)
    system = system_side(build_item_graph(view))
    return compare_sides(artifacts.corpus_id, system, gold_side(plant))


def main(argv: list[str] | None = None) -> None:
    """Rebuild the corpus and print the gate's result; exit 1 when it fails."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.line_view_gate")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_line_view_gate(load_corpus_artifacts(args.corpus_id, args.ingest_json))
    fidelity = result.fidelity
    print(f"LINE-01 (v2.2) {fidelity.corpus_id}: {'PASS' if result.passed else 'FAIL'}")
    print(f"line items: system {fidelity.n_items_system}, gold {fidelity.n_items_gold}")
    print(
        f"line edges: system {fidelity.n_edges_system}, gold {fidelity.n_edges_gold}, "
        f"matched {fidelity.n_matched} "
        f"(precision {fidelity.precision:.4f}, recall {fidelity.recall:.4f})"
    )
    print(f"untagged line items {result.n_untagged_items}, key collisions {result.key_collisions}")
    if not result.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
