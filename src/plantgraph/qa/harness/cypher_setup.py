"""The harness's CypherRAG pre-check: open the database and refuse a corpus that does not match.

CypherRAG queries have no corpus filter (`qa-system.md` §2.1 R4), so before a
run that includes it the harness checks that the database holds exactly one
`DrawingSet`, the run's own, with the same node and relationship counts as the
in-memory corpus's `LoadPlan`. The check runs before the run is frozen and
before any call, so a wrong database costs nothing.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.neo4j_view import Neo4jGraphView
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import from_env

#: Builds the (already checked) database source for one corpus. Tests pass a stub.
CypherSourceFactory = Callable[[LoadPlan], CypherSource]


def open_checked_neo4j_view(plan: LoadPlan) -> Neo4jGraphView:
    """Connect with `NEO4J_*` settings and refuse a database that is not exactly this corpus.

    Raises:
        ValueError: the `NEO4J_*` settings are absent.
        StoreMismatch: two `DrawingSet`s, a different corpus, or differing counts.
    """
    settings = from_env()
    if settings is None:
        raise ValueError(
            "expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD (environment or .env) "
            "for a run that includes cypher_rag, found them unset"
        )
    view = Neo4jGraphView(settings, plan)
    try:
        view.check_store()
    except Exception:
        view.close()  # a refused database must not leave a driver open
        raise
    return view
