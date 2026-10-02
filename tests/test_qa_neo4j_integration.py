"""Opt-in integration test: CypherRAG's database side against a live Neo4j (QA-T12).

Skipped unless the database answers (`conftest.neo4j_skip_reason`). It loads
the 4-unit corpus under two throw-away corpus ids and wipes exactly those two
in a finalizer; any other corpus in the database is only ever read, never
written. Hand-written Cypher stands in for the LLM: it must return what the
networkx reference (the question's `reference`, computed on the ground-truth
plant) says. The Cypher-writing LLM is the fake transport.

Because the database may hold other corpora, every hand-written query pins its
anchor node to the test corpus. A real CypherRAG query has no such filter: the
one-corpus check is what makes that safe (`qa-system.md` §2.1 R4).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from conftest import neo4j_skip_reason
from plantgraph.ingest.pipeline import SyntheticCorpus
from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.llm.openrouter_settings import OpenRouterSettings
from plantgraph.qa.cypher import CypherExecutionError, WriteClauseError
from plantgraph.qa.models import Outcome, Question, QuestionFamily
from plantgraph.qa.neo4j_view import Neo4jGraphView, StoreMismatch
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.strategies.cypher_rag import CypherRag
from plantgraph.store.neo4j_loader import load_corpus, wipe_corpus
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env
from qa_cypher_corpus import four_unit_corpus, load_plan_of
from qa_harness_toy import pin

#: never a real experiment's id, so these tests can never collide with one.
_CORPUS_ID = "pytest-qa-t12"
_SECOND_CORPUS_ID = "pytest-qa-t12-b"

_TIMEOUT_S = 30.0
_ROW_CAP = 5000

_skip_reason = neo4j_skip_reason()
pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")


@dataclass
class Loaded:
    settings: Neo4jSettings
    corpus: SyntheticCorpus
    plan: LoadPlan
    view: Neo4jGraphView
    questions: dict[QuestionFamily, list[Question]]


@pytest.fixture(scope="module")
def loaded() -> Iterator[Loaded]:
    settings = from_env()
    assert settings is not None  # pytestmark skips the module otherwise
    corpus = four_unit_corpus()  # G1 is asserted inside, before anything is loaded
    plan = load_plan_of(corpus, _CORPUS_ID)
    view = Neo4jGraphView(settings, plan)
    try:
        load_corpus(settings, plan)
        questions = all_candidates(
            corpus.plant, corpus.manifest, corpus.sheets, corpus_id=_CORPUS_ID, seed=0
        )
        yield Loaded(settings, corpus, plan, view, questions)
    finally:
        view.close()
        wipe_corpus(settings, _CORPUS_ID)
        wipe_corpus(settings, _SECOND_CORPUS_ID)


def _anchor(variable: str, tag: str) -> str:
    """A node pattern pinned to the test corpus (the database may hold other corpora)."""
    return f"({variable}:CorpusNode {{corpus_id: '{_CORPUS_ID}', tag: '{tag}'}})"


def _run(loaded: Loaded, query: str) -> list[dict[str, object]]:
    result = loaded.view.run_cypher(query, timeout_s=_TIMEOUT_S, row_cap=_ROW_CAP)
    assert not result.truncated
    return result.rows


def _sample(loaded: Loaded, family: QuestionFamily, n: int) -> list[Question]:
    return loaded.questions[family][:n]


def _crossing_first(questions: list[Question], n: int) -> list[Question]:
    """Questions that cross sheets first, so the sample is not all k = 0."""
    return sorted(questions, key=lambda q: -(q.k or 0))[:n]


def test_the_loaded_store_matches_the_load_plan(loaded: Loaded) -> None:
    assert loaded.view.stored_label_counts() == loaded.plan.expected_node_labels
    assert loaded.view.stored_relationship_counts() == loaded.plan.expected_relationship_types


def test_lookup_type_matches_the_reference(loaded: Loaded) -> None:
    for question in _sample(loaded, QuestionFamily.LOOKUP_TYPE, 4):
        rows = _run(loaded, f"MATCH {_anchor('n', question.anchors[0])} RETURN labels(n) AS labels")
        assert len(rows) == 1
        assert question.reference in rows[0]["labels"]  # type: ignore[operator]


def test_lookup_unit_matches_the_reference_through_the_plant_section(loaded: Loaded) -> None:
    for question in _sample(loaded, QuestionFamily.LOOKUP_UNIT, 4):
        query = (
            f"MATCH {_anchor('n', question.anchors[0])}-[:is_located_in]->(s:PlantSection) "
            "RETURN s.unit_id AS unit"
        )
        assert [row["unit"] for row in _run(loaded, query)] == [question.reference]


def test_downstream_neighbours_match_the_reference_across_sheets(loaded: Loaded) -> None:
    candidates = loaded.questions[QuestionFamily.NEIGHBOURS_DOWNSTREAM]
    sample = _crossing_first(candidates, 5)
    assert any((q.k or 0) > 0 for q in sample), "the sample must include a sheet crossing"
    for question in sample:
        # the first tagged node reached over send_to, looking through connector stubs
        query = (
            f"MATCH p = {_anchor('a', question.anchors[0])}"
            "-[:send_to|continues_as*1..7]->(b:CorpusNode) "
            "WHERE b.tag IS NOT NULL AND all(m IN nodes(p)[1..-1] WHERE m.tag IS NULL) "
            "RETURN DISTINCT b.tag AS tag"
        )
        assert sorted(str(row["tag"]) for row in _run(loaded, query)) == question.reference


def _flow_path_rows(loaded: Loaded, question: Question) -> list[dict[str, object]]:
    """Every send_to / continues_as path between the question's anchors, up to a length bound."""
    assert isinstance(question.reference, list)
    # a crossing adds two connector hops, so a route of h items is at most 3h relationships
    bound = 3 * (len(question.reference) - 1)
    source, target = question.anchors
    route = f"-[:send_to|continues_as*1..{bound}]->"
    query = (
        f"MATCH p = {_anchor('a', source)}{route}{_anchor('b', target)} "
        "RETURN [n IN nodes(p) | n.tag] AS tags, "
        "size([r IN relationships(p) WHERE type(r) = 'continues_as']) AS crossings"
    )
    return _run(loaded, query)


def test_flow_paths_match_the_reference_and_continues_as_equals_k(loaded: Loaded) -> None:
    candidates = loaded.questions[QuestionFamily.FLOW_PATH]
    sample = _crossing_first(candidates, 5)
    assert sample[0].k and sample[0].k >= 1, "the sample must include a sheet crossing"
    for question in sample:
        paths = []
        for row in _flow_path_rows(loaded, question):
            tags = [tag for tag in row["tags"] if tag is not None]  # type: ignore[attr-defined]
            paths.append((len(tags), tags, row["crossings"]))
        # the reference is the fewest-items path, ties broken by the smallest tag sequence
        _, best_tags, crossings = min(paths, key=lambda path: (path[0], path[1]))
        assert best_tags == question.reference
        # duplication is 0, so every crossing of the evidence is a connector pair (k == k_connector)
        assert question.k == question.k_connector
        assert crossings == question.k


def test_a_write_clause_is_rejected_and_nothing_is_written(loaded: Loaded) -> None:
    with pytest.raises(WriteClauseError):
        loaded.view.run_cypher("CREATE (:PytestQaT12Never)", timeout_s=5.0, row_cap=10)

    count = _run(loaded, "MATCH (n:PytestQaT12Never) RETURN count(n) AS n")
    assert count == [{"n": 0}]


def test_the_session_itself_is_read_only(loaded: Loaded) -> None:
    """Even a write that got past the text filter would be refused by the server."""
    with loaded.view._open_session() as session, pytest.raises(Exception, match="read access"):
        session.run("CREATE (:PytestQaT12Never)").consume()


def test_a_syntax_error_is_a_cypher_execution_error(loaded: Loaded) -> None:
    with pytest.raises(CypherExecutionError, match="Syntax"):
        loaded.view.run_cypher("MATCH (n RETURN n", timeout_s=5.0, row_cap=10)


def test_a_syntax_error_through_the_strategy_is_a_retrieval_error(
    loaded: Loaded, tmp_path: Path
) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="MATCH (n RETURN n"))
    client = ChatClient.for_openrouter(
        OpenRouterSettings.model_validate({"api_key": "sk-test"}),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=fake.as_httpx_client(),
    )

    def send(request: ChatRequest) -> ChatResponse:
        return client.complete(request, run_id="test")

    strategy = CypherRag(loaded.view, pin(), send, timeout_s=5.0, row_cap=10)
    retrieval = strategy.retrieve("What type of item is P-1-1?")

    assert retrieval.failure is Outcome.RETRIEVAL_ERROR
    assert "Syntax" in retrieval.trace["cypher_error"]
    assert len(fake.requests) == 1  # the query-writing call only


def test_rows_are_cut_at_the_cap_and_say_so(loaded: Loaded) -> None:
    result = loaded.view.run_cypher("UNWIND range(1, 10) AS i RETURN i", timeout_s=5.0, row_cap=3)
    assert [row["i"] for row in result.rows] == [1, 2, 3]
    assert result.truncated is True


def test_returned_nodes_hide_the_stores_bookkeeping(loaded: Loaded) -> None:
    question = _sample(loaded, QuestionFamily.LOOKUP_TYPE, 1)[0]
    rows = _run(loaded, f"MATCH {_anchor('n', question.anchors[0])} RETURN n")
    node = rows[0]["n"]
    assert isinstance(node, dict)
    assert "uid" not in node and "corpus_id" not in node
    assert "CorpusNode" not in node["labels"]
    assert node["tag"] == question.anchors[0]


def test_a_database_holding_two_drawing_sets_is_refused(loaded: Loaded) -> None:
    second_plan = load_plan_of(loaded.corpus, _SECOND_CORPUS_ID)
    load_corpus(loaded.settings, second_plan)
    with pytest.raises(StoreMismatch, match=_SECOND_CORPUS_ID):
        loaded.view.check_store()


class _MarkerSeesOnlyThisCorpus(Neo4jGraphView):
    """Hides other corpora from the marker query, so the count check runs in a shared database."""

    def _read(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        rows = super()._read(query, **parameters)
        if "DrawingSet" not in query:
            return rows
        return [row for row in rows if row["corpus_id"] == self.corpus_id()]


def test_the_count_check_passes_for_this_corpus_and_refuses_wrong_counts(loaded: Loaded) -> None:
    _MarkerSeesOnlyThisCorpus(loaded.settings, loaded.plan).check_store()

    wrong_plan = loaded.plan.model_copy(update={"expected_node_labels": {"Sheet": 1}})
    with pytest.raises(StoreMismatch, match="node label counts"):
        _MarkerSeesOnlyThisCorpus(loaded.settings, wrong_plan).check_store()


def test_a_database_holding_only_this_corpus_passes(loaded: Loaded) -> None:
    wipe_corpus(loaded.settings, _SECOND_CORPUS_ID)
    marker_rows = loaded.view.run_cypher(
        "MATCH (d:DrawingSet) RETURN d.corpus_id AS corpus_id", 5.0, 100
    ).rows
    others = [row["corpus_id"] for row in marker_rows if row["corpus_id"] != _CORPUS_ID]
    if others:
        pytest.skip(f"the database also holds {others}; this case needs a database of its own")

    loaded.view.check_store()


def test_the_schema_text_matches_what_the_store_holds(loaded: Loaded) -> None:
    text = loaded.view.schema_text()
    stored = {label for label in loaded.view.stored_label_counts() if label != "CorpusNode"}
    assert all(label in text for label in stored)
    assert json.dumps(text)  # plain text, serializable into a prompt
