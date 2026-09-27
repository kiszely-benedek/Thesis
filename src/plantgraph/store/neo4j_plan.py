"""Cypher and parameter generation for one corpus's load (design `kg-construction.md` §7.4).

No `neo4j` driver import here (T7 adds it in `neo4j_loader.py`): everything in this
module is pure data transformation, so the generated statements can be checked in
tests with no database running. `neo4j_rows.py` decides what each node and
relationship row is; this module turns those rows into batched Cypher.

What gets written, in the vocabulary this module uses:

- A **corpus** is one set of sheets loaded together under one `corpus_id` —
  the unit the loader wipes and reloads as a whole.
- An **occurrence** is one appearance of an equipment or piping symbol on one
  sheet — the same physical pump drawn on two sheets is two occurrences of
  one piece of equipment.
- An **off-page connector** is the stub symbol a drafter uses instead of
  drawing a pipe running off the edge of the sheet; the drawing says "this
  pipe continues on sheet 7", rather than actually crossing sheets.
- `continues_as` links two connector stubs that the resolver decided are the
  two ends of one such cut pipe; `same_tagged_item_as` links a shorthand
  repeat of a tag to the one occurrence that carries the full data for it.

Design decision D2 (§7.1) is to store the **occurrence graph**: every node of
every sheet, stubs included, plus the resolver's cross-sheet links — not a
single collapsed plant graph. This keeps the store lossless with respect to
what was actually drawn, at the cost of the resolver having to be re-applied
by any retrieval strategy that wants a merged view.

Decision D3 (§7.3) is `UNWIND`-batched writes: one `CREATE` per distinct
Neo4j label combination (a "label set") and one per relationship type, each
possibly split into several batches by `batch_size`. Labels and relationship
types can never be Cypher parameters, so they are written into the query
text — but only ever from `schema.labels_for()`, `schema.Relation`, or (the
one exception, ADR-0016 §3.1 rule 7) a `GenericItem` occurrence's own
`dexpi_labels`, each checked in `neo4j_rows.py` before it ever reaches here.
That closed whitelist is what makes writing labels into query text safe:
nothing else ever reaches the query string.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from typing import Literal

from pydantic import BaseModel

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_rows import (
    NodeRow,
    RelationshipRow,
    all_node_rows,
    all_relationship_rows,
    check_unique_uids,
)

#: `corpus_id` becomes part of every generated uid and a literal Cypher property
#: value — never part of query text — but this shape check still guards against
#: accidents (e.g. a stray `|` that would make two different corpora's uids collide).
_CORPUS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class CypherStatement(BaseModel):
    """One parametrized Cypher statement — values only ever travel through `parameters`."""

    query: str
    parameters: dict[str, object]


class LoadPlan(BaseModel):
    """Everything `neo4j_loader.py` (T7) needs to load one corpus, computed with no driver.

    `wipe_statement` is not part of the design's illustrative `LoadPlan` code
    block (`kg-construction.md` §7.4), but its own test list (§7.7) requires a
    wipe query to be checkable without a database, so it is generated here
    alongside every other statement, keyed to the same `corpus_id`.
    """

    corpus_id: str
    schema_statements: list[CypherStatement]
    wipe_statement: CypherStatement
    node_statements: list[CypherStatement]
    relationship_statements: list[CypherStatement]
    expected_node_labels: dict[str, int]
    expected_relationship_types: dict[str, int]


def build_load_plan(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"] = "resolver",
    batch_size: int = 5000,
) -> LoadPlan:
    """Turn localized sheets and their resolution into one corpus's Cypher load plan.

    `sheets` must already be `localize()`d — `check_contract` is run first, so a
    caller who forgot that step fails here with a clear error, the same
    guarantee the resolver itself gives (§4.3).

    Args:
        corpus_id: identifies this load; every uid and wipe is scoped to it.
        sheets: the localized sheets that were also passed to `resolve()`.
        resolution: `resolve(sheets)`'s output — its pairs and identity groups
            become `continues_as` and `same_tagged_item_as` links.
        asserted_by: who is claimed to have found the links — `"resolver"` for
            a normal run, `"oracle"` only for the deferred ground-truth path
            (§7.2, not built yet).
        batch_size: rows per `UNWIND` batch; a starting value, not measured
            (§7.4).

    Raises:
        ValueError: if `corpus_id` or `batch_size` has an unsafe shape, the
            sheets fail `check_contract`, a node's `node_class` is unknown, a
            `GenericItem`'s `dexpi_labels` contains an unsafe label, an edge's
            `relation` is outside the topology whitelist, or two nodes would
            share one uid.
    """
    _validate_corpus_id(corpus_id)
    _validate_batch_size(batch_size)
    check_contract(sheets)
    ordered_sheets = sorted(sheets, key=lambda sheet: sheet.sheet_id)

    node_rows = all_node_rows(corpus_id, ordered_sheets)
    check_unique_uids(node_rows)
    relationship_rows = all_relationship_rows(corpus_id, ordered_sheets, resolution, asserted_by)

    return LoadPlan(
        corpus_id=corpus_id,
        schema_statements=list(_SCHEMA_STATEMENTS),
        wipe_statement=wipe_statement(corpus_id, batch_size),
        node_statements=_node_statements(node_rows, batch_size),
        relationship_statements=_relationship_statements(relationship_rows, batch_size),
        expected_node_labels=_count_labels(node_rows),
        expected_relationship_types=_count_types(relationship_rows),
    )


def _validate_corpus_id(corpus_id: str) -> None:
    if not _CORPUS_ID_PATTERN.match(corpus_id):
        raise ValueError(f"corpus_id {corpus_id!r} must match {_CORPUS_ID_PATTERN.pattern!r}")


def _validate_batch_size(batch_size: int) -> None:
    if batch_size < 1:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size}")


# --- turning rows into batched statements --------------------------------------------------


def _node_statements(rows: Sequence[NodeRow], batch_size: int) -> list[CypherStatement]:
    """One `CREATE` query per distinct label set, split into batches of `batch_size` rows."""
    rows_by_labels: dict[tuple[str, ...], list[NodeRow]] = defaultdict(list)
    for row in rows:
        rows_by_labels[row.labels].append(row)

    statements = []
    for labels in sorted(rows_by_labels):
        query = _node_create_query(labels)
        ordered_rows = sorted(rows_by_labels[labels], key=lambda row: row.uid)
        for batch in _chunk(ordered_rows, batch_size):
            parameters = {"rows": [{"props": row.props} for row in batch]}
            statements.append(CypherStatement(query=query, parameters=parameters))
    return statements


def _node_create_query(labels: tuple[str, ...]) -> str:
    label_text = ":".join(labels)
    return f"UNWIND $rows AS row CREATE (n:{label_text}) SET n = row.props"


def _relationship_statements(
    rows: Sequence[RelationshipRow], batch_size: int
) -> list[CypherStatement]:
    """One `CREATE` query per relationship type, split into batches of `batch_size` rows."""
    rows_by_type: dict[str, list[RelationshipRow]] = defaultdict(list)
    for row in rows:
        rows_by_type[row.rel_type].append(row)

    statements = []
    for rel_type in sorted(rows_by_type):
        query = _relationship_create_query(rel_type)
        ordered_rows = sorted(
            rows_by_type[rel_type], key=lambda row: (row.source_uid, row.target_uid)
        )
        for batch in _chunk(ordered_rows, batch_size):
            parameters = {
                "rows": [
                    {
                        "source_uid": row.source_uid,
                        "target_uid": row.target_uid,
                        "props": row.props,
                    }
                    for row in batch
                ]
            }
            statements.append(CypherStatement(query=query, parameters=parameters))
    return statements


def _relationship_create_query(rel_type: str) -> str:
    return (
        "UNWIND $rows AS row "
        "MATCH (a:CorpusNode {uid: row.source_uid}) MATCH (b:CorpusNode {uid: row.target_uid}) "
        f"CREATE (a)-[r:{rel_type}]->(b) SET r = row.props"
    )


def _chunk[T](rows: Sequence[T], batch_size: int) -> Iterator[Sequence[T]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def _count_labels(rows: Sequence[NodeRow]) -> dict[str, int]:
    """Every label a node carries counts once — this is what `neo4j_loader.py`'s verify checks."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(row.labels)
    return dict(counts)


def _count_types(rows: Sequence[RelationshipRow]) -> dict[str, int]:
    return dict(Counter(row.rel_type for row in rows))


# --- wipe and schema statements: the same for every corpus, aside from the wipe's ids ------


def wipe_statement(corpus_id: str, batch_size: int = 5000) -> CypherStatement:
    """Delete only this corpus's nodes, one `LIMIT`-ed batch per call (§7.4).

    Public so `neo4j_loader.py` (T7) can wipe a corpus on its own, without a
    `LoadPlan` — `build_load_plan` always writes at least one `CorpusNode`
    (the `DrawingSet` row for the corpus itself), so loading an "empty" plan
    is not a way to leave a corpus with zero nodes. `neo4j_loader.py` reruns
    the returned statement until it reports zero deletions — a
    version-independent stand-in for `CALL { ... } IN TRANSACTIONS`.
    """
    _validate_corpus_id(corpus_id)
    _validate_batch_size(batch_size)
    query = (
        "MATCH (n:CorpusNode {corpus_id: $corpus_id}) "
        "WITH n LIMIT $batch_size "
        "DETACH DELETE n RETURN count(*) AS deleted"
    )
    return CypherStatement(
        query=query, parameters={"corpus_id": corpus_id, "batch_size": batch_size}
    )


_SCHEMA_STATEMENTS: tuple[CypherStatement, ...] = (
    CypherStatement(
        query=(
            "CREATE CONSTRAINT corpus_node_uid IF NOT EXISTS "
            "FOR (n:CorpusNode) REQUIRE n.uid IS UNIQUE"
        ),
        parameters={},
    ),
    CypherStatement(
        query=(
            "CREATE INDEX corpus_node_corpus_id IF NOT EXISTS FOR (n:CorpusNode) ON (n.corpus_id)"
        ),
        parameters={},
    ),
    CypherStatement(
        query="CREATE INDEX corpus_node_tag IF NOT EXISTS FOR (n:CorpusNode) ON (n.tag)",
        parameters={},
    ),
)
