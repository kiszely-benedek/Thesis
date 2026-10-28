"""`cypher_rag_lines`: prompt rules, the one repair round, the tag check and the hung guard.

Everything runs on fakes: a scripted model and a scripted database. No network, no Neo4j.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from corpus_v2 import corpus

from plantgraph.qa.cypher import CypherExecutionError, CypherResult, WriteClauseError
from plantgraph.qa.harness.cypher_setup import check_store_profile, required_cypher_profile
from plantgraph.qa.harness.registry import CypherDeps, build_strategy
from plantgraph.qa.models import Outcome
from plantgraph.qa.neo4j_view import StoreMismatch
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME, CypherRag
from plantgraph.qa.strategies.cypher_rag_lines import (
    CypherAttempt,
    CypherRagLines,
    classify_failure,
    render_query_prompt,
    render_repair_prompt,
)
from plantgraph.store.neo4j_plan import build_load_plan
from qa_agent_fakes import PIN, ScriptedModel
from qa_cypher_corpus import four_unit_corpus, load_plan_of
from qa_plant_api_toy import toy_graph

_ROOT = Path(__file__).resolve().parents[2]
_INPUTS = _ROOT / "data/runs/exp0007/inputs"
_QUERY = "MATCH (u:PlantItem)-[:line_to*1..]->(a:PlantItem {tag: 'P-1'}) RETURN DISTINCT u.tag"
_TIMEOUT = CypherExecutionError("Neo.ClientError.Transaction.TransactionTimedOut: x")
_MEMORY = CypherExecutionError("Neo.TransientError.General.MemoryPoolOutOfMemoryError: pool")
_SYNTAX = CypherExecutionError("Neo.ClientError.Statement.SyntaxError: Invalid input 'RETURN'")
_ROWS = CypherResult(rows=[{"tag": "V-1"}, {"tag": "V-2"}], truncated=False)
_LOOKUP_START = "MATCH (n:PlantItem) WHERE n.tag IN"
_NO_TAG_QUESTION = "Which valves are upstream of the pump?"
_TAG_QUESTION = "Which valves are upstream of P-1?"


class _Database:
    """Answers each query in turn from a script of results or errors.

    A question that names a tag first sends the tag lookup; tests give it its own `lookup`
    answer so the script holds only the model's queries.
    """

    def __init__(
        self,
        script: list[CypherResult | Exception],
        *,
        lookup: CypherResult | Exception | None = None,
    ) -> None:
        self._script = list(script)
        self._lookup = lookup
        self.queries: list[str] = []
        self.timeouts: list[float] = []

    def corpus_id(self) -> str:
        return "c"

    def schema_text(self) -> str:
        return "STUB-SCHEMA"

    def label_names(self) -> frozenset[str]:
        return frozenset({"PlantItem", "Valve"})

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.queries.append(query)
        self.timeouts.append(timeout_s)
        is_lookup = query.startswith(_LOOKUP_START) and self._lookup is not None
        outcome = self._lookup if is_lookup else self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert outcome is not None
        return outcome

    def close(self) -> None:
        pass


def _lines(db: Any, model: ScriptedModel, **kwargs: Any) -> CypherRagLines:
    return CypherRagLines(db, PIN, model, timeout_s=30, row_cap=1000, **kwargs)


# --- the prompt ----------------------------------------------------------------------------


def test_the_prompt_carries_the_query_shape_rules_and_the_schema_and_question() -> None:
    prompt = render_query_prompt(schema_text="SCHEMA-X", question_text="QUESTION-X")

    assert "SCHEMA-X" in prompt and "QUESTION-X" in prompt and "<<" not in prompt
    assert "Never bind a variable-length path to a variable" in prompt
    assert "RETURN DISTINCT u.tag" in prompt
    assert "use shortestPath()" in prompt
    assert "Do not use the SHORTEST keyword (SHORTEST 1" in prompt
    assert "follow line_to, not send_to" in prompt
    assert "no *..5" in prompt  # hop caps are refused: they drop correct long answers


def test_the_f1_cypher_class_and_template_are_untouched_by_the_v2t_rules() -> None:
    f1 = CypherRag(_Database([]), PIN, ScriptedModel([]), timeout_s=1, row_cap=1)
    template = (_ROOT / "src/plantgraph/qa/prompts/cypher_query.txt").read_text("utf-8")

    assert (f1.name, f1.profile) == ("cypher_rag", "occurrence")
    assert "shortestPath" not in template and "line_to" not in template


def test_the_repair_prompt_holds_the_prompt_the_query_a_cut_error_and_the_class_hint() -> None:
    failed = CypherAttempt(query="BAD Q", call=None, error="E" * 500, failure="timeout")

    text = render_repair_prompt("FIRST PROMPT", failed, timeout_s=30)

    assert text.startswith("FIRST PROMPT") and "BAD Q" in text
    assert "E" * 400 in text and "E" * 401 not in text
    assert "did not finish in 30 s" in text and "shortestPath" in text


def test_a_failure_that_is_not_repairable_has_no_repair_prompt() -> None:
    hung = CypherAttempt(query="Q", call=None, error="hung", failure="hung")

    with pytest.raises(ValueError, match="expected a repairable failure"):
        render_repair_prompt("P", hung, timeout_s=30)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_TIMEOUT, "timeout"),
        (_MEMORY, "memory"),
        (_SYNTAX, "syntax"),
        (WriteClauseError("w"), "write"),
    ],
)
def test_failures_are_classified_from_the_database_message(error: Exception, kind: str) -> None:
    assert classify_failure(error) == kind


# --- retrieve: success ---------------------------------------------------------------------


def test_a_good_query_runs_once_and_its_rows_are_the_context() -> None:
    db, model = _Database([_ROWS]), ScriptedModel([_QUERY])

    result = _lines(db, model).retrieve(_NO_TAG_QUESTION)

    assert result.failure is None and result.context is not None
    assert _QUERY in result.context and '"tag": "V-1"' in result.context
    assert len(model.requests) == 1 and result.trace["repaired"] is False
    assert result.trace["n_rows"] == 2 and result.trace["cypher"] == _QUERY
    assert db.timeouts == [30]  # no tag in the question: no lookup query


def test_the_tag_note_is_prepended_and_the_lookup_makes_no_model_call() -> None:
    lookup = CypherResult(rows=[{"tag": "P-1", "name": None}], truncated=False)
    db, model = _Database([_ROWS], lookup=lookup), ScriptedModel([_QUERY])

    result = _lines(db, model).retrieve("Is P-1 or X-9 upstream of V-1?")

    assert result.context is not None and result.context.startswith("Tags named in the question")
    assert "- found: P-1" in result.context and "- not found: X-9, V-1" in result.context
    assert result.trace["tags_missing"] == ["X-9", "V-1"]
    assert len(model.requests) == 1


def test_a_failed_tag_lookup_is_recorded_and_does_not_fail_the_question() -> None:
    db = _Database([_ROWS], lookup=_SYNTAX)

    result = _lines(db, ScriptedModel([_QUERY])).retrieve(_TAG_QUESTION)

    assert result.failure is None and "tag_check_error" in result.trace
    assert result.context is not None and not result.context.startswith("Tags named")


# --- retrieve: the repair round ------------------------------------------------------------


@pytest.mark.parametrize("error", [_SYNTAX, _TIMEOUT, _MEMORY, WriteClauseError("found DELETE")])
def test_a_repairable_failure_is_sent_back_once_and_the_repaired_query_is_used(
    error: Exception,
) -> None:
    db = _Database([error, _ROWS])
    model = ScriptedModel(["BROKEN", _QUERY])

    result = _lines(db, model).retrieve(_NO_TAG_QUESTION)

    assert result.failure is None and result.trace["repaired"] is True
    assert len(model.requests) == 2
    second = model.requests[1].messages[0].content
    assert "BROKEN" in second and str(error)[:50] in second
    assert [a["failure"] for a in result.trace["attempts"]] == [classify_failure(error), None]
    assert result.trace["cypher"] == _QUERY  # the last query is the one shown


def test_the_repair_is_paid_for_in_the_trace_total() -> None:
    db, model = _Database([_SYNTAX, _ROWS]), ScriptedModel(["B", _QUERY])

    result = _lines(db, model).retrieve(_NO_TAG_QUESTION)

    assert result.trace["cypher_call"]["cost_usd"] == pytest.approx(0.02)
    assert result.trace["cypher_call"]["prompt_tokens"] == 20


def test_there_is_only_one_repair_round() -> None:
    db = _Database([_SYNTAX, _TIMEOUT])
    model = ScriptedModel(["B1", "B2", "NEVER"])

    result = _lines(db, model).retrieve(_NO_TAG_QUESTION)

    assert result.failure is Outcome.RETRIEVAL_ERROR and len(model.requests) == 2
    assert "TransactionTimedOut" in result.trace["cypher_error"]
    assert len(result.trace["attempts"]) == 2  # both attempts stay in the trace


def test_an_empty_reply_and_an_overflow_are_not_repaired() -> None:
    empty = _lines(_Database([]), ScriptedModel([""])).retrieve(_NO_TAG_QUESTION)
    overflow = _lines(_Database([]), ScriptedModel([], overflow_at=0)).retrieve(_NO_TAG_QUESTION)

    assert empty.failure is Outcome.RETRIEVAL_ERROR
    assert "held no query" in empty.trace["cypher_error"]
    assert overflow.failure is Outcome.RETRIEVAL_ERROR
    assert "overflowed" in overflow.trace["cypher_error"]
    assert empty.trace["repaired"] is False and overflow.trace["repaired"] is False


# --- retrieve: the hard guard --------------------------------------------------------------


class _DeadServer(_Database):
    """Never answers the question's query until closed (the 8.6 h hang seen in QT-0)."""

    def __init__(self) -> None:
        super().__init__([])
        self.release = threading.Event()
        self.closed = False

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.queries.append(query)
        self.release.wait()
        raise CypherExecutionError("connection closed")

    def close(self) -> None:
        self.closed = True
        self.release.set()


def test_a_hung_server_gives_a_retrieval_error_and_is_not_repaired() -> None:
    db, model = _DeadServer(), ScriptedModel([_QUERY, "NEVER"])

    result = _lines(db, model, hang_grace_s=0.2).retrieve(_NO_TAG_QUESTION)

    assert result.failure is Outcome.RETRIEVAL_ERROR
    assert result.trace["cypher_error"].startswith("hung: server ignored the timeout")
    assert db.closed and len(model.requests) == 1 and len(db.queries) == 1
    assert result.trace["attempts"][0]["failure"] == "hung"


# --- wiring: profile, registry, params -----------------------------------------------------


def test_the_lines_arm_reads_the_plant_lines_store_and_the_checks_accept_it() -> None:
    assert PROFILE_OF_NAME["cypher_rag_lines"] == "plant_lines"
    assert required_cypher_profile(["context_rag", "cypher_rag_lines"]) == "plant_lines"
    built = corpus()
    plan = build_load_plan("c", built.localized_sheets, built.resolution, profile="plant_lines")
    check_store_profile(plan, "plant_lines")
    for other in ("occurrence", "plant"):
        stored = load_plan_of(four_unit_corpus(), "p", profile=other)  # type: ignore[arg-type]
        with pytest.raises(StoreMismatch, match="--store-profile plant_lines"):
            check_store_profile(stored, "plant_lines")


def test_one_cypher_arm_per_run_still_holds_with_the_lines_arm() -> None:
    with pytest.raises(ValueError, match="one Cypher arm per run"):
        required_cypher_profile(["cypher_rag_plant", "cypher_rag_lines"])


def test_the_plain_cypher_class_refuses_the_lines_profile() -> None:
    with pytest.raises(ValueError, match="use CypherRagLines"):
        CypherRag(
            _Database([]), PIN, ScriptedModel([]), timeout_s=1, row_cap=1, profile="plant_lines"
        )


def _params(setting: str) -> dict[str, Any]:
    path = _INPUTS / f"params_cypher_v2t_{setting}.json"
    params: dict[str, Any] = json.loads(path.read_text("utf-8"))["cypher_rag_lines"]
    return params


def test_the_registry_builds_the_lines_strategy_from_either_params_file() -> None:
    deps = CypherDeps(_Database([]), PIN, ScriptedModel([]))

    for setting, timeout in (("a", 30.0), ("b", 120.0)):
        strategy = build_strategy("cypher_rag_lines", _params(setting), toy_graph(), cypher=deps)
        assert isinstance(strategy, CypherRagLines) and strategy.name == "cypher_rag_lines"
        assert (strategy._timeout_s, strategy._row_cap) == (timeout, 1000)


def test_the_two_settings_differ_only_in_the_query_timeout() -> None:
    a, b = _params("a"), _params("b")

    assert (a["timeout_s"], b["timeout_s"]) == (30, 120)
    assert {k: v for k, v in a.items() if k != "timeout_s"} == {
        k: v for k, v in b.items() if k != "timeout_s"
    }


def test_the_query_runs_under_the_configured_timeout() -> None:
    db = _Database([_ROWS])
    lines = CypherRagLines(db, PIN, ScriptedModel([_QUERY]), timeout_s=120, row_cap=1000)

    lines.retrieve(_NO_TAG_QUESTION)

    assert db.timeouts == [120]
