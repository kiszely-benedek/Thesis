"""The synthetic benchmark generator: cuts a plant graph into sheets, and produces an answer key.

The orchestration has four steps (splitter.md section 2):

  1. partitioning — which node goes on which sheet (strategies.py),
  2. cutting sheets — turning one sheet's nodes/edges into a graph,
  3. **identity-based** cross-referencing: some equipment gets drawn on more
     than one sheet (splitter.md open question 3),
  4. **off-page connector**: the remaining cross-sheet edges are replaced with
     two stub nodes, and their pairing is recorded in the answer key
     (connectors.py — its own module, because splitter.py would otherwise
     exceed the 400-line file limit).

This module only manipulates the graph; it does not draw an image (splitter.md
section 1).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

import networkx as nx

from plantgraph.benchmark import connectors
from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.strategies import STRATEGIES, StrategyFn


def split(plant: nx.DiGraph[str], config: SplitConfig) -> tuple[list[SheetGraph], SplitManifest]:
    """Cut a full plant graph into sheets, and produce its matching answer key.

    Every random decision goes through a single random.Random seeded from
    config.seed — never touches the global random module, so the "same seed ->
    byte-identical manifest" promise can hold.
    """
    _validate_has_equipment(plant, config.equipment_classes)
    rng = random.Random(config.seed)

    node_sheet = _strategy(config.strategy)(plant, config, rng)
    sheets = _induce_sheets(plant, node_sheet)
    identity_groups, resolved_edges = _duplicate_equipment(plant, sheets, node_sheet, config, rng)
    connector_pairs = connectors.cut_remaining_edges(
        plant, sheets, node_sheet, resolved_edges, config, rng
    )

    all_connectors = [connector for sheet in sheets.values() for connector in sheet.connectors]
    manifest = SplitManifest(
        source="synthetic",
        sheet_files=sorted(sheets),
        strategy=config.strategy,
        seed=config.seed,
        source_graph_hash=_hash_graph(plant),
        connector_pairs=connector_pairs,
        off_page_connectors=all_connectors,
        identity_groups=identity_groups,
    )
    return [sheets[sheet_id] for sheet_id in sorted(sheets)], manifest


def _strategy(name: str) -> StrategyFn:
    try:
        return STRATEGIES[name]
    except KeyError:
        known = sorted(STRATEGIES)
        raise ValueError(f"unknown split strategy {name!r}; choose one of {known}") from None


def _validate_has_equipment(plant: nx.DiGraph[str], equipment_classes: set[str]) -> None:
    has_equipment = any(
        attrs.get("node_class") in equipment_classes for _, attrs in plant.nodes(data=True)
    )
    if not has_equipment:
        raise ValueError(
            f"plant graph has no node with node_class in {sorted(equipment_classes)}; "
            "the splitter needs at least one equipment node to anchor the sheet budget"
        )


def _hash_graph(plant: nx.DiGraph[str]) -> str:
    """A stable fingerprint of the graph — what makes the benchmark instance reproducible."""
    nodes = sorted((node_id, sorted(attrs.items())) for node_id, attrs in plant.nodes(data=True))
    edges = sorted(
        (source, target, sorted(attrs.items())) for source, target, attrs in plant.edges(data=True)
    )
    canonical = repr((nodes, edges)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _induce_sheets(plant: nx.DiGraph[str], node_sheet: dict[str, str]) -> dict[str, SheetGraph]:
    """Copy every node and every within-sheet edge into its own sheet's graph.

    Leaves cross-sheet edges untouched for now — the caller handles those.
    """
    sheets = {
        sheet_id: SheetGraph(sheet_id=sheet_id, graph=nx.DiGraph())
        for sheet_id in sorted(set(node_sheet.values()))
    }
    for node_id, attrs in plant.nodes(data=True):
        sheets[node_sheet[node_id]].graph.add_node(node_id, **attrs)
    for source, target, attrs in plant.edges(data=True):
        if node_sheet[source] == node_sheet[target]:
            sheets[node_sheet[source]].graph.add_edge(source, target, **attrs)
    return sheets


def _duplicate_equipment(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    config: SplitConfig,
    rng: random.Random,
) -> tuple[list[IdentityGroup], set[tuple[str, str]]]:
    """Select a duplication_rate share of the equipment with cross-sheet neighbours.

    This is the **identity-based** cross-referencing (splitter.md open question
    3): the selected equipment gets drawn on every sheet where it has a
    neighbour — one home occurrence with full attributes, and one reference
    occurrence per sheet with the tag and little else. Edges resolved this way
    are no longer cut by the caller with an off-page connector.
    """
    candidates = sorted(
        _equipment_with_cross_sheet_neighbours(plant, node_sheet, config.equipment_classes)
    )
    chosen_count = round(len(candidates) * config.duplication_rate)
    chosen = rng.sample(candidates, chosen_count) if chosen_count else []

    groups: list[IdentityGroup] = []
    resolved_edges: set[tuple[str, str]] = set()
    for node_id in sorted(chosen):
        group, edges = _draw_on_neighbour_sheets(plant, sheets, node_sheet, node_id, config, rng)
        groups.append(group)
        resolved_edges |= edges
    return groups, resolved_edges


def _equipment_with_cross_sheet_neighbours(
    plant: nx.DiGraph[str], node_sheet: dict[str, str], equipment_classes: set[str]
) -> list[str]:
    """The equipment that has a neighbour on another sheet.

    Only these are eligible for duplication.
    """
    result: list[str] = []
    for node_id, attrs in plant.nodes(data=True):
        if attrs.get("node_class") not in equipment_classes:
            continue
        home_sheet = node_sheet[node_id]
        neighbours = set(plant.predecessors(node_id)) | set(plant.successors(node_id))
        if any(node_sheet[neighbour] != home_sheet for neighbour in neighbours):
            result.append(node_id)
    return result


def _draw_on_neighbour_sheets(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    node_id: str,
    config: SplitConfig,
    rng: random.Random,
) -> tuple[IdentityGroup, set[tuple[str, str]]]:
    """Draw a selected piece of equipment onto every one of its neighbouring sheets.

    Connects the local edges to the copy on the sheet where it was drawn.
    """
    home_sheet = node_sheet[node_id]
    home_attrs = plant.nodes[node_id]
    tag = str(home_attrs.get("tag", node_id))
    neighbours = set(plant.predecessors(node_id)) | set(plant.successors(node_id))
    other_sheets = sorted(
        {node_sheet[neighbour] for neighbour in neighbours if node_sheet[neighbour] != home_sheet}
    )

    references: list[str] = []
    tag_variants: dict[str, str] = {}
    resolved_edges: set[tuple[str, str]] = set()
    for sheet_id in other_sheets:
        reference_tag = tag if config.exact_match_tags else _tag_variant(tag, rng)
        sheets[sheet_id].graph.add_node(
            node_id, tag=reference_tag, node_class=home_attrs.get("node_class")
        )
        reference_key = f"{sheet_id}:{node_id}"
        references.append(reference_key)
        if reference_tag != tag:
            tag_variants[reference_key] = reference_tag
        resolved_edges |= _wire_local_edges(plant, sheets[sheet_id], node_id, sheet_id, node_sheet)

    group = IdentityGroup(
        tag=tag, home=f"{home_sheet}:{node_id}", references=references, tag_variants=tag_variants
    )
    return group, resolved_edges


def _wire_local_edges(
    plant: nx.DiGraph[str],
    sheet: SheetGraph,
    node_id: str,
    sheet_id: str,
    node_sheet: dict[str, str],
) -> set[tuple[str, str]]:
    """Connect the duplicated node's edges whose other endpoint also lives on this sheet."""
    resolved: set[tuple[str, str]] = set()
    for _, target, attrs in plant.out_edges(node_id, data=True):
        if node_sheet[target] == sheet_id:
            sheet.graph.add_edge(node_id, target, **attrs)
            resolved.add((node_id, target))
    for source, _, attrs in plant.in_edges(node_id, data=True):
        if node_sheet[source] == sheet_id:
            sheet.graph.add_edge(source, node_id, **attrs)
            resolved.add((source, node_id))
    return resolved


def _tag_variant(tag: str, rng: random.Random) -> str:
    """Perturb the tag away from the home occurrence, so the benchmark isn't trivially matchable.

    On OPEN100, the same pump appears both as RC-P102A and RCS-PU-102A — this
    imitates that with a few simple, but non-systematic, transformations.
    """
    mutations: list[Any] = [
        lambda t: t.replace("-", ""),  # RC-P102A -> RCP102A
        lambda t: t.replace("-", "-0", 1),  # RC-P102A -> RC-0P102A
        lambda t: t.lower(),  # RC-P102A -> rc-p102a
    ]
    return str(rng.choice(mutations)(tag))
