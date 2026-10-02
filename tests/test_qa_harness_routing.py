"""Gold-side computations of the harness: routing recall and path-scoring inputs (QA-T10)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import GraphView, NetworkxGraphView
from plantgraph.qa.harness.gold import build_gold_scoring, routing_hit
from plantgraph.qa.harness.registry import STRATEGY_FACTORIES, build_strategy
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import AnswerType, Question, QuestionFamily, RetrievalResult
from plantgraph.qa.strategies.base import Strategy
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("routing-toy"))


class _RoutedTo:
    """A stand-in strategy that claims to have routed to fixed sheets."""

    name = "routed_stub"

    def __init__(self, sheets: list[str]) -> None:
        self._sheets = sheets

    def retrieve(self, question_text: str) -> RetrievalResult:
        return RetrievalResult(
            context="context", failure=None, trace={"routed_sheets": self._sheets}
        )


def _question(evidence_sheets: list[str]) -> Question:
    return Question(
        question_id="q",
        corpus_id="c",
        family=QuestionFamily.LOOKUP_TYPE,
        template_id="t",
        template_version="1",
        text="?",
        answer_type=AnswerType.TAG,
        answerable=bool(evidence_sheets),
        reference="x",
        evidence_sheets=evidence_sheets,
        generator_seed=0,
    )


def test_routing_hit_is_subset_of_routed_sheets() -> None:
    trace: dict[str, Any] = {"retrieval": {"routed_sheets": ["S1", "S2"]}}
    assert routing_hit(_question(["S1"]), trace) is True
    assert routing_hit(_question(["S1", "S3"]), trace) is False


def test_routing_hit_is_none_without_routing_or_evidence() -> None:
    assert routing_hit(_question(["S1"]), {"retrieval": {}}) is None
    assert routing_hit(_question([]), {"retrieval": {"routed_sheets": ["S1"]}}) is None


def test_routing_hit_rejects_a_non_list() -> None:
    with pytest.raises(ValueError, match="list"):
        routing_hit(_question(["S1"]), {"retrieval": {"routed_sheets": "S1"}})


def test_unknown_strategy_is_refused(toy: Toy) -> None:
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    view = NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
    with pytest.raises(ValueError, match="context_rag"):
        build_strategy("no_such_strategy", {}, view)


def test_gold_scoring_collects_flow_edges_and_connector_numbers(toy: Toy) -> None:
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    view = NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
    assert artifacts.gold.plant is not None
    gold = build_gold_scoring(artifacts.gold.plant, view)
    assert gold.valid_edges
    assert gold.connector_tags  # a corpus split over several sheets has connector stubs


@pytest.mark.parametrize(("routed_all", "expected"), [(True, 1.0), (False, 0.0)])
def test_run_reports_routing_recall_from_gold_evidence(
    toy: Toy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    routed_all: bool,
    expected: float,
) -> None:
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    sheets = sorted({sheet.sheet_id for sheet in artifacts.localized_sheets}) if routed_all else []

    def make_stub(view: GraphView, params: dict[str, Any]) -> Strategy:
        return _RoutedTo(params["sheets"])

    monkeypatch.setitem(STRATEGY_FACTORIES, "routed_stub", make_stub)
    config = make_config(toy, strategies={"routed_stub": {"sheets": sheets}}, allow_paid_calls=True)
    fake: FakeTransport = abstaining_transport()

    summary = run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
    )

    assert summary.routing_recall == {"routed_stub": expected}
