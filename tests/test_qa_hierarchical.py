"""Hierarchical: the four mode combinations, budget order and the trace (H-T2; design §3.4-§3.6)."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from plantgraph.qa.strategies.hierarchical import Hierarchical
from qa_hierarchical_toy import chain_toy, strategy, tail_toy
from qa_routing_toy import ToyCorpus

_QUESTION = "Is TA upstream of TE?"
_ALL_FIVE = ["S1", "S2", "S3", "S4", "S5"]
_TRACE_KEYS = {
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


def _trace(hierarchical: Hierarchical, question: str = _QUESTION) -> dict[str, Any]:
    result = hierarchical.retrieve(question)
    assert result.failure is None and result.context is not None
    return result.trace


@pytest.mark.parametrize(
    ("route_mode", "budget_mode"),
    list(itertools.product(["sheet_graph", "flow_path"], ["drop_rings", "through_line"])),
)
def test_every_combination_sends_the_whole_route_and_reports_every_trace_key(
    route_mode: str, budget_mode: str
) -> None:
    trace = _trace(strategy(chain_toy(), route_mode=route_mode, budget_mode=budget_mode))

    assert _TRACE_KEYS <= trace.keys()
    assert trace["routed_sheets"] == _ALL_FIVE  # S9, the island, is not on the route
    assert trace["route_found"] is True and trace["route_fallback"] is None
    assert (trace["route_mode"], trace["budget_mode"]) == (route_mode, budget_mode)
    assert trace["anchors"] == ["TA", "TE"]
    assert trace["truncated"] is False and trace["over_budget"] is False
    assert trace["through_line_sheets"] == [] and trace["fallback_used"] is False


def test_the_context_text_is_what_context_chars_counts() -> None:
    result = strategy(chain_toy()).retrieve(_QUESTION)

    assert result.context is not None
    assert result.trace["context_chars"] == len(result.context)
    assert "S3:m3" in result.trace["serialized_keys"]


def test_a_single_tag_has_no_route_and_a_tag_on_an_island_has_none_found() -> None:
    one = _trace(strategy(chain_toy()), "What is TA?")
    island = _trace(strategy(chain_toy(), route_mode="sheet_graph"), "Is TA upstream of TZ?")

    assert one["route_found"] is None and one["routed_sheets"] == ["S1"]
    assert island["route_found"] is False
    assert island["routed_sheets"] == ["S1", "S9"]  # both anchor sheets; no route to add


def test_flow_mode_records_when_it_fell_back_to_the_sheet_route() -> None:
    toy = ToyCorpus()  # two branches that meet only upstream: no directed path TA -> TB
    toy.item("S1", "x", "TX")
    toy.item("S2", "a", "TA")
    toy.item("S3", "b", "TB")
    toy.cut("S1", "x", "S2", "a", "c1")
    toy.cut("S1", "x", "S3", "b", "c2")

    flow = _trace(strategy(toy, route_mode="flow_path"), "TA and TB")
    sheets = _trace(strategy(toy, route_mode="sheet_graph"), "TA and TB")

    assert flow["route_fallback"] == "sheet_graph" and flow["routed_sheets"] == ["S1", "S2", "S3"]
    assert sheets["route_fallback"] is None


def test_a_tag_with_a_space_and_an_imported_valve_name_are_anchors() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "SV 104.01")
    toy.item("S2", "b", "TK-9", piping_component_name="66KL21")
    toy.cut("S1", "a", "S2", "b", "c1")

    trace = _trace(strategy(toy), "Does SV 104.01 feed 66KL21?")

    assert trace["anchors"] == ["SV 104.01", "66KL21"]
    assert trace["routed_sheets"] == ["S1", "S2"]  # a corpus without unit_id routes by tag alone


def test_rings_are_dropped_outermost_first_and_the_anchor_sheet_stays() -> None:
    toy = tail_toy()
    lengths = [
        _trace(strategy(toy, sheet_hops=hops), "What is TA?")["context_chars"] for hops in (0, 1, 2)
    ]

    def cut_at(limit: int) -> dict[str, Any]:
        return _trace(strategy(toy, sheet_hops=2, max_context_chars=limit), "What is TA?")

    traces = [cut_at(lengths[2]), cut_at(lengths[2] - 1), cut_at(lengths[1] - 1), cut_at(1)]

    assert [t["routed_sheets"] for t in traces] == [
        ["S1", "S2", "S3"],
        ["S1", "S2"],
        ["S1"],
        ["S1"],
    ]
    assert [t["rings_dropped"] for t in traces] == [0, 1, 2, 2]
    assert [t["truncated"] for t in traces] == [False, True, True, True]
    assert [t["over_budget"] for t in traces] == [False, False, False, True]


def test_an_over_budget_core_is_sent_and_flagged() -> None:
    trace = _trace(strategy(chain_toy(), budget_mode="drop_rings", max_context_chars=1))

    # the context is still returned, so the shared fit check decides, not a silent cut here
    assert trace["over_budget"] is True
    assert trace["routed_sheets"] == _ALL_FIVE
    assert trace["truncated"] is False  # nothing may be cut from a route


def test_through_line_compresses_the_sheet_farthest_from_the_anchors_first() -> None:
    full = _trace(strategy(chain_toy(), budget_mode="through_line"))["context_chars"]

    one = _trace(strategy(chain_toy(), budget_mode="through_line", max_context_chars=full - 1))

    # S3 is two hops from both anchor sheets; S2 and S4 are one hop from one of them
    assert one["through_line_sheets"] == ["S3"]
    assert one["truncated"] is True and one["over_budget"] is False
    assert one["routed_sheets"] == _ALL_FIVE
    assert "S3:m3" in one["serialized_keys"] and "S3:jS3_0" not in one["serialized_keys"]


def test_through_line_keeps_the_path_stubs_and_is_deterministic() -> None:
    def thinnest() -> dict[str, Any]:
        return _trace(strategy(chain_toy(), budget_mode="through_line", max_context_chars=1))

    first = thinnest()

    assert first["through_line_sheets"] == ["S2", "S3", "S4"]
    assert {"S2:in_c1", "S2:m2", "S2:out_c2"} <= set(first["serialized_keys"])
    assert not any(key.startswith("S2:jS2") for key in first["serialized_keys"])
    assert {"S1:jS1_0", "S5:jS5_0"} <= set(first["serialized_keys"])  # anchor sheets stay whole
    assert first["over_budget"] is True  # even the thinnest plan exceeds a limit of one character
    assert thinnest() == first


def test_drop_rings_never_compresses_a_route_sheet() -> None:
    trace = _trace(strategy(chain_toy(), budget_mode="drop_rings", max_context_chars=1))

    assert trace["through_line_sheets"] == []
    assert "S3:jS3_0" in trace["serialized_keys"]


def _unit_toy() -> ToyCorpus:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA", unit_id="7")
    toy.item("S2", "b", "TB", unit_id="7")
    toy.item("S3", "c", "TC", unit_id="7")
    toy.item("S4", "d", "TD", unit_id="8")
    return toy


def test_a_unit_anchor_brings_its_sheets_and_unit_only_sheets_are_cut_highest_id_first() -> None:
    toy = _unit_toy()
    full = _trace(strategy(toy), "What is in unit 7?")

    cut = _trace(strategy(toy, max_context_chars=full["context_chars"] - 1), "What is in unit 7?")

    assert full["routed_sheets"] == ["S1", "S2", "S3"] and full["anchors"] == ["unit 7"]
    assert cut["routed_sheets"] == ["S1", "S2"] and cut["truncated"] is True


def test_a_tag_anchor_sheet_is_never_cut_with_its_unit() -> None:
    trace = _trace(strategy(_unit_toy(), max_context_chars=1), "Where is TC in unit 7?")

    assert trace["routed_sheets"] == ["S3"] and trace["over_budget"] is True
    assert trace["anchors"] == ["TC", "unit 7"]


def test_parameters_are_validated_with_what_was_expected() -> None:
    toy = chain_toy()

    with pytest.raises(ValueError, match="route_mode in .*flow_path.*found 'shortest'"):
        strategy(toy, route_mode="shortest")
    with pytest.raises(ValueError, match="budget_mode"):
        strategy(toy, budget_mode="squeeze")
    with pytest.raises(ValueError, match="max_context_chars > 0"):
        strategy(toy, max_context_chars=0)
