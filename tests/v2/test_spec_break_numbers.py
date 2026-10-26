"""Rule L20 / invariant S10: the line number changes at every spec change (a `PropertyBreak`).

A `LineSpec` with a break carries a second line number for the stretch after it, and `runs()`
cuts it into two stretches that both backends build the same way.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_everything import build_instrumented_plant
from pydantic import ValidationError
from trim_everything import ALL_ON
from trim_harness import STYLE, TrimHarness, assert_round_trip, send_to_path

from plantgraph.benchmark.v2 import trims_extra
from plantgraph.benchmark.v2.config import TrimConvention
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec
from plantgraph.benchmark.v2.tags import format_line_number, parse_line_number
from plantgraph.benchmark.v2.trim_plan import main_line
from plantgraph.graph.schema import Relation

_BREAK = "PropertyBreak"


def _line_number(sequence: int, spec: str = "A1A") -> str:
    return format_line_number(4, "P", 1, sequence, spec, "N")


def _item(node_id: str, node_class: str = "GateValve") -> LineItemSpec:
    return LineItemSpec(node_id=node_id, node_class=node_class)


def _line(*items: LineItemSpec, after: str | None = None, dst: str | None = "b") -> LineSpec:
    return LineSpec(
        line_number=_line_number(1),
        fluid_code="P",
        unit_no=1,
        src_id="a",
        dst_id=dst,
        items=items,
        line_number_after_break=after,
    )


def check_s10(graph: nx.DiGraph[str]) -> int:
    """S10: every line number parses; it changes (number and spec) at every `PropertyBreak`.

    Returns the number of breaks checked.
    """
    numbers = {
        d["line_number"]
        for _, _, d in graph.edges(data=True)
        if d["relation"] == Relation.SEND_TO.value
    }
    assert all(parse_line_number(number) is not None for number in numbers), sorted(numbers)
    breaks = [n for n, d in graph.nodes(data=True) if d["node_class"] == _BREAK]
    for node in breaks:
        (before,) = {graph.edges[p, node]["line_number"] for p in graph.predecessors(node)}
        (after,) = {graph.edges[node, s]["line_number"] for s in graph.successors(node)}
        assert before != after, f"{node}: the line number stays {before} across the break"
        assert parse_line_number(before).spec != parse_line_number(after).spec, node  # type: ignore[union-attr]
    return len(breaks)


def test_a_break_run_has_two_numbers_and_the_second_spec_differs() -> None:
    h = TrimHarness()
    src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    plan = trims_extra.spec_break(h.ctx, STYLE)
    line = main_line(h.ctx, STYLE, src, plan.run, dst)
    assert line.line_number_after_break is not None
    before, after = (parse_line_number(number) for number in line.line_numbers)
    assert before is not None and after is not None
    assert before.spec != after.spec
    assert (before.size, before.service) == (after.size, after.service)


def test_a_line_without_a_break_keeps_one_number() -> None:
    h = TrimHarness()
    line = main_line(h.ctx, STYLE, None, (_item("v"),), "x")
    assert line.line_number_after_break is None and len(line.line_numbers) == 1


def test_s10_the_edges_after_the_break_carry_the_new_number_in_both_backends() -> None:
    """The oracle and the DEXPI builder agree; the break ends the first stretch."""
    h = TrimHarness()
    src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    plan = h.write(trims_extra.spec_break(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    (spec_break,) = [n for n, d in graph.nodes(data=True) if d["node_class"] == _BREAK]
    assert send_to_path(graph, src, dst) == [src, spec_break, dst]
    before, after = plan.lines[0].line_numbers
    assert graph.edges[src, spec_break]["line_number"] == before
    assert graph.edges[spec_break, dst]["line_number"] == after
    assert check_s10(graph) == 1
    model = h.dexpi.build().conceptualModel
    systems = [system.lineNumber for system in model.pipingNetworkSystems]
    assert len(systems) == len(set(systems)) and {before, after} <= set(systems)


def test_a_break_between_two_valves_splits_the_line_in_the_middle() -> None:
    h = TrimHarness()
    src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    run = (
        _item("v1"),
        _item("br", _BREAK),
        _item("v2"),
    )
    line = main_line(h.ctx, STYLE, src, run, dst)
    first, second = line.runs()
    assert [p.node_id for p in first.items] == ["v1", "br"] and first.dst_id is None
    assert second.src_id == "br" and [p.node_id for p in second.items] == ["v2"]
    assert second.dst_id == dst


def test_s10_holds_over_a_whole_plant_with_a_break() -> None:
    h = TrimHarness(seed=5, config=TrimConvention(**ALL_ON))  # type: ignore[arg-type]
    build_instrumented_plant(h)
    graph = assert_round_trip(h)
    assert check_s10(graph) >= 1


def test_a_number_after_the_break_needs_exactly_one_break_item() -> None:
    with pytest.raises(ValidationError, match="needs exactly one PropertyBreak"):
        _line(_item("v"), after=_line_number(2))
    with pytest.raises(ValidationError, match="needs exactly one PropertyBreak"):
        _line(_item("b1", _BREAK), _item("b2", _BREAK), after=_line_number(2))


def test_the_number_after_the_break_must_differ_and_something_must_follow_the_break() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        _line(_item("br", _BREAK), after=_line_number(1))
    with pytest.raises(ValidationError, match="must be followed"):
        _line(_item("br", _BREAK), after=_line_number(2), dst=None)
