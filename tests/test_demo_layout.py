"""Tests for the sheet layout (`demo/drawing`): toy sheets, invariants, an optional D100 sweep."""

from __future__ import annotations

import random
import time
from pathlib import Path

import networkx as nx
import pytest

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing import PlacedSymbol, SheetLayout, layout_sheet
from plantgraph.demo.drawing.geometry import (
    Box,
    count_foreign_crossings,
    count_overlaps,
    segment_hits_box,
    symbol_box,
)

PUMP = "CentrifugalPump"
TANK = "Tank"
VALVE = "GlobeValve"
IN_FLAG = "FlowInPipeOffPageConnector"
OUT_FLAG = "FlowOutPipeOffPageConnector"
IN_SIGNAL = "FlowInSignalOffPageConnector"
OUT_SIGNAL = "FlowOutSignalOffPageConnector"
TRANSMITTER = "ProcessSignalGeneratingFunction"
CONTROLLER = "ProcessInstrumentationFunction"
ACTUATOR = "ActuatingFunction"


def make_sheet(
    nodes: dict[str, str], edges: list[tuple[str, str, str]], sheet_id: str = "1"
) -> SheetGraph:
    """nodes: id -> node_class (the tag is the id); edges: (source, target, relation)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class in nodes.items():
        graph.add_node(node_id, node_class=node_class, tag=node_id, unit_id="U1")
    for source, target, relation in edges:
        graph.add_edge(source, target, relation=relation, line_number="L-1")
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def pipes(*pairs: tuple[str, str]) -> list[tuple[str, str, str]]:
    return [(a, b, "send_to") for a, b in pairs]


def by_id(layout: SheetLayout) -> dict[str, PlacedSymbol]:
    return {symbol.node_id: symbol for symbol in layout.symbols}


def assert_invariants(sheet: SheetGraph, layout: SheetLayout) -> None:
    """What must hold for every sheet: complete, overlap-free, lines join and avoid boxes."""
    assert {s.node_id for s in layout.symbols} == set(sheet.graph.nodes)
    assert count_overlaps(layout) == 0
    keys = [(line.source, line.target) for line in layout.lines]
    assert sorted(keys) == sorted(sheet.graph.edges)  # every edge routed exactly once
    boxes = {s.node_id: symbol_box(s) for s in layout.symbols}
    for line in layout.lines:
        assert _on_border(line.points[0], boxes[line.source]), line
        assert _on_border(line.points[-1], boxes[line.target]), line
    assert count_foreign_crossings(layout) == 0


def _on_border(point: tuple[float, float], box: Box) -> bool:
    x, y = point
    on_vertical = abs(x - box.left) < 1e-6 or abs(x - box.right) < 1e-6
    on_horizontal = abs(y - box.top) < 1e-6 or abs(y - box.bottom) < 1e-6
    within_x = box.left - 1e-6 <= x <= box.right + 1e-6
    within_y = box.top - 1e-6 <= y <= box.bottom + 1e-6
    return (on_vertical and within_y) or (on_horizontal and within_x)


def test_chain_runs_left_to_right() -> None:
    sheet = make_sheet({"a": PUMP, "b": VALVE, "c": TANK}, pipes(("a", "b"), ("b", "c")))
    layout = layout_sheet(sheet)
    symbols = by_id(layout)
    assert symbols["a"].x < symbols["b"].x < symbols["c"].x
    assert layout.units == ("U1",)
    assert layout.scale == 1.0
    assert_invariants(sheet, layout)


def test_same_input_gives_identical_layout() -> None:
    nodes = {"a": PUMP, "b": VALVE, "c": TANK, "d": TANK}
    edges = pipes(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"))
    first = layout_sheet(make_sheet(nodes, edges))
    second = layout_sheet(make_sheet(nodes, edges))
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_branch_puts_both_arms_in_one_column() -> None:
    nodes = {"a": PUMP, "b": VALVE, "c": VALVE, "d": TANK}
    sheet = make_sheet(nodes, pipes(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")))
    layout = layout_sheet(sheet)
    symbols = by_id(layout)
    assert symbols["b"].x == symbols["c"].x
    assert symbols["b"].y != symbols["c"].y
    assert_invariants(sheet, layout)


def test_long_edge_goes_around_the_boxes_in_between() -> None:
    nodes = {"a": PUMP, "b": VALVE, "c": VALVE, "d": TANK}
    sheet = make_sheet(nodes, pipes(("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")))
    layout = layout_sheet(sheet)
    long_line = next(line for line in layout.lines if (line.source, line.target) == ("a", "d"))
    assert len(long_line.points) > 2  # bends through the empty slots of the skipped columns
    assert_invariants(sheet, layout)


def test_cycle_has_exactly_one_back_edge_in_true_direction() -> None:
    nodes = {"a": PUMP, "b": VALVE, "c": TANK}
    sheet = make_sheet(nodes, pipes(("a", "b"), ("b", "c"), ("c", "a")))
    layout = layout_sheet(sheet)
    back = [line for line in layout.lines if line.is_back_edge]
    assert len(back) == 1
    symbols = by_id(layout)
    source_x = symbols[back[0].source].x
    target_x = symbols[back[0].target].x
    assert source_x > target_x  # a back edge runs right to left
    assert back[0].points[0][0] < symbols[back[0].source].x  # starts on the source's left side
    assert_invariants(sheet, layout)


def test_two_node_cycle_and_self_loop() -> None:
    two_cycle = make_sheet({"a": PUMP, "b": TANK}, pipes(("a", "b"), ("b", "a")))
    layout = layout_sheet(two_cycle)
    assert sum(line.is_back_edge for line in layout.lines) == 1
    assert_invariants(two_cycle, layout)
    with pytest.raises(ValueError, match="to itself"):
        layout_sheet(make_sheet({"a": PUMP}, pipes(("a", "a"))))


def test_pipe_flags_sit_on_the_left_and_right_edge() -> None:
    nodes = {"in": IN_FLAG, "p": PUMP, "v": VALVE, "out": OUT_FLAG, "t": TANK}
    edges = pipes(("in", "p"), ("p", "v"), ("v", "out"), ("p", "t"))
    sheet = make_sheet(nodes, edges)
    layout = layout_sheet(sheet)
    symbols = by_id(layout)
    others = [s for s in layout.symbols if s.family != "pipe_flag"]
    assert symbols["in"].x < min(s.x for s in others)
    assert symbols["out"].x > max(s.x for s in others)
    assert symbols["out"].x == max(s.x for s in layout.symbols)
    assert symbols["in"].x == min(s.x for s in layout.symbols)
    assert_invariants(sheet, layout)


def test_flag_labels_and_target_sheet() -> None:
    sheet = make_sheet({"in": IN_FLAG, "p": PUMP}, pipes(("in", "p")))
    sheet.graph.nodes["in"].update(
        referenced_drawing_number=7, line_number="L-9", fluid_code="WTR", connector_number=3
    )
    flag = by_id(layout_sheet(sheet))["in"]
    assert flag.target_sheet == "7"
    assert flag.labels == ("FROM DWG 7", "L-9", "WTR", "CONN 3")


def test_instrument_band_is_above_the_flow_drawing() -> None:
    nodes = {"p": PUMP, "v": VALVE, "tt": TRANSMITTER, "ic": CONTROLLER, "act": ACTUATOR}
    edges = pipes(("p", "v")) + [
        ("p", "tt", "measured_by"),
        ("tt", "ic", "send_signal_to"),
        ("ic", "act", "send_signal_to"),
        ("act", "v", "control"),
    ]
    sheet = make_sheet(nodes, edges)
    layout = layout_sheet(sheet)
    symbols = by_id(layout)
    flow_top = min(symbols[n].y - symbols[n].height / 2 for n in ("p", "v"))
    for name in ("tt", "ic", "act"):
        assert symbols[name].y + symbols[name].height / 2 < flow_top
    assert_invariants(sheet, layout)


def test_signal_flags_sit_in_the_band_at_its_ends() -> None:
    nodes = {
        "p": PUMP,
        "tt": TRANSMITTER,
        "ic": CONTROLLER,
        "sin": IN_SIGNAL,
        "sout": OUT_SIGNAL,
    }
    edges = [
        ("p", "tt", "measured_by"),
        ("sin", "ic", "send_signal_to"),
        ("tt", "ic", "send_signal_to"),
        ("ic", "sout", "send_signal_to"),
    ]
    sheet = make_sheet(nodes, edges)
    layout = layout_sheet(sheet)
    symbols = by_id(layout)
    pump_y = symbols["p"].y
    assert symbols["sin"].y < pump_y and symbols["sout"].y < pump_y
    others = [s for s in layout.symbols if s.node_id not in ("sin", "sout")]
    assert symbols["sin"].x <= min(s.x for s in others)
    assert symbols["sout"].x >= max(s.x for s in others)
    assert_invariants(sheet, layout)


def test_crowded_sheet_is_scaled_down_and_stays_valid() -> None:
    names = [f"n{i:02d}" for i in range(40)]
    nodes = {name: VALVE for name in names}
    sheet = make_sheet(nodes, pipes(*zip(names, names[1:], strict=False)))
    layout = layout_sheet(sheet)
    assert 0 < layout.scale < 1
    assert_invariants(sheet, layout)


def test_many_instruments_fill_several_band_rows() -> None:
    nodes = {"p": PUMP} | {f"i{k:02d}": TRANSMITTER for k in range(30)}
    edges = [("p", f"i{k:02d}", "measured_by") for k in range(30)]
    sheet = make_sheet(nodes, edges)
    layout = layout_sheet(sheet)
    assert_invariants(sheet, layout)


def test_empty_sheet_and_unknown_class() -> None:
    empty = layout_sheet(SheetGraph(sheet_id="0", graph=nx.DiGraph()))
    assert empty.symbols == () and empty.lines == ()
    with pytest.raises(ValueError, match="cannot draw node_class"):
        layout_sheet(make_sheet({"x": "Spaceship"}, []))


def test_segment_hits_box() -> None:
    box = Box(0, 0, 10, 10)
    assert segment_hits_box((-10, 0), (10, 0), box)
    assert not segment_hits_box((-10, 6), (10, 6), box)
    assert not segment_hits_box((6, -10), (6, 10), box)
    assert segment_hits_box((-10, -10), (10, 10), box)


@pytest.mark.parametrize("seed", range(25))
def test_random_sheets_keep_all_invariants(seed: int) -> None:
    sheet = _random_sheet(random.Random(seed))
    assert_invariants(sheet, layout_sheet(sheet))


def _random_sheet(rng: random.Random) -> SheetGraph:
    """Flow symbols with random edges (cycles included), plus instruments and flags."""
    flow = [f"f{i:02d}" for i in range(rng.randint(3, 25))]
    nodes = {name: rng.choice([PUMP, VALVE, TANK]) for name in flow}
    edges = [(a, b, "send_to") for a in flow for b in flow if a < b and rng.random() < 0.15]
    edges += [(b, a, "send_to") for a in flow for b in flow if a < b and rng.random() < 0.02]
    nodes["in1"], nodes["out1"] = IN_FLAG, OUT_FLAG
    edges += [("in1", rng.choice(flow), "send_to"), (rng.choice(flow), "out1", "send_to")]
    for index in range(rng.randint(0, 12)):
        name = f"i{index:02d}"
        nodes[name] = rng.choice([TRANSMITTER, CONTROLLER])
        edges.append((rng.choice(flow), name, "measured_by"))
    nodes["sin"], nodes["sout"] = IN_SIGNAL, OUT_SIGNAL
    return make_sheet(nodes, [e for e in edges if e[0] != e[1]])


D100_INGEST = Path(__file__).resolve().parent.parent / "data/runs/cv1/corpora/D100/ingest.json"


@pytest.mark.skipif(not D100_INGEST.exists(), reason="D100 ingest.json not on this machine")
def test_every_d100_sheet_lays_out_without_overlaps() -> None:
    from plantgraph.qa.corpus import load_corpus_artifacts

    sheets = load_corpus_artifacts("D100", D100_INGEST).localized_sheets
    start = time.perf_counter()
    layouts = [layout_sheet(sheet) for sheet in sheets]
    seconds = time.perf_counter() - start
    print(f"D100: {len(layouts)} sheets in {seconds:.2f} s")
    assert len(layouts) == 101
    for sheet, layout in zip(sheets, layouts, strict=True):
        assert count_overlaps(layout) == 0
        assert len(layout.lines) == sheet.graph.number_of_edges()
        assert count_foreign_crossings(layout) == 0
