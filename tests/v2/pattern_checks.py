"""Graph checks shared by the pattern tests: the invariants of design 12.2 a pattern controls.

Not a test module (no `test_` prefix). `assert_pattern_invariants` runs the DEXPI round trip and the
invariants S4, S7, S8, S9, S22 and S10's line-number part over everything the harness has written.
"""

from __future__ import annotations

from collections import deque

import networkx as nx
from instrument_harness import solenoids
from instrument_invariants import check_s4, check_s7, check_s8, check_s9, check_s22
from pattern_harness import PatternHarness
from trim_harness import assert_round_trip

from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation


def assert_pattern_invariants(h: PatternHarness) -> nx.DiGraph[str]:
    """Round trip, then S4, S7, S8, S9, S22 on the oracle graph; returns that graph."""
    graph = assert_round_trip(h)
    check_s4(graph)
    check_s7(graph, solenoids(h))
    check_s8(graph)
    check_s9(graph)
    check_s22(graph)
    return graph


def assert_line_numbers_unique_and_valid(lines: tuple[LineSpec, ...]) -> None:
    """S10, the part a pattern controls: every line number parses and none is used twice."""
    numbers = [number for line in lines for number in line.line_numbers]
    assert len(numbers) == len(set(numbers)), "a line number is used twice"
    for number in numbers:
        assert parse_line_number(number) is not None, number


def nodes_of_class(graph: nx.DiGraph[str], *node_classes: str) -> list[str]:
    """The node ids of the given classes, sorted."""
    return sorted(n for n, d in graph.nodes(data=True) if d["node_class"] in node_classes)


def nodes_with_letters(graph: nx.DiGraph[str], *letters: str) -> list[str]:
    """The node ids whose tag has exactly these ISA / code letters, sorted."""
    wanted = set(letters)
    return sorted(
        n
        for n, d in graph.nodes(data=True)
        if d.get("tag") and d["tag"].partition("-")[0] in wanted
    )


def located_on(graph: nx.DiGraph[str], node_id: str) -> list[str]:
    """The sensors located on `node_id` (its `measured_by` targets), sorted."""
    return sorted(
        t
        for _, t, d in graph.out_edges(node_id, data=True)
        if d["relation"] == Relation.MEASURED_BY.value
    )


def flow_graph(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """Only the `send_to` edges: the piping."""
    return nx.DiGraph(
        (s, t) for s, t, d in graph.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )


def reaches_a_safety_device(graph: nx.DiGraph[str], vessel: str) -> bool:
    """S6: walk the piping from `vessel`, never entering other equipment, to find a safety valve."""
    piping = flow_graph(graph)
    seen, queue = {vessel}, deque([vessel])
    while queue:
        for nxt in piping.successors(queue.popleft()):
            if graph.nodes[nxt]["node_class"].endswith("SafetyValve"):
                return True
            if nxt not in seen and graph.nodes[nxt]["node_class"] not in EQUIPMENT_CLASSES:
                seen.add(nxt)
                queue.append(nxt)
    return False
