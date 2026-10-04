"""The harness's CypherRAG pre-check: open the database and refuse a corpus that does not match.

CypherRAG queries have no corpus filter (`qa-system.md` §2.1 R4), so before a
run that includes it the harness checks that the database holds exactly one
`DrawingSet`, the run's own, with the same node and relationship counts as the
in-memory corpus's `LoadPlan`. The check runs before the run is frozen and
before any call, so a wrong database costs nothing.

The database holds one graph layout, its **store profile** (ADR-0036): `occurrence`
(every drawing as drawn) or `plant` (one node per physical item). `cypher_rag` reads the
first, `cypher_rag_plant` the second, so a run names one Cypher arm only and a store of
another profile is refused. A `both` store is for the demo: a label such as `:Equipment`
would match each item twice there, so no experiment arm reads it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.neo4j_view import Neo4jGraphView, StoreMismatch
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME, CypherProfile
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import from_env

#: Builds the (already checked) database source for one corpus. Tests pass a stub.
CypherSourceFactory = Callable[[LoadPlan], CypherSource]


def required_cypher_profile(strategy_names: Iterable[str]) -> CypherProfile | None:
    """The store profile the run's Cypher arm reads; `None` when the run has no Cypher arm.

    Raises:
        ValueError: both Cypher arms are named; they need differently loaded stores.
    """
    arms = sorted(name for name in strategy_names if name in PROFILE_OF_NAME)
    if len(arms) > 1:
        raise ValueError(
            f"expected one Cypher arm per run, found {arms}: they read differently loaded "
            "stores. Run them separately: load the store with `--store-profile occurrence` for "
            "cypher_rag, then reload it with `--store-profile plant` for cypher_rag_plant"
        )
    return PROFILE_OF_NAME[arms[0]] if arms else None


def check_store_profile(plan: LoadPlan, required: CypherProfile) -> None:
    """Refuse a store whose recorded profile is not the one the Cypher arm reads.

    Raises:
        StoreMismatch: naming both profiles and the ingest option that fixes it.
    """
    if plan.profile != required:
        raise StoreMismatch(
            f"expected the store of {plan.corpus_id!r} to have profile {required!r} for "
            f"{_arm_of(required)}, found {plan.profile!r}. To fix: wipe the corpus and load it "
            f"with `python -m plantgraph.ingest ... --store-profile {required}`"
        )


def _arm_of(profile: CypherProfile) -> str:
    return next(name for name, arm_profile in PROFILE_OF_NAME.items() if arm_profile == profile)


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
            "for a run that includes a Cypher arm, found them unset"
        )
    view = Neo4jGraphView(settings, plan)
    try:
        view.check_store()
    except Exception:
        view.close()  # a refused database must not leave a driver open
        raise
    return view
