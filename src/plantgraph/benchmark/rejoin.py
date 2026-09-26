"""The splitter's inverse: rebuilds the original plant graph from sheets and the answer key.

Used only by the tests — to check that split() loses nothing and adds nothing
(splitter.md section 4, "round-trip invariant"). It has to undo two things: the
off-page connector stubs must be reconnected into the real edge, and the
identity groups' reference occurrences must be merged back into the home node
before the graphs can be compared.
"""

from __future__ import annotations

from typing import cast

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph


def rejoin(sheets: list[SheetGraph], manifest: SplitManifest) -> nx.DiGraph[str]:
    """Rebuild the original graph from sheets and the answer key.

    In two steps: strip the off-page connector stubs and reconnect the cut
    edges, then merge the identity groups' reference occurrences into the home
    node (see the module docstring).
    """
    stub_keys = {connector.key for sheet in sheets for connector in sheet.connectors}
    reference_keys = {
        reference for group in manifest.identity_groups for reference in group.references
    }

    merged: nx.DiGraph[str] = nx.DiGraph()
    for sheet in sheets:
        _copy_sheet_into(merged, sheet, stub_keys, reference_keys)
    for pair in manifest.connector_pairs:
        _reconnect(merged, sheets, pair)
    return merged


def _copy_sheet_into(
    merged: nx.DiGraph[str], sheet: SheetGraph, stub_keys: set[str], reference_keys: set[str]
) -> None:
    """Copy one sheet's nodes/edges into the merged graph, skipping the off-page connector stubs.

    Reference node attributes are deliberately not copied over: those are only
    the stripped-down data visible on the drawing, the real attributes come from
    the home occurrence. Its edges are real, though, so those are copied.
    """
    for node_id, attrs in sheet.graph.nodes(data=True):
        key = f"{sheet.sheet_id}:{node_id}"
        if key in stub_keys:
            continue
        if key in reference_keys:
            merged.add_node(node_id)  # the full attributes will come from the home occurrence
            continue
        merged.add_node(node_id, **attrs)

    for source, target, attrs in sheet.graph.edges(data=True):
        source_key = f"{sheet.sheet_id}:{source}"
        target_key = f"{sheet.sheet_id}:{target}"
        if source_key in stub_keys or target_key in stub_keys:
            continue  # one half of a cut edge — _reconnect restores the real edge
        merged.add_edge(source, target, **attrs)


def _reconnect(merged: nx.DiGraph[str], sheets: list[SheetGraph], pair: ConnectorPair) -> None:
    """Put the original edge back in place of an off-page connector pair.

    The stub edge preserved the attributes, so we read them back from there.
    """
    original_edge = pair.original_edge
    if original_edge is None:
        raise ValueError(
            f"connector pair {pair.from_key} -> {pair.to_key} has no original_edge; "
            "only synthetic pairs can be rejoined"
        )
    attrs = _stub_edge_attrs(sheets, pair.from_key)
    source, target = original_edge
    merged.add_edge(source, target, **attrs)


def _stub_edge_attrs(sheets: list[SheetGraph], key: str) -> dict[str, object]:
    """Find a stub node's single edge.

    Both sides of a stub carry the same original-edge data, so either can be read.
    """
    sheet_id, node_id = key.split(":", 1)
    sheet = next(candidate for candidate in sheets if candidate.sheet_id == sheet_id)
    # a stub has exactly one edge; whether it is outgoing or incoming depends on
    # which side of the cut it landed on — so check both directions
    for _, _, attrs in sheet.graph.out_edges(node_id, data=True):
        return cast(dict[str, object], attrs)
    for _, _, attrs in sheet.graph.in_edges(node_id, data=True):
        return cast(dict[str, object], attrs)
    raise ValueError(f"stub node {key!r} has no incident edge in its sheet graph — insertion bug")
