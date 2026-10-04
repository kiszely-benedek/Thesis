"""PLANT-01: is the plant layer stored in Neo4j the gold plant (ADR-0036, design §A.6)?

The plant layer is the merged graph: one node per physical item, however many
sheets draw it. This check reads it back (`store/plant_readback.py`) and compares
it, with no model and no cost, against the unsplit ground-truth plant the
corpus was generated from. The parts:

- a: the stored graph, renamed to original ids, equals the gold plant (ids, visible properties)
- b: its edges equal the gold edges when items are named by tag (precision / recall)
- c: each item's stored sheets are the sheets of all drawings of its original node
- d: each item's stored unit is its original node's unit
- e: the stored layer equals the in-memory `ItemGraph` that the plant-API agents use

Needs a synthetic corpus (a real import has no gold). Reads Neo4j, writes nothing::

    uv run python -m plantgraph.qa.harness.plant_layer_fidelity --corpus-id H100 \
        --ingest-json data/corpora/H100/ingest.json
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.api_fidelity import EdgeFidelity, TagEdge, compare_tag_edges
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.model import RELATION_GROUPS, sheet_of_key
from plantgraph.resolution.localize import OccurrenceMap
from plantgraph.store.neo4j_settings import from_env
from plantgraph.store.plant_readback import Neo4jSource, StoredPlantLayer, read_plant_layer

_UNTAGGED = "<untagged>"
_SAMPLE = 5
_FOUR_RELATIONS = RELATION_GROUPS["any"]


class Share(BaseModel):
    """How many items agreed, with a few disagreements spelled out."""

    model_config = ConfigDict(frozen=True)

    n_items: int
    n_equal: int
    mismatch_sample: tuple[str, ...]

    @property
    def share(self) -> float:
        """Agreeing items over items; 1.0 when there are none."""
        return self.n_equal / self.n_items if self.n_items else 1.0


class ItemGraphAgreement(BaseModel):
    """Part e: differences from the in-memory `ItemGraph` (none = equal)."""

    model_config = ConfigDict(frozen=True)

    differences: tuple[str, ...]
    #: `related_to` edges stored but not in the `ItemGraph`, which skips them (design F4)
    n_related_to_edges: int


class PlantLayerFidelity(BaseModel):
    """PLANT-01's five parts for one corpus."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n_items: int
    n_edges: int
    a_differences: tuple[str, ...]
    b_edges: EdgeFidelity
    c_sheets: Share
    d_units: Share
    e_item_graph: ItemGraphAgreement

    @property
    def passed(self) -> bool:
        """True when every part meets its pass line (design §A.6)."""
        return (
            self.n_items > 0
            and not self.a_differences
            and self.b_edges.precision == 1.0
            and self.b_edges.recall == 1.0
            and self.c_sheets.share == 1.0
            and self.d_units.share == 1.0
            and not self.e_item_graph.differences
        )


def check_plant_layer(
    layer: StoredPlantLayer,
    gold_plant: nx.DiGraph[str],
    occurrence_map: OccurrenceMap,
    item_graph: ItemGraph,
    corpus_id: str,
) -> PlantLayerFidelity:
    """Run parts a-e; pure, so it works on a layer replayed from rows as well as a stored one."""
    return PlantLayerFidelity(
        corpus_id=corpus_id,
        n_items=layer.graph.number_of_nodes(),
        n_edges=layer.graph.number_of_edges(),
        a_differences=tuple(_differences_with_gold(layer, gold_plant, occurrence_map)),
        b_edges=compare_tag_edges(_stored_tag_edges(layer), gold_plant),
        c_sheets=_sheets_share(layer, occurrence_map),
        d_units=_units_share(layer, gold_plant, occurrence_map),
        e_item_graph=_compare_with_item_graph(layer, item_graph),
    )


# --- a: graph equality with the gold plant ---------------------------------------------------


def _differences_with_gold(
    layer: StoredPlantLayer, gold_plant: nx.DiGraph[str], occurrence_map: OccurrenceMap
) -> list[str]:
    try:
        stored = to_original_ids(visible_view(layer.graph), occurrence_map)
    except ValueError as error:  # two stored items share one original node: an unmerged group
        return [str(error)]
    return graph_differences(_without_none(stored), _without_none(visible_view(gold_plant)))


def _without_none(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """Neo4j stores no null properties; drop them from the gold side so absent equals None."""
    clean: nx.DiGraph[str] = nx.DiGraph()
    for node, attrs in graph.nodes(data=True):
        clean.add_node(node, **_present(attrs))
    for source, target, attrs in graph.edges(data=True):
        clean.add_edge(source, target, **_present(attrs))
    return clean


def _present(attrs: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in attrs.items() if value is not None}


# --- b: edges by tag -------------------------------------------------------------------------


def _stored_tag_edges(layer: StoredPlantLayer) -> set[TagEdge]:
    """The four API relations by tag; an untagged item (an actuator, a stub) reads `<untagged>`."""
    return {
        (_tag(layer, source), attrs["relation"], _tag(layer, target))
        for source, target, attrs in layer.graph.edges(data=True)
        if attrs["relation"] in _FOUR_RELATIONS
    }


def _tag(layer: StoredPlantLayer, home_key: str) -> str:
    tag = layer.graph.nodes[home_key].get("tag")
    return _UNTAGGED if tag is None else str(tag)


# --- c, d: sheets and units per item ---------------------------------------------------------


def _share(items: Iterable[str], same: Callable[[str], str | None]) -> Share:
    """`same(item)` returns None when the item agrees, else a one-line description."""
    results = [(item, same(item)) for item in items]
    mismatches = sorted(f"{item}: {why}" for item, why in results if why is not None)
    return Share(
        n_items=len(results),
        n_equal=len(results) - len(mismatches),
        mismatch_sample=tuple(mismatches[:_SAMPLE]),
    )


def _gold_sheets_by_original(occurrence_map: OccurrenceMap) -> dict[str, set[str]]:
    """Original node id -> the sheets of every drawing of it (the manifest's view)."""
    sheets: dict[str, set[str]] = {}
    for local_key in occurrence_map.local_to_original:
        original = occurrence_map.original_node_id(local_key)
        sheets.setdefault(original, set()).add(sheet_of_key(local_key))
    return sheets


def _sheets_share(layer: StoredPlantLayer, occurrence_map: OccurrenceMap) -> Share:
    gold = _gold_sheets_by_original(occurrence_map)

    def check(home_key: str) -> str | None:
        stored = set(layer.sheets.get(home_key, ()))
        expected = gold.get(occurrence_map.original_node_id(home_key), set())
        return None if stored == expected else f"stored {sorted(stored)} != gold {sorted(expected)}"

    return _share(layer.graph.nodes, check)


def _units_share(
    layer: StoredPlantLayer, gold_plant: nx.DiGraph[str], occurrence_map: OccurrenceMap
) -> Share:
    def check(home_key: str) -> str | None:
        original = occurrence_map.original_node_id(home_key)
        if original not in gold_plant:
            return f"original node {original!r} is not in the gold plant"
        gold_unit = gold_plant.nodes[original].get("unit_id")
        expected = None if gold_unit is None else str(gold_unit)
        stored = layer.units.get(home_key)
        return None if stored == expected else f"stored unit {stored!r} != gold {expected!r}"

    return _share(layer.graph.nodes, check)


# --- e: equality with the in-memory item graph -----------------------------------------------


def _compare_with_item_graph(layer: StoredPlantLayer, item_graph: ItemGraph) -> ItemGraphAgreement:
    differences = _id_differences(layer, item_graph)
    differences += _edge_differences(layer, item_graph)
    differences += _item_differences(layer, item_graph)
    n_related = sum(1 for *_, a in layer.graph.edges(data=True) if a["relation"] == "related_to")
    return ItemGraphAgreement(differences=tuple(differences), n_related_to_edges=n_related)


def _id_differences(layer: StoredPlantLayer, item_graph: ItemGraph) -> list[str]:
    stored, in_memory = set(layer.graph.nodes), set(item_graph.all_ids())
    return [f"item only stored: {k!r}" for k in sorted(stored - in_memory)[:_SAMPLE]] + [
        f"item only in memory: {k!r}" for k in sorted(in_memory - stored)[:_SAMPLE]
    ]


def _edge_differences(layer: StoredPlantLayer, item_graph: ItemGraph) -> list[str]:
    """Edge sets by (source, target, relation); on common edges, `crossed_sheets` vs first `via`."""
    stored = {
        (s, t, a["relation"]): a.get("crossed_sheets")
        for s, t, a in layer.graph.edges(data=True)
        if a["relation"] in _FOUR_RELATIONS
    }
    in_memory = {(e.source, e.target, e.relation): _crossed_sheets(e.via) for e in item_graph.edges}
    differences = [f"edge only stored: {e!r}" for e in sorted(set(stored) - set(in_memory))]
    differences += [f"edge only in memory: {e!r}" for e in sorted(set(in_memory) - set(stored))]
    for edge in sorted(set(stored) & set(in_memory)):
        if stored[edge] != in_memory[edge]:
            differences.append(
                f"edge {edge!r} crossed_sheets stored {stored[edge]!r}, memory {in_memory[edge]!r}"
            )
    return differences[:_SAMPLE]


def _crossed_sheets(via: tuple[str, ...]) -> list[str] | None:
    """The sheets of the first stub pair; an edge with no `via` is drawn whole, so has none."""
    return [sheet_of_key(via[0]), sheet_of_key(via[1])] if via else None


def _item_differences(layer: StoredPlantLayer, item_graph: ItemGraph) -> list[str]:
    differences = []
    for home_key in sorted(set(layer.graph.nodes) & set(item_graph.all_ids())):
        item = item_graph.item(home_key)
        stored = {
            "sheets": layer.sheets.get(home_key, ()),
            "unit": layer.units.get(home_key),
            "occurrences": layer.occurrences.get(home_key, ()),
        }
        expected = {
            "sheets": item.sheets,
            "unit": item.unit_id,
            "occurrences": item.occurrence_keys,
        }
        differences += [
            f"item {home_key!r} {name}: stored {stored[name]!r} != memory {expected[name]!r}"
            for name in stored
            if stored[name] != expected[name]
        ]
    return differences[:_SAMPLE]


# --- report and command line -----------------------------------------------------------------


def render_report(result: PlantLayerFidelity) -> str:
    """The PLANT-01 table: one line per part, then any mismatches."""
    b, e = result.b_edges, result.e_item_graph
    lines = [
        f"PLANT-01 {result.corpus_id}: {result.n_items} items, {result.n_edges} edges "
        f"-> {'PASS' if result.passed else 'FAIL'}",
        f"a graph equals gold (ids, visible properties): {len(result.a_differences)} differences",
        f"b edges by tag: precision {b.precision:.4f}, recall {b.recall:.4f} "
        f"({b.n_matched}/{b.n_gold} gold, {b.n_item_graph} stored)",
        f"c sheets per item: {result.c_sheets.share:.4f}",
        f"d unit per item: {result.d_units.share:.4f}",
        f"e equals ItemGraph: {len(e.differences)} differences "
        f"(related_to edges stored: {e.n_related_to_edges})",
    ]
    lines += [f"  a: {d}" for d in result.a_differences[:_SAMPLE]]
    lines += [f"  b missing: {x}" for x in b.missing_sample] + [
        f"  b extra: {x}" for x in b.extra_sample
    ]
    lines += [f"  c: {m}" for m in result.c_sheets.mismatch_sample]
    lines += [f"  d: {m}" for m in result.d_units.mismatch_sample]
    lines += [f"  e: {d}" for d in e.differences]
    return "\n".join(lines)


def run_plant_layer_fidelity(
    artifacts: CorpusArtifacts, layer: StoredPlantLayer
) -> PlantLayerFidelity:
    """PLANT-01 for a rebuilt synthetic corpus and its stored layer.

    Raises:
        ValueError: the corpus has no gold plant (a real import).
    """
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(
            f"expected a synthetic corpus with a gold plant, found {artifacts.corpus_id!r}"
        )
    view = NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)
    return check_plant_layer(
        layer, plant, artifacts.gold.occurrence_map, build_item_graph(view), artifacts.corpus_id
    )


def main(argv: list[str] | None = None) -> None:
    """Rebuild the corpus, read its plant layer from Neo4j, print the PLANT-01 report."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.harness.plant_layer_fidelity")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    args = parser.parse_args(argv)

    settings = from_env()
    if settings is None:
        raise RuntimeError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD to be set")
    artifacts = load_corpus_artifacts(args.corpus_id, args.ingest_json)
    with Neo4jSource(settings) as source:
        layer = read_plant_layer(source, args.corpus_id)
    result = run_plant_layer_fidelity(artifacts, layer)
    print(render_report(result))
    if not result.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
