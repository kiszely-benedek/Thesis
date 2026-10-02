"""Relaxed routing hit, evidence-node recall and the summary's rates (H-T3), on hand-built toys."""

from __future__ import annotations

from typing import Any

import networkx as nx
import pytest

from plantgraph.graph.schema import Relation
from plantgraph.qa.harness.gold import ROUTING_HIT_TRACE_KEY
from plantgraph.qa.harness.routing_gold import (
    EVIDENCE_NODE_RECALL_TRACE_KEY,
    RELAXED_ROUTING_HIT_TRACE_KEY,
    RoutingGold,
    add_routing_metrics,
    evidence_node_recall,
    relaxed_routing_hit,
)
from plantgraph.qa.harness.summary import summarize_rows
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionFamily, QuestionResult
from plantgraph.resolution.localize import OccurrenceMap


def _gold() -> RoutingGold:
    """A -> B -> D and A -> C -> D; A and D on S1, B on S2, C on S3, and B also on S4."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id in "ABCD":
        plant.add_node(node_id, tag=f"t{node_id}")
    for source, target in ("AB", "BD", "AC", "CD"):
        plant.add_edge(source, target, relation=Relation.SEND_TO.value)
    sheets_of = {
        "A": frozenset({"S1"}),
        "B": frozenset({"S2", "S4"}),
        "C": frozenset({"S3"}),
        "D": frozenset({"S1"}),
    }
    local_to_original = {
        "S1:a": "S1:A",
        "S2:b": "S2:B",
        "S4:b2": "S4:B",  # B's reference occurrence
        "S3:c": "S3:C",
        "S1:d": "S1:D",
        "S1:stub": "S1:opc:S1:0",  # a connector stub: not in the plant
    }
    return RoutingGold(
        plant=plant,
        sheets_of=sheets_of,
        occurrence_map=OccurrenceMap(local_to_original=local_to_original),
        node_ids_of_tag={f"t{node_id}": [node_id] for node_id in "ABCD"},
    )


def _question(
    family: QuestionFamily = QuestionFamily.FLOW_PATH,
    evidence_sheets: list[str] | None = None,
    evidence_tags: list[str] | None = None,
) -> Question:
    return Question(
        question_id="q",
        corpus_id="c",
        family=family,
        template_id="t",
        template_version="1",
        text="?",
        answer_type=AnswerType.TAG_PATH,
        answerable=True,
        reference=["tA", "tB", "tD"],
        evidence_tags=["tA", "tB", "tD"] if evidence_tags is None else evidence_tags,
        evidence_sheets=["S1", "S2", "S4"] if evidence_sheets is None else evidence_sheets,
        anchors=["tA", "tD"],
        generator_seed=0,
    )


def _trace(**retrieval: Any) -> dict[str, Any]:
    return {"retrieval": retrieval}


def test_relaxed_hit_accepts_an_alternative_valid_path() -> None:
    # gold goes through B (S2, S4); the routed sheets cover the A -> C -> D path instead
    trace = _trace(routed_sheets=["S1", "S3"])
    assert add_and_read(trace)[ROUTING_HIT_TRACE_KEY] is False  # strict, unchanged
    assert relaxed_routing_hit(_question(), trace, _gold()) is True


def test_relaxed_hit_counts_a_node_drawn_on_any_routed_sheet() -> None:
    # B is routed only through its reference sheet S4
    assert relaxed_routing_hit(_question(), _trace(routed_sheets=["S1", "S4"]), _gold()) is True


def test_relaxed_hit_is_false_when_every_path_is_broken() -> None:
    # B and C both missing: A cannot reach D inside the routed sheets
    assert relaxed_routing_hit(_question(), _trace(routed_sheets=["S1"]), _gold()) is False


def test_relaxed_hit_equals_strict_for_other_families() -> None:
    question = _question(QuestionFamily.LOOKUP_TYPE, evidence_sheets=["S1", "S3"])
    assert relaxed_routing_hit(question, _trace(routed_sheets=["S1", "S3"]), _gold()) is True
    assert relaxed_routing_hit(question, _trace(routed_sheets=["S1"]), _gold()) is False


def test_relaxed_hit_rejects_an_unknown_tag() -> None:
    question = _question().model_copy(update={"anchors": ["tA", "nope"]})
    with pytest.raises(ValueError, match="nope"):
        relaxed_routing_hit(question, _trace(routed_sheets=["S1"]), _gold())


def test_evidence_node_recall_counts_an_item_through_any_occurrence() -> None:
    # tB is serialized through its reference occurrence S4:b2; the stub is ignored
    trace = _trace(serialized_keys=["S1:a", "S4:b2", "S1:stub"])
    assert evidence_node_recall(_question(), trace, _gold()) == pytest.approx(2 / 3)
    full = _trace(serialized_keys=["S1:a", "S4:b2", "S1:d"])
    assert evidence_node_recall(_question(), full, _gold()) == 1.0


def test_evidence_node_recall_is_none_without_keys_or_evidence() -> None:
    assert evidence_node_recall(_question(), _trace(), _gold()) is None
    no_evidence = _question(evidence_tags=[])
    assert evidence_node_recall(no_evidence, _trace(serialized_keys=["S1:a"]), _gold()) is None


def add_and_read(trace: dict[str, Any]) -> dict[str, Any]:
    """Run `add_routing_metrics` on a copy of `trace` and return the copy."""
    result = dict(trace)
    add_routing_metrics(result, _question(), _gold())
    return result


def test_add_routing_metrics_writes_the_three_keys_and_keeps_strict() -> None:
    trace = add_and_read(_trace(routed_sheets=["S1", "S2", "S4"], serialized_keys=["S1:a"]))
    assert trace[ROUTING_HIT_TRACE_KEY] is True
    assert trace[RELAXED_ROUTING_HIT_TRACE_KEY] is True
    assert trace[EVIDENCE_NODE_RECALL_TRACE_KEY] == pytest.approx(1 / 3)


def test_add_routing_metrics_writes_nothing_for_a_strategy_that_does_not_route() -> None:
    assert add_and_read(_trace()) == _trace()


def _row(question_id: str, strategy: str, trace: dict[str, Any]) -> QuestionResult:
    return QuestionResult(
        run_id="r",
        question_id=question_id,
        strategy=strategy,
        repeat=0,
        outcome=Outcome.ANSWERED,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=0.0,
        context_chars=0,
        trace=trace,
    )


def test_summary_reports_rates_per_strategy_and_per_k_bin() -> None:
    questions = [
        _question().model_copy(update={"question_id": "q1", "k": 0}),
        _question().model_copy(update={"question_id": "q2", "k": 3}),
    ]
    rows = [
        _row(
            "q1",
            "h",
            {
                ROUTING_HIT_TRACE_KEY: False,
                RELAXED_ROUTING_HIT_TRACE_KEY: True,
                EVIDENCE_NODE_RECALL_TRACE_KEY: 0.5,
                "retrieval": {
                    "over_budget": False,
                    "truncated": True,
                    "route_fallback": None,
                    "fallback_used": False,
                },
            },
        ),
        _row(
            "q2",
            "h",
            {
                ROUTING_HIT_TRACE_KEY: False,
                RELAXED_ROUTING_HIT_TRACE_KEY: False,
                EVIDENCE_NODE_RECALL_TRACE_KEY: 1.0,
                "retrieval": {
                    "over_budget": True,
                    "truncated": True,
                    "route_fallback": "sheet_graph",
                    "fallback_used": False,
                },
            },
        ),
        _row("q1", "plain", {"retrieval": {}}),  # a strategy with no routing, no rates
    ]

    summary = summarize_rows("r", rows, questions, n_new_rows=3)

    assert summary.routing_recall == {"h": 0.0}
    assert summary.relaxed_routing_recall == {"h": 0.5}
    assert summary.evidence_node_recall == {"h": 0.75}
    assert summary.routing_metrics_by_k_bin["relaxed_routing_recall"] == {
        "h": {"0": 1.0, "3-4": 0.0}
    }
    assert summary.trace_rates == {
        "h": {
            "over_budget_rate": 0.5,
            "truncated_rate": 1.0,
            "route_fallback_rate": 0.5,
            "router_fallback_rate": 0.0,
        }
    }
