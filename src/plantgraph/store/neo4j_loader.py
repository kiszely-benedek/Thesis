"""Executes a `LoadPlan` against a live Neo4j database (design `kg-construction.md` §7.4, T7).

`neo4j_plan.py` computes what to write with no database connection at all;
this module is the only place in `plantgraph.store` that imports the `neo4j`
driver, and the only place that actually talks to a server. Its steps, each
timed separately for `LoadReport`, are wipe -> schema -> nodes -> relationships
-> verify. Verify counts nodes by label and relationships by type for one
`corpus_id` and raises if either disagrees with the plan's `expected_*` —
this is the loader's own accuracy check, catching a row that silently failed
to match its endpoints or a batch that was skipped, not a claim that the
sheets it was given are themselves correct.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from neo4j import Driver, GraphDatabase, ManagedTransaction, Session
from pydantic import BaseModel

from plantgraph.store.neo4j_plan import CypherStatement, LoadPlan
from plantgraph.store.neo4j_plan import wipe_statement as build_wipe_statement
from plantgraph.store.neo4j_settings import Neo4jSettings


class LoadReport(BaseModel):
    """Timings and counts for one `load_corpus` call, for the run note (§7.6)."""

    corpus_id: str
    nodes_written: int
    relationships_written: int
    batch_size: int
    wipe_s: float
    schema_s: float
    nodes_s: float
    relationships_s: float
    verify_s: float
    total_s: float
    neo4j_version: str | None


def load_corpus(settings: Neo4jSettings, plan: LoadPlan) -> LoadReport:
    """Wipe, load and verify one corpus's `LoadPlan`.

    Raises:
        RuntimeError: if, after loading, the node-label or relationship-type
            counts found for `plan.corpus_id` do not match `plan.expected_*`.
    """
    driver = _open_driver(settings)
    try:
        with driver.session(database=settings.database) as session:
            total_start = time.perf_counter()
            wipe_s = _timed(lambda: _wipe(session, plan.wipe_statement))
            schema_s = _timed(lambda: _run_statements(session, plan.schema_statements))
            nodes_s = _timed(lambda: _run_statements(session, plan.node_statements))
            relationships_s = _timed(lambda: _run_statements(session, plan.relationship_statements))
            verify_s = _timed(lambda: _verify(session, plan))
            total_s = time.perf_counter() - total_start
            neo4j_version = _read_neo4j_version(session)
    finally:
        driver.close()

    return LoadReport(
        corpus_id=plan.corpus_id,
        nodes_written=_total_rows(plan.node_statements),
        relationships_written=_total_rows(plan.relationship_statements),
        batch_size=_batch_size_of(plan.wipe_statement),
        wipe_s=wipe_s,
        schema_s=schema_s,
        nodes_s=nodes_s,
        relationships_s=relationships_s,
        verify_s=verify_s,
        total_s=total_s,
        neo4j_version=neo4j_version,
    )


def wipe_corpus(settings: Neo4jSettings, corpus_id: str, batch_size: int = 5000) -> None:
    """Delete every node of `corpus_id`, with nothing written back in its place.

    `load_corpus` also wipes before it writes, but always as the first step of
    *loading* something — its plan writes at least one `CorpusNode` back (the
    corpus's own bookkeeping row, see `neo4j_plan.wipe_statement`'s
    docstring). Use this instead when a corpus should simply be gone, e.g. an
    integration test's cleanup.
    """
    statement = build_wipe_statement(corpus_id, batch_size)
    driver = _open_driver(settings)
    try:
        with driver.session(database=settings.database) as session:
            _wipe(session, statement)
    finally:
        driver.close()


def _open_driver(settings: Neo4jSettings) -> Driver:
    return GraphDatabase.driver(
        settings.uri, auth=(settings.username, settings.password.get_secret_value())
    )


def _timed(action: Callable[[], None]) -> float:
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


# --- running statements ----------------------------------------------------------------------


def _run_statements(session: Session, statements: Sequence[CypherStatement]) -> None:
    for statement in statements:
        _run_statement(session, statement)


def _run_statement(session: Session, statement: CypherStatement) -> None:
    """One statement, one managed write transaction (design §7.4)."""

    def _write(tx: ManagedTransaction) -> None:
        tx.run(statement.query, statement.parameters).consume()

    session.execute_write(_write)


def _wipe(session: Session, wipe_statement: CypherStatement) -> None:
    """Delete this corpus's nodes batch by batch until nothing is left (§7.4).

    A single `DETACH DELETE` with no `LIMIT` risks one oversized transaction on
    a large corpus; re-running the same `LIMIT`-ed statement is the
    version-independent stand-in for `CALL { ... } IN TRANSACTIONS` the design
    calls for.
    """
    while _run_wipe_batch(session, wipe_statement) > 0:
        pass


def _run_wipe_batch(session: Session, wipe_statement: CypherStatement) -> int:
    def _write(tx: ManagedTransaction) -> int:
        result = tx.run(wipe_statement.query, wipe_statement.parameters)
        record = result.single()
        if record is None:
            raise RuntimeError(
                "wipe batch query returned no row; expected exactly one 'deleted' count"
            )
        return int(record["deleted"])

    return session.execute_write(_write)


# --- verify: the loader's own accuracy check --------------------------------------------------


def _verify(session: Session, plan: LoadPlan) -> None:
    actual_node_labels = _count_node_labels(session, plan.corpus_id)
    actual_relationship_types = _count_relationship_types(session, plan.corpus_id)
    _raise_on_mismatch("node label", actual_node_labels, plan.expected_node_labels)
    _raise_on_mismatch(
        "relationship type", actual_relationship_types, plan.expected_relationship_types
    )


def _count_node_labels(session: Session, corpus_id: str) -> dict[str, int]:
    """Every label found on this corpus's nodes, counted once per node that carries it."""
    query = (
        "MATCH (n:CorpusNode {corpus_id: $corpus_id}) "
        "UNWIND labels(n) AS label RETURN label, count(*) AS n"
    )

    def _read(tx: ManagedTransaction) -> dict[str, int]:
        return {record["label"]: record["n"] for record in tx.run(query, corpus_id=corpus_id)}

    return session.execute_read(_read)


def _count_relationship_types(session: Session, corpus_id: str) -> dict[str, int]:
    """Every relationship type found starting from this corpus's nodes.

    Every relationship this loader ever creates is `CREATE (a)-[r]->(b)` with
    both `a` and `b` in the same corpus, so matching the directed pattern from
    `a` alone (rather than an undirected `-[r]-`) counts each relationship
    exactly once.
    """
    query = (
        "MATCH (a:CorpusNode {corpus_id: $corpus_id})-[r]->() "
        "RETURN type(r) AS rel_type, count(r) AS n"
    )

    def _read(tx: ManagedTransaction) -> dict[str, int]:
        return {record["rel_type"]: record["n"] for record in tx.run(query, corpus_id=corpus_id)}

    return session.execute_read(_read)


def _raise_on_mismatch(kind: str, actual: dict[str, int], expected: dict[str, int]) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{kind} counts after loading do not match: expected {expected}, found {actual}"
        )


# --- report figures computed from the plan, not from what the driver returned -----------------


def _total_rows(statements: Sequence[CypherStatement]) -> int:
    total = 0
    for statement in statements:
        rows = statement.parameters["rows"]
        if not isinstance(rows, list):
            raise TypeError(f"expected a list of rows in statement parameters, got {type(rows)!r}")
        total += len(rows)
    return total


def _batch_size_of(wipe_statement: CypherStatement) -> int:
    value = wipe_statement.parameters["batch_size"]
    if not isinstance(value, int):
        raise TypeError(f"expected an int batch_size in the wipe statement, got {type(value)!r}")
    return value


def _read_neo4j_version(session: Session) -> str | None:
    """The running server's edition and version, for the run note (§7.4).

    `dbms.components()` also reports the bundled Cypher language version
    (e.g. "Cypher 5, 25"), so the query picks out the "Neo4j Kernel" row by
    name rather than taking whatever row comes first. `None` if the procedure
    yields no such row — kept optional because a future Neo4j release could
    remove or rename this legacy procedure.
    """
    query = (
        "CALL dbms.components() YIELD name, versions, edition "
        "WHERE name = 'Neo4j Kernel' RETURN versions, edition"
    )

    def _read(tx: ManagedTransaction) -> str | None:
        record = tx.run(query).single()
        if record is None:
            return None
        versions = record["versions"]
        version = versions[0] if versions else "?"
        return f"Neo4j Kernel {version} ({record['edition']})"

    return session.execute_read(_read)
