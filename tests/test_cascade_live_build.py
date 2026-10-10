"""Opening the live cascade from stored tier runs (DA-T2): the store check, refusals, the CLI.

A real toy corpus and real strategies (`context_rag` as the answering tier); the Cypher tier is
named but its store is the wrong profile, which the profile check refuses before any database
is touched. No network, no Neo4j.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.cascade.cli import main
from plantgraph.qa.cascade.live import LivePolicyRefused
from plantgraph.qa.cascade.live_build import OpenedCascade, load_tier_from_run, open_live_cascade
from plantgraph.qa.cascade.live_models import FreeTextQuestion, LiveAnswer
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.store.neo4j_plan import LoadPlan
from qa_harness_toy import CORPUS_ID, Toy, build_toy, make_config, pin, seed_cache

CYPHER_PARAMS = {"timeout_s": 5.0, "row_cap": 10}


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("live-build-toy"))


def _policy(**fields: Any) -> CascadePolicy:
    cypher = TierSpec(
        name="cypher-low",
        strategy="cypher_rag_plant",
        pin_sha256=pin().pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED, AcceptRule.ROWS}),
    )
    agent = TierSpec(
        name="answer",
        strategy="context_rag",
        pin_sha256=pin().pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )
    return CascadePolicy(name="toy-live", tiers=(cypher, agent), **fields)


def _write_tier_runs(toy: Toy, root: Path) -> dict[str, Path]:
    """One frozen `run_config.json` per tier, as the harness writes it."""
    strategies = {"cypher-low": ("cypher_rag_plant", CYPHER_PARAMS), "answer": ("context_rag", {})}
    dirs: dict[str, Path] = {}
    for tier, (strategy, params) in strategies.items():
        run_dir = root / f"run-{tier}"
        RunDir(run_dir).freeze(make_config(toy, run_id=tier, strategies={strategy: params}))
        dirs[tier] = run_dir
    return dirs


def _never_called_factory(_plan: LoadPlan) -> CypherSource:
    raise AssertionError("the store profile check must refuse before the database is opened")


def _open(
    toy: Toy, root: Path, policy: CascadePolicy, transport: FakeTransport | None = None
) -> OpenedCascade:
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    view = NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
    return open_live_cascade(
        corpus_id=CORPUS_ID,
        policy=policy,
        view=view,
        load_plan=artifacts.load_plan,  # profile "occurrence": not what cypher_rag_plant reads
        tier_run_dirs=_write_tier_runs(toy, root),
        cache_path=root / "cache.sqlite",
        calls_log_path=root / "calls.jsonl",
        allow_paid_calls=False,
        cypher_source_factory=_never_called_factory,
        http_client=transport.as_httpx_client() if transport else None,
    )


def test_a_store_that_does_not_hold_the_corpus_leaves_tier_one_out(
    toy: Toy, tmp_path: Path
) -> None:
    question = toy.questions[0]
    seed_cache(toy, tmp_path / "cache.sqlite", [question])
    transport = FakeTransport()

    with _open(toy, tmp_path, _policy(), transport) as opened:
        asked = FreeTextQuestion(
            question_id="free-1", text=question.text, answer_type=question.answer_type
        )
        answer = opened.cascade.ask(asked)

    assert isinstance(answer, LiveAnswer)
    assert answer.policy == "toy-live-no-cypher-low" and not answer.evaluated_policy
    assert answer.notice is not None and "cypher-low" in answer.notice
    assert [report.tier for report in answer.tiers] == ["answer"]
    assert answer.from_cache and transport.requests == []


def test_a_pin_hash_that_differs_from_the_policys_is_refused(toy: Toy, tmp_path: Path) -> None:
    dirs = _write_tier_runs(toy, tmp_path)
    wrong = _policy().tiers[1].model_copy(update={"pin_sha256": "0" * 64})

    with pytest.raises(LivePolicyRefused, match="pin"):
        load_tier_from_run(wrong, dirs["answer"])


def test_a_label_routing_policy_is_refused_before_anything_is_opened(
    toy: Toy, tmp_path: Path
) -> None:
    with pytest.raises(LivePolicyRefused, match="label"):
        _open(toy, tmp_path, _policy(last_tier_by_label={"PATH": 0}))

    assert not (tmp_path / "cache.sqlite").exists()


def test_the_ask_command_end_to_end_replays_a_cached_answer(
    toy: Toy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    question = toy.questions[0]
    seed_cache(toy, tmp_path / "cache.sqlite", [question])
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(_policy().model_dump_json(), encoding="utf-8")
    dirs = _write_tier_runs(toy, tmp_path)

    main(
        [
            "ask",
            "--corpus", CORPUS_ID,
            "--corpora-root", str(toy.corpora_root),
            "--policy", str(policy_file),
            "--run", f"cypher-low={dirs['cypher-low']}",
            "--run", f"answer={dirs['answer']}",
            "--cache-path", str(tmp_path / "cache.sqlite"),
            "--calls-log", str(tmp_path / "calls.jsonl"),
            "--answer-type", question.answer_type.value,
            "--replay-only",  # paid is the default; a replay needs no API key
            question.text,
        ]
    )  # fmt: skip

    out = capsys.readouterr().out
    assert "WARNING: not the evaluated policy" in out
    assert "answered by: answer" in out and "all from cache" in out
