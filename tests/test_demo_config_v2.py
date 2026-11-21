"""The shipped v2 demo configs load, and the local EXP-0008 config is consistent with its data.

Offline: no Neo4j, no paid call. The data-dependent tests skip when this checkout lacks
`data/runs/exp0008/demo/` (the run outputs are not part of every clone).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.demo.app.config import DemoConfig, load_demo_config, resolve_policy
from plantgraph.demo.app.need_routing import route_question, split_by_start
from plantgraph.demo.app.results import check_results_sources
from plantgraph.qa.anchors import Anchors

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "src" / "plantgraph" / "demo" / "app"
LOCAL_CONFIG = ROOT / "data" / "runs" / "exp0008" / "demo" / "demo_config.json"
ISOLATION_FAMILY = "UPSTREAM_ISOLATION"

needs_data = pytest.mark.skipif(not LOCAL_CONFIG.exists(), reason="EXP-0008 demo data not present")


def _example_ids(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["question_id"] for line in lines]


def _example_rows(path: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_both_shipped_examples_validate() -> None:
    # Both files are plain JSON: validating needs no data on disk.
    for name in ("demo_config.example.json", "demo_config.v1.example.json"):
        DemoConfig.model_validate_json((APP_DIR / name).read_text(encoding="utf-8"))


def test_v2_example_names_the_v2_policy_and_tiers() -> None:
    config = DemoConfig.model_validate_json(
        (APP_DIR / "demo_config.example.json").read_text(encoding="utf-8")
    )
    assert config.policy.endswith("cascade_v4_iso.json")
    assert all(set(c.tier_runs) == {"cypher-v2t", "agent-v2t"} for c in config.corpora)


def test_v1_example_keeps_the_v1_policy() -> None:
    config = DemoConfig.model_validate_json(
        (APP_DIR / "demo_config.v1.example.json").read_text(encoding="utf-8")
    )
    assert config.policy == "cascade_v3"


@needs_data
def test_local_config_loads_with_two_plants() -> None:
    config = load_demo_config(LOCAL_CONFIG)
    assert [c.corpus_id for c in config.corpora] == ["H1000g21p1", "H100g21p1"]
    assert len(resolve_policy(config.policy).tiers) == 2


@needs_data
def test_every_presentation_id_exists_in_its_examples_file() -> None:
    config = load_demo_config(LOCAL_CONFIG)
    assert config.presentation, "expected the local config to carry presentation sequences"
    for sequence in config.presentation:
        corpus = config.corpus(sequence.corpus_id)
        assert corpus is not None and corpus.questions_jsonl is not None
        known = set(_example_ids(ROOT / corpus.questions_jsonl))
        asked = [s.question_id for s in sequence.steps if s.kind == "example"]
        assert set(asked) <= known, f"{sequence.title}: unknown ids {set(asked) - known}"


@needs_data
def test_isolation_steps_are_routed_to_the_agent() -> None:
    # The isolation rule reads wording only (no unit in these questions), so no anchors are needed.
    config = load_demo_config(LOCAL_CONFIG)
    routed = split_by_start(resolve_policy(config.policy))
    for sequence in config.presentation:
        corpus = config.corpus(sequence.corpus_id)
        assert corpus is not None and corpus.questions_jsonl is not None
        rows = {r["question_id"]: r for r in _example_rows(ROOT / corpus.questions_jsonl)}
        steps = [s.question_id for s in sequence.steps if s.kind == "example"]
        isolation = [i for i in steps if rows[str(i)]["family"] == ISOLATION_FAMILY]
        for question_id in isolation:
            route = route_question(rows[str(question_id)]["text"], lambda _t: Anchors(), routed)
            assert route.routed and route.start_tier == "agent-v2t"


@needs_data
def test_startup_results_check_passes_on_the_local_config() -> None:
    config = load_demo_config(LOCAL_CONFIG)
    # Raises on a missing report, an unknown plant row, infra row or e2e arm.
    check_results_sources(config.results, config.corpora)
