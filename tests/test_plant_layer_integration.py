"""Opt-in integration test: each store profile loads, verifies and passes its invariants (ADR-0036).

Skipped unless Neo4j credentials are set and the database answers
(`conftest.neo4j_skip_reason`), like the other live-database modules. Each test
loads a disposable `pytest-plant-<profile>` corpus and wipes it in a `finally`;
`load_corpus` itself raises on a count mismatch or a non-zero invariant, so
reaching the assertions already means the invariant queries returned 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import neo4j_skip_reason
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_loader import load_corpus, wipe_corpus
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env
from store_toy_corpus import toy_corpus

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: invariants expected to run per profile (design §A.5)
_INVARIANTS_PER_PROFILE = {"occurrence": 0, "plant": 2, "both": 7}

_skip_reason = neo4j_skip_reason()
pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")


def _toy() -> tuple[list[SheetGraph], Resolution]:
    return toy_corpus(duplication_rate=0.5)


def _ex01() -> tuple[list[SheetGraph], Resolution] | None:
    """`None` when the untracked file is absent — the caller skips instead."""
    if not _EX01_PATH.exists():
        return None
    imported = import_proteus_sheet(_EX01_PATH)
    localized, _occurrence_map = localize([imported.sheet])
    return localized, resolve(localized)


def _settings() -> Neo4jSettings:
    settings = from_env()
    if settings is None:
        raise RuntimeError("pytestmark should have skipped this module when settings are absent")
    return settings


@pytest.mark.parametrize("corpus_factory", [_toy, _ex01])
@pytest.mark.parametrize("profile", ["occurrence", "plant", "both"])
def test_each_profile_loads_verifies_and_passes_its_invariants(
    profile: str,
    corpus_factory,  # type: ignore[no-untyped-def]
) -> None:
    corpus = corpus_factory()
    if corpus is None:
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    sheets, resolution = corpus
    corpus_id = f"pytest-plant-{profile}"
    plan = build_load_plan(corpus_id, sheets, resolution, profile=profile)  # type: ignore[arg-type]
    settings = _settings()

    try:
        report = load_corpus(settings, plan)
        assert report.invariants_checked == _INVARIANTS_PER_PROFILE[profile]
        # every node carries `CorpusNode`, so that label's count is the node total
        assert report.nodes_written == plan.expected_node_labels["CorpusNode"]
    finally:
        wipe_corpus(settings, corpus_id)
