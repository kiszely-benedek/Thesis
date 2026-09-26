"""The resolver boundary: renames every occurrence so no answer key leaks through.

The raw output of `split()` (and of the importer too) still carries the answer
key: a duplicated equipment's reference occurrence gets the same node_id as its
home occurrence (design §4.1, L1 leak), and the stub nodes' `OffPageConnector`
list states their partner even where that would not be readable on the drawing
(L2 leak). `localize()` seals both off (§4.2, decision D1-a): from here on, the
resolver, the Neo4j loader, and any LLM prompt see only an opaque, per-sheet
identifier. Only the gate checks and the scoring code get the `OccurrenceMap`
that traces back to the original — the resolver never does.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import networkx as nx
from pydantic import BaseModel

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema

# 12 hex characters = 48 bits. SMOKE-02 has roughly 79 thousand occurrences
# (design §7.5) — collision probability is negligible, but _assign_occurrence_ids
# checks anyway, because an implicit hope is not proof.
_OCCURRENCE_ID_LENGTH = 12


class OccurrenceMap(BaseModel):
    """Opaque local key ("sheet:occ_id") -> original, sheet-qualified key ("sheet:node_id").

    Read only by the gate checks (G1/G2/G3) and the scoring code
    (`eval/resolution_scoring.py`) — never handed to the resolver, since this is
    exactly what the answer key would be.
    """

    local_to_original: dict[str, str]

    def original_key(self, local_key: str) -> str:
        """The original key behind a local_key, sheet included."""
        try:
            return self.local_to_original[local_key]
        except KeyError:
            raise ValueError(f"local key {local_key!r} is not in this occurrence map") from None

    def original_node_id(self, local_key: str) -> str:
        """Just the original node id, without the sheet.

        A sheet identifier never contains ':' (`contract.py` checks this), but
        the original node_id sometimes does (e.g. the "opc:sheet:0" stub ids) —
        so we split only at the first ':', treating the rest as part of the node_id.
        """
        _, _, node_id = self.original_key(local_key).partition(":")
        return node_id


def localize(
    sheets: Sequence[SheetGraph], salt: str = ""
) -> tuple[list[SheetGraph], OccurrenceMap]:
    """Rename to occurrence identifiers, filter to V-properties, clear the connector list.

    Every producer (synthetic splitter, Proteus importer) funnels through here
    before any downstream code sees the sheets (§4.2 D1-a).

    Args:
        sheets: the raw sheets (output of the splitter or the Proteus importer).
        salt: a different value produces entirely different occ_ids — the G2
            gate check (§5.6) reruns the resolver with this, so that no leftover
            pattern survives the leak-sealing.
    """
    localized_sheets: list[SheetGraph] = []
    local_to_original: dict[str, str] = {}
    for sheet in sheets:
        occurrence_id = _assign_occurrence_ids(sheet, salt)
        localized_sheets.append(_build_localized_sheet(sheet, occurrence_id))
        _record_mapping(sheet, occurrence_id, local_to_original)
    return localized_sheets, OccurrenceMap(local_to_original=local_to_original)


def _assign_occurrence_ids(sheet: SheetGraph, salt: str) -> dict[str, str]:
    """node_id -> occ_id within one sheet; raises on collision, never suppresses it."""
    occurrence_id: dict[str, str] = {}
    seen_occurrence_ids: set[str] = set()
    for node_id in sheet.graph.nodes:
        digest = hashlib.sha1(f"{salt}{sheet.sheet_id}:{node_id}".encode())
        occ_id = digest.hexdigest()[:_OCCURRENCE_ID_LENGTH]
        if occ_id in seen_occurrence_ids:
            raise ValueError(
                f"occurrence id collision on sheet {sheet.sheet_id!r}: two nodes hash to "
                f"{occ_id!r}; widen _OCCURRENCE_ID_LENGTH or change the salt"
            )
        seen_occurrence_ids.add(occ_id)
        occurrence_id[node_id] = occ_id
    return occurrence_id


def _build_localized_sheet(sheet: SheetGraph, occurrence_id: dict[str, str]) -> SheetGraph:
    """A renamed, filtered copy of a sheet, with sorted insertion.

    Sorted insertion (by occ_id, never in the original order) seals the L5 leak
    (§4.1): the original insertion order would reveal the plant's generation order.
    """
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id in sorted(sheet.graph.nodes, key=lambda n: occurrence_id[n]):
        attrs = _visible(sheet.graph.nodes[node_id], schema.VISIBLE_NODE_PROPERTIES)
        graph.add_node(occurrence_id[node_id], **attrs)
    for source, target in sorted(
        sheet.graph.edges, key=lambda edge: (occurrence_id[edge[0]], occurrence_id[edge[1]])
    ):
        attrs = _visible(sheet.graph.edges[source, target], schema.VISIBLE_EDGE_PROPERTIES)
        graph.add_edge(occurrence_id[source], occurrence_id[target], **attrs)
    return SheetGraph(sheet_id=sheet.sheet_id, graph=graph, connectors=[])


def _visible(attrs: dict[str, Any], whitelist: frozenset[str]) -> dict[str, Any]:
    """Keep only the keys on the whitelist — this seals the L2/L6 leak."""
    return {key: value for key, value in attrs.items() if key in whitelist}


def _record_mapping(
    sheet: SheetGraph, occurrence_id: dict[str, str], local_to_original: dict[str, str]
) -> None:
    """Record this sheet's every occurrence's original key into the OccurrenceMap."""
    for node_id, occ_id in occurrence_id.items():
        local_key = f"{sheet.sheet_id}:{occ_id}"
        local_to_original[local_key] = f"{sheet.sheet_id}:{node_id}"
