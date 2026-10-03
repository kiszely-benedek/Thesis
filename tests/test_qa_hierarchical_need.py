"""NeedAwareHierarchical: programs on the toy, budget order, fallbacks and the trace (QAR-T4)."""

from __future__ import annotations

from typing import Any

import pytest

from plantgraph.qa.models import RetrievalResult
from plantgraph.qa.need.classifiers import NeedDecision, NeedInput
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.strategies.hierarchical_need import NeedAwareHierarchical
from qa_hierarchical_toy import strategy as hierarchical_strategy
from qa_need_toy import ISOLATION_QUESTION, PATH_QUESTION, need_strategy, need_toy

_NEED_KEYS = {
    "need_label",
    "need_score",
    "need_scores",
    "need_classifier",
    "need_used",
    "need_fallback_reason",
    "need_program",
    "need_items",
    "need_items_dropped",
    "classifier_call",
}
#: The keys Hierarchical writes, which the harness's routing metrics and reports read.
_HIERARCHICAL_KEYS = {
    "routed_sheets",
    "through_line_sheets",
    "serialized_keys",
    "anchors",
    "route_mode",
    "budget_mode",
    "route_found",
    "route_fallback",
    "rings_dropped",
    "truncated",
    "over_budget",
    "fallback_used",
    "context_chars",
}


class _FixedClassifier:
    """Always answers the same label and score, so a test controls the decision."""

    def __init__(self, label: NeedLabel, score: float | None = None) -> None:
        self.name = "fixed"
        self._decision = NeedDecision(label=label, score=score, classifier="fixed")

    def classify(self, need_input: NeedInput) -> NeedDecision:
        return self._decision


def _rules(**kwargs: Any) -> NeedAwareHierarchical:
    return need_strategy(need_toy(), RuleNeedClassifier(), **kwargs)


def _retrieve(strategy: NeedAwareHierarchical, question: str) -> RetrievalResult:
    result = strategy.retrieve(question)
    assert result.failure is None and result.context is not None
    return result


def test_the_strategy_is_named_after_its_classifier() -> None:
    assert _rules().name == "hierarchical_need_rules"
    assert need_strategy(need_toy(), _FixedClassifier(NeedLabel.ITEM)).name == (
        "hierarchical_need_fixed"
    )


def test_isolation_sends_the_anchor_sheet_whole_and_only_the_items_back_to_the_first_valve() -> (
    None
):
    trace = _retrieve(_rules(), ISOLATION_QUESTION).trace
    keys = set(trace["serialized_keys"])

    assert trace["need_label"] == "UPSTREAM_TO_FIRST_VALVE" and trace["need_used"] is True
    assert trace["routed_sheets"] == ["S1", "S2", "S3"]
    assert trace["through_line_sheets"] == ["S1", "S2"]
    assert {"S3:t", "S3:jS30", "S3:jS31", "S3:jS32"} <= keys  # the core sheet is whole
    assert {"S2:m", "S1:v1"} <= keys  # P-2 and the valve XV-1 it was walked back to
    assert "S1:a" not in keys  # beyond the first operated valve
    assert not {k for k in keys if k.startswith(("S1:jS1", "S2:jS2"))}  # junk of other sheets


def test_the_stubs_of_a_walked_edge_stay_so_the_crossing_is_visible() -> None:
    trace = _retrieve(_rules(), ISOLATION_QUESTION).trace

    assert {"S1:out_c1", "S2:in_c1", "S2:out_c2", "S3:in_c2"} <= set(trace["serialized_keys"])


def test_the_trace_has_every_hierarchical_key_and_every_need_key() -> None:
    trace = _retrieve(_rules(), ISOLATION_QUESTION).trace

    assert (_HIERARCHICAL_KEYS | _NEED_KEYS) <= trace.keys()
    assert trace["anchors"] == ["P-3"] and trace["need_classifier"] == "rules"
    assert trace["need_score"] is None and trace["need_fallback_reason"] is None
    assert trace["need_program"] == [
        'traverse("P-3", upstream, flow, stop_at={label: OperatedValve})'
    ]
    assert trace["need_items"] == 2 and trace["need_items_dropped"] == 0
    assert trace["truncated"] is False and trace["over_budget"] is False
    assert trace["context_chars"] == len(_retrieve(_rules(), ISOLATION_QUESTION).context or "")


def test_a_path_question_sends_the_route_through_the_middle_sheet() -> None:
    trace = _retrieve(_rules(), PATH_QUESTION).trace
    keys = set(trace["serialized_keys"])

    assert trace["need_label"] == "PATH"
    assert trace["through_line_sheets"] == ["S2"]
    assert {"S2:m", "S2:in_c1", "S2:out_c2"} <= keys
    assert not {k for k in keys if k.startswith("S2:jS2")}


def test_item_sends_the_anchor_sheets_and_nothing_else() -> None:
    trace = _retrieve(_rules(), "What type of item is P-3?").trace

    assert trace["need_label"] == "ITEM" and trace["need_used"] is True
    assert trace["routed_sheets"] == ["S3"] and trace["through_line_sheets"] == []
    assert trace["need_items"] == 0


def test_the_unit_anchor_sheets_are_part_of_the_core() -> None:
    trace = _retrieve(_rules(), "How many centrifugal pumps are in unit 1?").trace

    assert trace["need_label"] == "UNIT_SCOPE"
    assert {"S1", "S2"} <= set(trace["routed_sheets"])  # unit 1 is drawn on S1 and S2


def test_the_farthest_items_are_dropped_first_and_the_core_never() -> None:
    def trace_at(limit: int) -> dict[str, Any]:
        return _retrieve(_rules(max_context_chars=limit), ISOLATION_QUESTION).trace

    full = trace_at(10**9)["context_chars"]
    without_valve = trace_at(full - 1)
    without_pump = trace_at(without_valve["context_chars"] - 1)
    core_only = trace_at(1)

    assert (
        "S1:v1" not in without_valve["serialized_keys"]
        and "S2:m" in without_valve["serialized_keys"]
    )
    assert without_valve["need_items_dropped"] == 1 and without_valve["truncated"] is True
    assert without_valve["over_budget"] is False
    assert "S2:m" not in without_pump["serialized_keys"] and without_pump["need_items_dropped"] == 2
    assert core_only["routed_sheets"] == ["S3"] and core_only["over_budget"] is True
    assert "S3:t" in core_only["serialized_keys"]


@pytest.mark.parametrize(
    ("question", "label", "reason"),
    [
        ("Tell me a story about P-3.", "GENERIC", "generic"),
        ("Trace the process flow path from P-1 to P-9.", "PATH", "precondition"),
        ("What type of item is Z-99?", "ITEM", "no_anchor"),
    ],
)
def test_each_fallback_reason_returns_the_hierarchical_context_byte_for_byte(
    question: str, label: str, reason: str
) -> None:
    toy = need_toy()
    baseline = hierarchical_strategy(toy, route_mode="flow_path", budget_mode="drop_rings")
    # no unit router: the no-anchor question fails retrieval in both, identically
    expected = baseline.retrieve(question)

    got = need_strategy(toy, RuleNeedClassifier()).retrieve(question)

    assert got.context == expected.context and got.failure == expected.failure
    assert got.trace["need_label"] == label and got.trace["need_fallback_reason"] == reason
    assert got.trace["need_used"] is False and got.trace["need_program"] == []
    assert got.trace.items() >= expected.trace.items()  # nothing of Hierarchical's trace is lost


def test_a_precondition_fallback_says_what_was_missing() -> None:
    trace = _retrieve(_rules(), "Trace the process flow path from P-1 to P-9.").trace

    assert "at least 2 tag anchor" in trace["need_fallback_detail"]


def test_a_score_below_tau_falls_back_and_one_at_tau_does_not() -> None:
    low = need_strategy(need_toy(), _FixedClassifier(NeedLabel.ITEM, 0.4), tau=0.5)
    at_tau = need_strategy(need_toy(), _FixedClassifier(NeedLabel.ITEM, 0.5), tau=0.5)

    assert _retrieve(low, "What is P-3?").trace["need_fallback_reason"] == "low_confidence"
    assert _retrieve(at_tau, "What is P-3?").trace["need_used"] is True


def test_a_program_that_finds_nothing_sends_the_anchor_sheets_alone() -> None:
    # P-3 has nothing downstream, so the program returns no item
    strategy = need_strategy(need_toy(), _FixedClassifier(NeedLabel.NEIGHBOURS_DOWNSTREAM))
    trace = _retrieve(strategy, "What follows P-3?").trace

    assert trace["need_used"] is True and trace["routed_sheets"] == ["S3"]
    assert trace["need_items"] == 0


def test_a_bad_tau_is_rejected() -> None:
    with pytest.raises(ValueError, match="tau in"):
        need_strategy(need_toy(), RuleNeedClassifier(), tau=1.5)
