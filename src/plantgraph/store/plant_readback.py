"""Read the stored plant layer back out of Neo4j (ADR-0036, merged-plant-layer design §A.6).

The plant layer is the merged graph: one `PlantItem` node per physical thing,
however many sheets it is drawn on. A **home key** is the local key of the
drawing an item was merged into (`S0042:a1b2c3d4e5f6`); it is the item's id
everywhere else in the project, and the stored uid is `<corpus>|item:<home key>`.

`read_plant_layer` runs five read-only queries through a `PlantLayerSource` and
assembles a `StoredPlantLayer`. The source is a one-method protocol so the
assembly is tested against a fake, with no database; `Neo4jSource` is the real
one. Nothing here writes, and nothing here reads the answer key.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol

import networkx as nx
from neo4j import READ_ACCESS, Driver, GraphDatabase

from plantgraph.graph import schema
from plantgraph.store.neo4j_probe import DEFAULT_CONNECTION_TIMEOUT_S
from plantgraph.store.neo4j_settings import Neo4jSettings

#: stored bookkeeping, not part of an item's drawn properties
_BOOKKEEPING = frozenset({"uid", "corpus_id"})
#: only item-to-item relationships of these types are plant edges (the rest are structure)
_EDGE_TYPES = sorted(relation.value for relation in schema.TOPOLOGY_RELATIONS)

ITEMS_QUERY = (
    f"MATCH (i:{schema.PLANT_ITEM_LABEL} {{corpus_id: $corpus_id}}) "
    "RETURN i.uid AS uid, labels(i) AS labels, properties(i) AS properties"
)
EDGES_QUERY = (
    f"MATCH (a:{schema.PLANT_ITEM_LABEL} {{corpus_id: $corpus_id}})-[r]->"
    f"(b:{schema.PLANT_ITEM_LABEL}) WHERE type(r) IN {_EDGE_TYPES} "
    "RETURN a.uid AS source, b.uid AS target, type(r) AS relation, properties(r) AS properties"
)
SHEETS_QUERY = (
    f"MATCH (i:{schema.PLANT_ITEM_LABEL} {{corpus_id: $corpus_id}})-[:is_drawn_on]->(s:Sheet) "
    "RETURN i.uid AS item, s.sheet_id AS value"
)
UNITS_QUERY = (
    f"MATCH (i:{schema.PLANT_ITEM_LABEL} {{corpus_id: $corpus_id}})"
    "-[:is_located_in]->(u:PlantSection) RETURN i.uid AS item, u.unit_id AS value"
)
DRAWN_AS_QUERY = (
    f"MATCH (i:{schema.PLANT_ITEM_LABEL} {{corpus_id: $corpus_id}})-[:drawn_as]->(o) "
    "RETURN i.uid AS item, o.uid AS value"
)

Record = Mapping[str, Any]


class PlantLayerSource(Protocol):
    """Anything that can run one of the queries above for a corpus and return plain rows."""

    def read(self, query: str, corpus_id: str) -> list[Record]:
        """Rows of `query`, each a mapping from the query's column names to values."""
        ...


@dataclass
class StoredPlantLayer:
    """The plant layer as stored: a graph keyed by home key, plus what hangs off each item."""

    #: node attributes = stored item properties (no uid/corpus_id); edge attributes =
    #: `relation` (the Neo4j type) and the stored relationship properties
    graph: nx.DiGraph[str] = field(default_factory=nx.DiGraph)
    #: home key -> the item's label chain, including `PlantItem`
    labels: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: home key -> sheet ids from `is_drawn_on`, sorted
    sheets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: home key -> unit id from `is_located_in`; an item with no unit is absent
    units: dict[str, str] = field(default_factory=dict)
    #: home key -> local keys of the occurrences from `drawn_as`, sorted
    occurrences: dict[str, tuple[str, ...]] = field(default_factory=dict)


def read_plant_layer(source: PlantLayerSource, corpus_id: str) -> StoredPlantLayer:
    """Read one corpus's plant layer; empty (no items) if it was loaded with profile `occurrence`.

    Raises:
        ValueError: a row names an item that is not in the layer, or a uid of another corpus.
    """
    layer = StoredPlantLayer()
    for row in source.read(ITEMS_QUERY, corpus_id):
        _add_item(layer, corpus_id, row)
    for row in source.read(EDGES_QUERY, corpus_id):
        _add_edge(layer, corpus_id, row)
    _add_sheets(layer, corpus_id, source.read(SHEETS_QUERY, corpus_id))
    _add_units(layer, corpus_id, source.read(UNITS_QUERY, corpus_id))
    _add_occurrences(layer, corpus_id, source.read(DRAWN_AS_QUERY, corpus_id))
    return layer


# --- uids -> keys -------------------------------------------------------------------------------


def _strip(uid: str, prefix: str, what: str) -> str:
    if not uid.startswith(prefix):
        raise ValueError(f"expected a {what} uid starting with {prefix!r}, found {uid!r}")
    return uid[len(prefix) :]


def _home_key(corpus_id: str, item_uid: str) -> str:
    return _strip(item_uid, f"{corpus_id}|item:", "plant item")


def _known_home_key(layer: StoredPlantLayer, corpus_id: str, item_uid: str) -> str:
    key = _home_key(corpus_id, item_uid)
    if key not in layer.graph:
        raise ValueError(f"expected item {key!r} to be read before its relationships; not found")
    return key


# --- assembling ---------------------------------------------------------------------------------


def _add_item(layer: StoredPlantLayer, corpus_id: str, row: Record) -> None:
    key = _home_key(corpus_id, row["uid"])
    attrs = {k: v for k, v in row["properties"].items() if k not in _BOOKKEEPING}
    layer.graph.add_node(key, **attrs)
    layer.labels[key] = tuple(row["labels"])


def _add_edge(layer: StoredPlantLayer, corpus_id: str, row: Record) -> None:
    source = _known_home_key(layer, corpus_id, row["source"])
    target = _known_home_key(layer, corpus_id, row["target"])
    if layer.graph.has_edge(source, target):
        # nx.DiGraph holds one edge per pair, as the gold plant does; refuse rather than merge
        raise ValueError(
            f"expected one relationship between {source!r} and {target!r}, found a second: "
            f"{layer.graph.edges[source, target]['relation']!r} and {row['relation']!r}"
        )
    layer.graph.add_edge(source, target, relation=row["relation"], **row["properties"])


def _grouped(layer: StoredPlantLayer, corpus_id: str, rows: list[Record]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[_known_home_key(layer, corpus_id, row["item"])].append(row["value"])
    return grouped


def _add_sheets(layer: StoredPlantLayer, corpus_id: str, rows: list[Record]) -> None:
    for key, sheet_ids in _grouped(layer, corpus_id, rows).items():
        layer.sheets[key] = tuple(sorted(sheet_ids))


def _add_units(layer: StoredPlantLayer, corpus_id: str, rows: list[Record]) -> None:
    for key, unit_ids in _grouped(layer, corpus_id, rows).items():
        if len(unit_ids) != 1:
            raise ValueError(f"expected one unit for item {key!r}, found {sorted(unit_ids)}")
        layer.units[key] = unit_ids[0]


def _add_occurrences(layer: StoredPlantLayer, corpus_id: str, rows: list[Record]) -> None:
    for key, uids in _grouped(layer, corpus_id, rows).items():
        local_keys = [_strip(uid, f"{corpus_id}|", "occurrence") for uid in uids]
        layer.occurrences[key] = tuple(sorted(local_keys))


# --- the real source ----------------------------------------------------------------------------


class Neo4jSource:
    """Runs the readback queries in read-access sessions; a context manager that owns the driver."""

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver: Driver = GraphDatabase.driver(
            settings.uri,
            auth=(settings.username, settings.password.get_secret_value()),
            connection_timeout=DEFAULT_CONNECTION_TIMEOUT_S,
        )

    def read(self, query: str, corpus_id: str) -> list[Record]:
        """Rows of `query` as plain dicts, from a read-only session."""
        with self._driver.session(
            database=self._settings.database, default_access_mode=READ_ACCESS
        ) as session:
            return [record.data() for record in session.run(query, corpus_id=corpus_id)]

    def close(self) -> None:
        """Close the driver."""
        self._driver.close()

    def __enter__(self) -> Neo4jSource:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
