"""A resolver-határ: minden előfordulást átnevez, hogy egyetlen válaszkulcs se szivárogjon át.

A `split()` nyers kimenete (és az importáló kimenete is) még hordozza a
válaszkulcsot: egy duplikált berendezés reference-előfordulása ugyanazt a
node_id-t kapja, mint a home-előfordulása (design §4.1, L1 szivárgás), és a
csonk-csomópontok `OffPageConnector`-listája megmondja a párját akkor is, ha a
rajzon ez nem lenne olvasható (L2 szivárgás). A `localize()` ezt zárja be
(§4.2, D1-a döntés): innentől a resolver, a Neo4j-betöltő és bármely
LLM-prompt csak opak, laponkénti azonosítót lát. Az eredetihez visszavezető
`OccurrenceMap`-et csak a gate és a scoring kód kapja meg — a resolver soha.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import networkx as nx
from pydantic import BaseModel

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema

# 12 hexa karakter = 48 bit. SMOKE-02 kb. 79 ezer előfordulást tartalmaz
# (design §7.5) — ütközés valószínűsége elhanyagolható, de _assign_occurrence_ids
# mégis ellenőrzi, mert a hallgatólagos remény nem bizonyíték.
_OCCURRENCE_ID_LENGTH = 12


class OccurrenceMap(BaseModel):
    """Opak lap-kulcs ("sheet:occ_id") -> eredeti, lap-minősített kulcs ("sheet:node_id").

    Ezt csak a gate (G1/G2/G3) és a scoring kód (`eval/resolution_scoring.py`)
    olvassa — a resolvernek sosem adjuk át, mert pont ez volna a válaszkulcs.
    """

    local_to_original: dict[str, str]

    def original_key(self, local_key: str) -> str:
        """A local_key mögötti eredeti kulcs, lappal együtt."""
        try:
            return self.local_to_original[local_key]
        except KeyError:
            raise ValueError(f"local key {local_key!r} is not in this occurrence map") from None

    def original_node_id(self, local_key: str) -> str:
        """Csak az eredeti csomópont-id, lap nélkül.

        A lap-azonosító sosem tartalmaz ':'-t (`contract.py` ezt ellenőrzi),
        az eredeti node_id viszont igen (pl. az "opc:sheet:0" csonk-id-k) —
        ezért csak az első ':'-nál vágunk, a többit a node_id részének vesszük.
        """
        _, _, node_id = self.original_key(local_key).partition(":")
        return node_id


def localize(
    sheets: Sequence[SheetGraph], salt: str = ""
) -> tuple[list[SheetGraph], OccurrenceMap]:
    """Előfordulás-azonosítókra nevez át, V-tulajdonságokra szűr, törli a connector-listát.

    Minden termelő (szintetikus splitter, Proteus-importáló) ide fut be,
    mielőtt bármi downstream meglátná a lapokat (§4.2 D1-a).

    Args:
        sheets: a nyers lapok (splitter vagy Proteus-importáló kimenete).
        salt: eltérő értékkel teljesen más occ_id-k jönnek ki — ezzel futtatja
            újra a resolvert a G2 kapu (§5.6), hogy egy véletlenül megmaradt
            mintázat se élhesse túl a szivárgás-zárást.
    """
    localized_sheets: list[SheetGraph] = []
    local_to_original: dict[str, str] = {}
    for sheet in sheets:
        occurrence_id = _assign_occurrence_ids(sheet, salt)
        localized_sheets.append(_build_localized_sheet(sheet, occurrence_id))
        _record_mapping(sheet, occurrence_id, local_to_original)
    return localized_sheets, OccurrenceMap(local_to_original=local_to_original)


def _assign_occurrence_ids(sheet: SheetGraph, salt: str) -> dict[str, str]:
    """node_id -> occ_id egy lapon belül; ütközés esetén hibát dob, sosem hallgat el."""
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
    """Egy lap átnevezett, szűrt másolata, rendezett beszúrással.

    A rendezett beszúrás (occ_id szerint, sosem az eredeti sorrendben) zárja
    az L5 szivárgást (§4.1): az eredeti beszúrási sorrend elárulná a plant
    generálási sorrendjét.
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
    """Csak a fehérlistán szereplő kulcsokat tartja meg — ez zárja az L2/L6 szivárgást."""
    return {key: value for key, value in attrs.items() if key in whitelist}


def _record_mapping(
    sheet: SheetGraph, occurrence_id: dict[str, str], local_to_original: dict[str, str]
) -> None:
    """Az adott lap minden előfordulásának eredeti kulcsát felveszi az OccurrenceMap-be."""
    for node_id, occ_id in occurrence_id.items():
        local_key = f"{sheet.sheet_id}:{occ_id}"
        local_to_original[local_key] = f"{sheet.sheet_id}:{node_id}"
