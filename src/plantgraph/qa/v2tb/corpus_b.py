"""Loading a B corpus for a run: the B twin of `runner._load_corpus` (design §10 R5, R6).

A B corpus is rebuilt exactly like an A corpus (`load_corpus_artifacts`), then gets its positions:
read from `operating_positions.json`, re-keyed by local key, patched into the load plan and set on
the in-memory view. The run-time loader never generates a plant a second time for the positions.

`require_b` is the runner's rule that a run holds only B corpora (ids ending in `B`). With it off,
a corpus without a positions file loads with no positions at all, which is exactly an A corpus:
that is how the runner-equivalence test runs the B code over an A corpus.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.class_vocabulary import answer_class_names
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.harness.corpus_record import build_corpus_record
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, check_store_profile
from plantgraph.qa.harness.gold import build_gold_scoring
from plantgraph.qa.harness.routing_gold import build_routing_gold
from plantgraph.qa.neo4j_view import Neo4jGraphView
from plantgraph.qa.strategies.cypher_rag import CypherProfile
from plantgraph.qa.v2tb.attempt_b import LoadedCorpusB
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME, read_positions_file
from plantgraph.qa.v2tb.store_b import positions_by_local_key, with_positions
from plantgraph.qa.v2tb.views_b import Neo4jGraphViewB, NetworkxGraphViewB
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import from_env

B_CORPUS_SUFFIX = "B"
#: The store profile the B Cypher arm reads (as V2T-A2's `cypher_rag_lines` does).
B_CYPHER_PROFILE: CypherProfile = "plant_lines"


def open_checked_neo4j_view_b(plan: LoadPlan) -> Neo4jGraphView:
    """Connect with `NEO4J_*` settings and refuse a database that is not exactly this B corpus.

    Copy of `cypher_setup.open_checked_neo4j_view` with the B view.

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
    view = Neo4jGraphViewB(settings, plan)
    try:
        view.check_store()
    except Exception:
        view.close()  # a refused database must not leave a driver open
        raise
    return view


def load_corpus_b(
    corpus_id: str,
    role: str,
    corpora_root: Path,
    *,
    cypher_source_factory: CypherSourceFactory,
    needs_cypher: bool,
    require_b: bool,
) -> LoadedCorpusB:
    """Rebuild one corpus with its positions: the view, the gold inputs and the record.

    Raises:
        ValueError: the corpus has no ground truth, or a position has no valve occurrence or row.
        FileNotFoundError: `require_b` and the corpus has no positions file.
    """
    ingest_path = corpora_root / corpus_id / "ingest.json"
    artifacts = load_corpus_artifacts(corpus_id, ingest_path)
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    if plant is None or manifest is None:
        raise ValueError(f"expected a ground-truth plant and split for {corpus_id!r}, found none")
    by_local_key = _positions_of_corpus(corpus_id, corpora_root, artifacts, require_b)
    plan = with_positions(artifacts.load_plan, by_local_key)
    view = NetworkxGraphViewB(
        corpus_id, artifacts.localized_sheets, artifacts.resolution, by_local_key
    )
    if needs_cypher:
        check_store_profile(plan, B_CYPHER_PROFILE)
    return LoadedCorpusB(
        view=view,
        gold=build_gold_scoring(plant, view),
        routing_gold=build_routing_gold(
            plant, artifacts.gold.sheets, manifest, artifacts.gold.occurrence_map
        ),
        record=build_corpus_record(artifacts, ingest_path, role),
        cypher=cypher_source_factory(plan) if needs_cypher else None,
        class_names=answer_class_names(artifacts.generator_config, artifacts.load_plan),
        plant_index=PlantIndex(plant),
    )


def _positions_of_corpus(
    corpus_id: str, corpora_root: Path, artifacts: CorpusArtifacts, require_b: bool
) -> dict[str, str]:
    """Local key -> code for the corpus; `{}` for an A corpus when `require_b` is off."""
    path = corpora_root / corpus_id / POSITIONS_FILE_NAME
    if not require_b and not path.is_file():
        return {}
    positions, _sha256 = read_positions_file(path)
    return positions_by_local_key(positions, artifacts.gold.occurrence_map)
