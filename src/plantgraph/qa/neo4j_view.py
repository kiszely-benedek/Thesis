"""The Neo4j side of CypherRAG: schema text, one-corpus check, read-only queries (design §5, D9).

Only CypherRAG reads the database; every other strategy reads the in-memory
`NetworkxGraphView`, which holds the same graph. So this view implements the
four things CypherRAG and the harness need (`corpus_id`, `check_store`,
`schema_text`, `run_cypher`) and raises `NotImplementedError` for the rest of
the `GraphView` protocol.

Two checks keep a CypherRAG number honest. The query runs in a read-access
session after the write filter (`cypher.py`). And `check_store` refuses a
database that does not hold exactly the corpus the run names, because a
CypherRAG query has no corpus filter and would otherwise read a mixture.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Any

import networkx as nx
from neo4j import READ_ACCESS, Driver, GraphDatabase, Query, Record, Session
from neo4j.exceptions import Neo4jError
from neo4j.graph import Node, Path, Relationship

from plantgraph.qa.cypher import CypherExecutionError, CypherResult, reject_write_clauses
from plantgraph.qa.graph_view import EdgeRecord, ItemRecord
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_probe import DEFAULT_CONNECTION_TIMEOUT_S
from plantgraph.store.neo4j_settings import Neo4jSettings

#: Store bookkeeping that is never shown to the model (`qa-system.md` §2.1 R3);
#: `via_connector_uids` lists the off-page connector stubs a plant edge was joined through.
_HIDDEN_PROPERTIES = frozenset({"uid", "corpus_id", "via_connector_uids"})
_HIDDEN_LABELS = frozenset({"CorpusNode"})

_REFUSE_HINT = (
    "wipe the other corpora with plantgraph.store.neo4j_loader.wipe_corpus, or load this "
    "corpus into its own database (NEO4J_DATABASE) with `python -m plantgraph.ingest ... "
    "--store-profile occurrence|plant` (the profile the arm reads)"
)


class StoreMismatch(RuntimeError):
    """The database does not hold exactly the corpus the run names."""


def check_single_corpus(found_corpus_ids: Iterable[str], expected_corpus_id: str) -> None:
    """Raise unless the database holds exactly one `DrawingSet`, and it is `expected_corpus_id`.

    Raises:
        StoreMismatch: naming what was found and how to fix it.
    """
    found = sorted(found_corpus_ids)
    if found != [expected_corpus_id]:
        raise StoreMismatch(
            f"expected the database to hold exactly one DrawingSet, {expected_corpus_id!r}; "
            f"found {found}. To fix: {_REFUSE_HINT}"
        )


def check_counts(
    kind: str, found: Mapping[str, int], expected: Mapping[str, int], corpus_id: str
) -> None:
    """Raise if the stored counts (`kind` is "node label" or "relationship type") differ."""
    if dict(found) != dict(expected):
        raise StoreMismatch(
            f"expected the stored {kind} counts of {corpus_id!r} to equal the load plan's "
            f"{dict(expected)}; found {dict(found)}. The store and the in-memory corpus differ; "
            f"reload it with `python -m plantgraph.ingest ... --store-profile occurrence|plant` "
            f"(the profile the arm reads)"
        )


class Neo4jGraphView:
    """A read-only view of one loaded corpus, for CypherRAG and the harness's pre-check."""

    def __init__(self, settings: Neo4jSettings, plan: LoadPlan) -> None:
        self._settings = settings
        self._plan = plan
        self._schema_text = build_schema_text(plan)
        self._driver: Driver | None = None

    def corpus_id(self) -> str:
        """The corpus this view expects the database to hold."""
        return self._plan.corpus_id

    def schema_text(self) -> str:
        """The schema description for the Cypher-writing LLM (see `schema_text.py`)."""
        return self._schema_text

    def close(self) -> None:
        """Close the driver, if a query ever opened one."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def check_store(self) -> None:
        """Refuse unless the database is exactly this corpus, as the load plan describes it.

        Raises:
            StoreMismatch: two `DrawingSet`s, the wrong one, or counts that differ from the plan.
        """
        marker_rows = self._read("MATCH (d:DrawingSet) RETURN d.corpus_id AS corpus_id")
        check_single_corpus([row["corpus_id"] for row in marker_rows], self.corpus_id())
        corpus_id = self.corpus_id()
        stored_labels = self.stored_label_counts()
        check_counts("node label", stored_labels, self._plan.expected_node_labels, corpus_id)
        stored_types = self.stored_relationship_counts()
        check_counts(
            "relationship type", stored_types, self._plan.expected_relationship_types, corpus_id
        )

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        """Run one read-only query in a read-access session, keeping at most `row_cap` rows.

        Raises:
            WriteClauseError: the query contains a write clause; it was not sent.
            CypherExecutionError: a syntax error, a timeout or any other database refusal.
        """
        if row_cap < 1:
            raise ValueError(f"row_cap must be a positive integer, got {row_cap}")
        reject_write_clauses(query)  # before the driver is touched: a rejected query is never sent
        try:
            with self._open_session() as session:
                result = session.run(Query(query, timeout=timeout_s))
                # one row past the cap tells us whether anything was cut off
                records = list(islice(result, row_cap + 1))
                result.consume()
        except Neo4jError as error:
            raise CypherExecutionError(f"{error.code}: {error.message}") from error
        kept = records[:row_cap]
        rows = [_row_dict(record) for record in kept]
        return CypherResult(rows=rows, truncated=len(records) > row_cap)

    # --- the rest of the GraphView protocol: served by NetworkxGraphView instead (D9) ---------

    def items(self) -> list[ItemRecord]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("items")

    def edges(self) -> list[EdgeRecord]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("edges")

    def sheets(self) -> list[str]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("sheets")

    def find_by_tag(self, tag: str) -> list[ItemRecord]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("find_by_tag")

    def unit_ids(self) -> list[str]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("unit_ids")

    def sheets_of_unit(self, unit_id: str) -> list[str]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("sheets_of_unit")

    def sheet_neighbours(self, sheet_id: str) -> list[str]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("sheet_neighbours")

    def subgraph(self, sheet_ids: Iterable[str]) -> nx.DiGraph[str]:
        """Not served here; use `NetworkxGraphView` (D9)."""
        raise _not_served("subgraph")

    # --- internals --------------------------------------------------------------------------

    def _open_session(self) -> Session:
        return self._get_driver().session(
            database=self._settings.database, default_access_mode=READ_ACCESS
        )

    def _get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._settings.uri,
                auth=(self._settings.username, self._settings.password.get_secret_value()),
                connection_timeout=DEFAULT_CONNECTION_TIMEOUT_S,
            )
        return self._driver

    def _read(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self._open_session() as session:
            return [record.data() for record in session.run(query, parameters)]

    def stored_label_counts(self) -> dict[str, int]:
        """Node counts per label for this corpus, as the database holds them."""
        rows = self._read(
            "MATCH (n:CorpusNode {corpus_id: $corpus_id}) "
            "UNWIND labels(n) AS label RETURN label, count(*) AS n",
            corpus_id=self.corpus_id(),
        )
        return {row["label"]: row["n"] for row in rows}

    def stored_relationship_counts(self) -> dict[str, int]:
        """Relationship counts per type for this corpus, as the database holds them."""
        rows = self._read(
            "MATCH (a:CorpusNode {corpus_id: $corpus_id})-[r]->() "
            "RETURN type(r) AS rel_type, count(r) AS n",
            corpus_id=self.corpus_id(),
        )
        return {row["rel_type"]: row["n"] for row in rows}


def _not_served(name: str) -> NotImplementedError:
    return NotImplementedError(
        f"Neo4jGraphView does not implement {name}; only CypherRAG reads Neo4j (D9), "
        "every other strategy uses NetworkxGraphView"
    )


def _row_dict(record: Record) -> dict[str, Any]:
    return {key: _json_ready(record[key]) for key in record.keys()}


def _json_ready(value: Any) -> Any:
    """Turn a driver value into plain JSON types, hiding the store's bookkeeping."""
    if isinstance(value, Node):
        labels = sorted(label for label in value.labels if label not in _HIDDEN_LABELS)
        return {"labels": labels, **_visible_properties(value)}
    if isinstance(value, Relationship):
        return {"type": value.type, **_visible_properties(value)}
    if isinstance(value, Path):
        return {
            "nodes": [_json_ready(node) for node in value.nodes],
            "relationships": [_json_ready(rel) for rel in value.relationships],
        }
    if isinstance(value, list | tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)  # dates and other driver types: their text form is enough


def _visible_properties(entity: Node | Relationship) -> dict[str, Any]:
    properties: dict[str, Any] = dict(entity)
    return {key: val for key, val in properties.items() if key not in _HIDDEN_PROPERTIES}
