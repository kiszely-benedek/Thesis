"""CypherRAG with a stub database and the fake transport (QA-T12): no Neo4j, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply, message_hash
from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.llm.openrouter_settings import OpenRouterSettings
from plantgraph.qa.cypher import CypherExecutionError, CypherResult, WriteClauseError
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.registry import CypherDeps, build_strategy
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionFamily, QuestionResult
from plantgraph.qa.strategies.base import answer_question
from plantgraph.qa.strategies.cypher_rag import (
    CypherRag,
    extract_query,
    format_context,
    render_cypher_request,
)
from plantgraph.store.neo4j_plan import LoadPlan
from qa_cypher_corpus import four_unit_corpus
from qa_harness_toy import CORPUS_ID, Toy, build_toy, make_config, pin

_ANSWER = '{"answer": "Pump", "not_present": false}'
_QUERY = "MATCH (n {tag: 'P-1'}) RETURN labels(n) AS labels"
_PARAMS = {"timeout_s": 5, "row_cap": 3}


class _StubSource:
    """A database stand-in that returns a scripted result, or raises a scripted error."""

    def __init__(self, result: CypherResult | Exception) -> None:
        self._result = result
        self.queries: list[str] = []
        self.closed = False

    def corpus_id(self) -> str:
        return "stub"

    def schema_text(self) -> str:
        return "STUB-SCHEMA"

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.queries.append(query)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    def close(self) -> None:
        self.closed = True


def _empty() -> _StubSource:
    return _StubSource(CypherResult(rows=[], truncated=False))


def _question() -> Question:
    return Question(
        question_id="q1",
        corpus_id="c",
        family=QuestionFamily.LOOKUP_TYPE,
        template_id="t",
        template_version="1",
        text="What type of item is P-1?",
        answer_type=AnswerType.CLASS_NAME,
        answerable=True,
        reference="Pump",
        generator_seed=0,
    )


def _transport(cypher_reply: str) -> FakeTransport:
    """Replies `cypher_reply` to the query-writing prompt and `_ANSWER` to anything else."""
    request = render_cypher_request(
        pin=pin(), schema_text="STUB-SCHEMA", question_text=_question().text
    )
    return FakeTransport(
        default_reply=ScriptedReply(text=_ANSWER),
        replies_by_message_hash={message_hash(request.messages): ScriptedReply(text=cypher_reply)},
    )


def _send(fake: FakeTransport, tmp_path: Path) -> SendChatRequest:
    client = ChatClient.for_openrouter(
        OpenRouterSettings.model_validate({"api_key": "sk-test"}),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=fake.as_httpx_client(),
    )

    def send(request: ChatRequest) -> ChatResponse:
        return client.complete(request, run_id="test")

    return send


def _strategy(source: _StubSource, fake: FakeTransport, tmp_path: Path) -> CypherRag:
    return CypherRag(source, pin(), _send(fake, tmp_path), timeout_s=5.0, row_cap=3)


def test_rows_become_the_context_and_the_question_is_answered(tmp_path: Path) -> None:
    source = _StubSource(CypherResult(rows=[{"labels": ["Pump"]}], truncated=False))
    fake = _transport(_QUERY)

    result = answer_question(
        _strategy(source, fake, tmp_path),
        _question(),
        pin=pin(),
        wall=None,
        send=_send(fake, tmp_path),
    )

    assert result.outcome is Outcome.ANSWERED
    assert source.queries == [_QUERY]
    assert len(fake.requests) == 2  # one query-writing call, one final call
    final_prompt = json.loads(fake.requests[1].content)["messages"][0]["content"]
    assert _QUERY in final_prompt and '{"labels": ["Pump"]}' in final_prompt
    retrieval_trace = result.trace["retrieval"]
    assert retrieval_trace["cypher"] == _QUERY
    assert retrieval_trace["n_rows"] == 1 and retrieval_trace["empty_result"] is False
    assert retrieval_trace["cypher_call"]["prompt_tokens"] == 10


def test_the_writing_prompt_holds_the_schema_and_the_question_only(tmp_path: Path) -> None:
    fake = _transport(_QUERY)

    _strategy(_empty(), fake, tmp_path).retrieve(_question().text)

    prompt = json.loads(fake.requests[0].content)["messages"][0]["content"]
    assert "STUB-SCHEMA" in prompt and _question().text in prompt
    assert "<<" not in prompt  # every placeholder was filled


def test_an_empty_result_is_reported_and_still_reaches_the_final_step(tmp_path: Path) -> None:
    retrieval = _strategy(_empty(), _transport(_QUERY), tmp_path).retrieve(_question().text)

    assert retrieval.failure is None
    assert retrieval.trace["empty_result"] is True
    assert retrieval.context is not None and "(no rows)" in retrieval.context


def test_truncation_is_recorded(tmp_path: Path) -> None:
    rows = [{"tag": "A"}, {"tag": "B"}, {"tag": "C"}]
    source = _StubSource(CypherResult(rows=rows, truncated=True))

    retrieval = _strategy(source, _transport(_QUERY), tmp_path).retrieve(_question().text)

    assert retrieval.trace["truncated"] is True
    assert retrieval.context is not None and "cut off at the first 3 rows" in retrieval.context


@pytest.mark.parametrize(
    "error",
    [CypherExecutionError("Neo.ClientError.Statement.SyntaxError: bad"), WriteClauseError("SET")],
)
def test_a_failed_query_is_a_retrieval_error_with_no_final_call(
    tmp_path: Path, error: Exception
) -> None:
    fake = _transport(_QUERY)

    result = answer_question(
        _strategy(_StubSource(error), fake, tmp_path),
        _question(),
        pin=pin(),
        wall=None,
        send=_send(fake, tmp_path),
    )

    assert result.outcome is Outcome.RETRIEVAL_ERROR
    assert result.final_answer is None
    assert len(fake.requests) == 1  # only the query-writing call
    assert str(error) in result.trace["retrieval"]["cypher_error"]


def test_a_reply_with_no_query_is_a_retrieval_error(tmp_path: Path) -> None:
    source = _empty()

    retrieval = _strategy(source, _transport("  ```cypher\n```  "), tmp_path).retrieve(
        _question().text
    )

    assert retrieval.failure is Outcome.RETRIEVAL_ERROR
    assert source.queries == []  # nothing was run


@pytest.mark.parametrize(
    ("reply", "query"),
    [
        ("MATCH (n) RETURN n;", "MATCH (n) RETURN n"),
        ("```cypher\nMATCH (n) RETURN n\n```", "MATCH (n) RETURN n"),
        ("Here you go:\n```\nMATCH (n)\nRETURN n;\n```\nDone.", "MATCH (n)\nRETURN n"),
        ("  MATCH (n) RETURN n  ", "MATCH (n) RETURN n"),
    ],
)
def test_extract_query(reply: str, query: str) -> None:
    assert extract_query(reply) == query


def test_context_lists_rows_as_json_lines() -> None:
    result = CypherResult(rows=[{"b": 1, "a": "x"}, {"a": "y"}], truncated=False)
    context = format_context("MATCH (n) RETURN n", result, row_cap=10)
    assert context.endswith('{"a": "x", "b": 1}\n{"a": "y"}')


def test_registry_requires_the_database_and_its_pilot_parameters(tmp_path: Path) -> None:
    corpus = four_unit_corpus()
    view = NetworkxGraphView("c", corpus.localized_sheets, corpus.resolution)
    send = _send(_transport(_QUERY), tmp_path)
    deps = CypherDeps(_empty(), pin(), send)

    with pytest.raises(ValueError, match="database connection"):
        build_strategy("cypher_rag", _PARAMS, view, None)
    with pytest.raises(ValueError, match="row_cap"):
        build_strategy("cypher_rag", {"timeout_s": 5}, view, deps)
    assert build_strategy("cypher_rag", _PARAMS, view, deps).name == "cypher_rag"


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("cypher-toy"), store_profile="occurrence")


def _run(toy: Toy, tmp_path: Path, fake: FakeTransport, factory: object) -> None:
    config = make_config(toy, strategies={"cypher_rag": _PARAMS}, allow_paid_calls=True)
    run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
        cypher_source_factory=factory,  # type: ignore[arg-type]
    )


def test_harness_runs_cypher_rag_through_a_stub_database(toy: Toy, tmp_path: Path) -> None:
    source = _StubSource(CypherResult(rows=[{"tag": "X"}], truncated=False))
    seen_corpora: list[str] = []

    def factory(plan: LoadPlan) -> _StubSource:
        seen_corpora.append(plan.corpus_id)
        return source

    fake = FakeTransport(default_reply=ScriptedReply(text=_ANSWER))
    _run(toy, tmp_path, fake, factory)

    assert seen_corpora == [CORPUS_ID]  # the pre-check hook ran once, for the run's corpus
    assert source.closed
    assert len(fake.requests) == 2 * len(toy.questions)  # every question: write + answer
    run_dir = tmp_path / "runs" / "toy"
    rows = [
        QuestionResult.model_validate_json(line)
        for line in (run_dir / "answers.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(rows) == len(toy.questions)
    assert all(row.strategy == "cypher_rag" for row in rows)
    assert all("cypher" in row.trace["retrieval"] for row in rows)
    calls = (run_dir / "calls.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(line)["purpose"] for line in calls].count("cypher") == len(toy.questions)


def test_a_failing_pre_check_stops_the_run_before_any_call(toy: Toy, tmp_path: Path) -> None:
    def refuse(plan: LoadPlan) -> _StubSource:
        raise RuntimeError("two DrawingSets")

    fake = FakeTransport(default_reply=ScriptedReply(text=_ANSWER))

    with pytest.raises(RuntimeError, match="two DrawingSets"):
        _run(toy, tmp_path, fake, refuse)

    assert fake.requests == []
    assert not (tmp_path / "runs" / "toy").exists()  # not even frozen


def test_the_prompt_separates_a_control_loop_from_the_valve_it_actuates() -> None:
    request = render_cypher_request(pin=pin(), schema_text="STUB", question_text="Q?")

    text = request.messages[0].content
    assert "a control loop is identified by its controller (loop) tag" in text
    assert "separate item with its own tag" in text
    assert text.index("Domain note") < text.index("Question:")
