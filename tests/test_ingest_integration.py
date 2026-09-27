"""Opt-in integration test: the `synthetic` pipeline against a live Neo4j (design §7.7, §8).

Skipped unless `NEO4J_URI`, `NEO4J_USERNAME` and `NEO4J_PASSWORD` are all set
(directly, or via the git-ignored `.env`), exactly like `test_neo4j_integration.py`.
Uses its own dedicated `corpus_id`, distinct from every other test's, and wipes
it again in a `finally` — no other test in the suite touches a live database
from this module.

**Do not run anything large here.** SMOKE-04/05 (1,000/2,900 units) belong to
the main session, not to a pytest run (T8's own instructions).
"""

from __future__ import annotations

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.store.neo4j_loader import wipe_corpus
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env, missing_required_vars

#: never a real experiment's id, so this test can never collide with one.
_CORPUS_ID = "pytest-ingest-integration"

_missing = missing_required_vars()
pytestmark = pytest.mark.skipif(
    bool(_missing),
    reason=f"ingest integration test needs {_missing} (set in the shell or in .env)",
)


def _settings() -> Neo4jSettings:
    settings = from_env()
    if settings is None:
        raise RuntimeError("pytestmark should have skipped this module when settings are absent")
    return settings


def test_run_synthetic_loads_a_tiny_corpus_and_verifies_it() -> None:
    settings = _settings()
    try:
        result = run_synthetic(
            corpus_id=_CORPUS_ID,
            generator_config=GeneratorConfig(n_units=3, seed=0),
            split_config=SplitConfig(sheet_equipment_budget=2, seed=0),
            check=True,
            settings=settings,
        )

        assert result.gate_equal is True
        assert result.load_report is not None
        assert result.load_report.nodes_written == result.counts.n_nodes
        assert result.load_report.relationships_written == result.counts.n_relationships
        assert result.neo4j_version is not None
        assert {"load_wipe", "load_schema", "load_nodes", "load_relationships"} <= set(
            result.stage_seconds
        )
    finally:
        wipe_corpus(settings, _CORPUS_ID)
