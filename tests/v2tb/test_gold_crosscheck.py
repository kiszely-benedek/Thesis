"""The scope X gold cross-check: its graph fold, its walk, its naming, and a live agreement run.

The last tests run the cross-check on a small generated plant and then *damage* one side (a stored
reference, a position in the view) to prove the check can fail.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

import pytest

from plantgraph.graph.schema import EQUIPMENT_CLASSES, OPERATED_VALVE_CLASSES
from plantgraph.qa.exp0009.gold_crosscheck import CrossChecker, PlantCheck, tally
from plantgraph.qa.exp0009.gold_crosscheck_graph import (
    FlowGraph,
    build_flow_graph,
    fold_class,
    fold_line,
    fold_tag,
)
from plantgraph.qa.exp0009.gold_crosscheck_plants import dev_plant_check
from plantgraph.qa.exp0009.gold_crosscheck_walks import (
    EQUIPMENT_CLASSES as MY_EQUIPMENT,
)
from plantgraph.qa.exp0009.gold_crosscheck_walks import (
    OPERATED_CLASSES,
    Namer,
    isolation_valves,
    tagged_ends,
)
from plantgraph.qa.graph_view import EdgeRecord, ItemRecord

# ---- hand-built graphs --------------------------------------------------------------------------


def _graph(
    nodes: Mapping[str, tuple[str, str | None]],
    edges: Sequence[tuple[str, str, str]],
    positions: dict[str, str] | None = None,
) -> FlowGraph:
    """nodes: key -> (class, printed tag or None); edges: (source, target, line number)."""
    successors: defaultdict[str, set[str]] = defaultdict(set)
    predecessors: defaultdict[str, set[str]] = defaultdict(set)
    lines: defaultdict[str, set[str]] = defaultdict(set)
    for source, target, line in edges:
        successors[source].add(target)
        predecessors[target].add(source)
        lines[source].add(fold_line(line))
        lines[target].add(fold_line(line))
    return FlowGraph(
        successors={k: frozenset(v) for k, v in successors.items()},
        predecessors={k: frozenset(v) for k, v in predecessors.items()},
        tags={k: fold_tag(tag) for k, (_, tag) in nodes.items() if tag},
        classes={k: cls for k, (cls, _) in nodes.items()},
        lines={k: frozenset(v) for k, v in lines.items()},
        positions=positions or {},
        occurrences={k: (k,) for k in nodes},
    )


# source --a--> GateValve v1 --> CheckValve --> GateValve v2 --> Tank T
_CHAIN_NODES = {
    "src": ("Tank", "T-1"),
    "v1": ("GateValve", None),
    "chk": ("CheckValve", None),
    "v2": ("GlobeValve", "HV-2"),
    "tank": ("Tank", "T-2"),
}
_CHAIN_EDGES = [("src", "v1", "L1"), ("v1", "chk", "L1"), ("chk", "v2", "L1"), ("v2", "tank", "L1")]


def test_the_walk_stops_at_the_first_operated_valve() -> None:
    graph = _graph(_CHAIN_NODES, _CHAIN_EDGES)
    assert isolation_valves(graph, "tank", upstream=True) == frozenset({"v2"})


def test_the_walk_passes_through_a_check_valve() -> None:
    graph = _graph(_CHAIN_NODES, _CHAIN_EDGES)
    assert isolation_valves(graph, "chk", upstream=True) == frozenset({"v1"})


def test_a_route_that_ends_at_a_source_makes_the_item_no_candidate() -> None:
    graph = _graph(_CHAIN_NODES, _CHAIN_EDGES)
    assert isolation_valves(graph, "src", upstream=True) is None
    assert isolation_valves(graph, "tank", upstream=False) is None


def test_every_branch_contributes_its_first_valve() -> None:
    nodes = {
        "a": ("Tank", "A"),
        "b": ("Tank", "B"),
        "tee": ("PipeTee", None),
        "va": ("BallValve", None),
        "vb": ("GateValve", None),
        "sink": ("Tank", "S"),
    }
    edges = [("a", "va", "L"), ("b", "vb", "L"), ("va", "tee", "L"), ("vb", "tee", "L"),
             ("tee", "sink", "L")]  # fmt: skip
    assert isolation_valves(_graph(nodes, edges), "sink", upstream=True) == frozenset({"va", "vb"})


def test_a_loop_does_not_make_the_walk_run_forever() -> None:
    nodes = {
        "x": ("Tank", "X"),
        "t1": ("PipeTee", None),
        "t2": ("PipeTee", None),
        "v": ("GateValve", None),
    }
    edges = [("t1", "t2", "L"), ("t2", "t1", "L"), ("v", "t1", "L"), ("t2", "x", "L")]
    graph = _graph(nodes, edges)
    assert isolation_valves(graph, "x", upstream=True) == frozenset({"v"})
    # the same loop fed by a plain pipe (no valve) is a route with nothing to close
    nodes["v"] = ("PipeTee", None)
    assert isolation_valves(_graph(nodes, edges), "x", upstream=True) is None


def test_nearest_tagged_stops_at_tags_and_ignores_line_numbers() -> None:
    nodes = {"p": ("CentrifugalPump", "P-1"), "v": ("GateValve", None),
             "t": ("PipeTee", None), "x": ("Tank", "T-9")}  # fmt: skip
    edges = [("p", "v", "L1"), ("v", "t", "L1"), ("t", "x", "OTHER")]
    graph = _graph(nodes, edges)
    assert tagged_ends(graph, "v", forward=True) == {"x"}
    assert tagged_ends(graph, "v", forward=False) == {"p"}


def test_two_valves_of_one_class_beside_one_tag_have_no_unique_descriptor() -> None:
    nodes = {"p": ("Pump", "P-1"), "v1": ("GateValve", None), "v2": ("GateValve", None),
             "x": ("Tank", "T-1")}  # fmt: skip
    edges = [("p", "v1", "L"), ("v1", "v2", "L"), ("v2", "x", "L")]
    namer = Namer(_graph(nodes, edges))
    assert not namer.is_nameable("v1")  # both gate valves sit upstream of T-1 on line L
    assert not namer.is_nameable("v2")


def test_a_different_class_or_line_separates_two_valves() -> None:
    nodes = {"p": ("Pump", "P-1"), "v1": ("GateValve", None), "v2": ("BallValve", None),
             "x": ("Tank", "T-1")}  # fmt: skip
    edges = [("p", "v1", "L"), ("v1", "v2", "L"), ("v2", "x", "L")]
    namer = Namer(_graph(nodes, edges))
    assert namer.is_nameable("v1") and namer.is_nameable("v2")
    item = '{"class": "GateValve", "line_number": "l", "next_to": "t-1", "side": "upstream"}'
    assert namer.resolve_item(item) == {"v1"}


def test_a_tag_item_resolves_to_the_operated_valve_only() -> None:
    nodes = {"cv": ("GlobeValve", "FV-1"), "act": ("ActuatingFunction", "FV-1")}
    namer = Namer(_graph(nodes, []))
    assert namer.resolve_item("fv-1") == {"cv"}


def test_a_descriptor_missing_a_key_is_refused() -> None:
    namer = Namer(_graph(_CHAIN_NODES, _CHAIN_EDGES))
    with pytest.raises(ValueError, match="expected class, line_number, next_to"):
        namer.resolve_item('{"class": "GateValve"}')


# ---- folding the occurrence view ----------------------------------------------------------------


class _FakeView:
    """The two methods `build_flow_graph` reads."""

    def __init__(self, items: list[ItemRecord], edges: list[EdgeRecord]) -> None:
        self._items, self._edges = items, edges

    def items(self) -> list[ItemRecord]:
        return self._items

    def edges(self) -> list[EdgeRecord]:
        return self._edges


def _item(key: str, node_class: str, tag: str | None = None, **props: str) -> ItemRecord:
    properties = {"tag": tag, **props} if tag else dict(props)
    return ItemRecord(local_key=key, sheet_id=key.split(":")[0], node_class=node_class,
                      properties=properties)  # fmt: skip


def _edge(source: str, target: str, relation: str, line: str | None = None) -> EdgeRecord:
    return EdgeRecord(source=source, target=target, relation=relation,
                      properties={"line_number": line} if line else {})  # fmt: skip


def test_a_stub_pair_is_bridged_and_a_repeated_item_is_merged() -> None:
    # S1: P-1 -> valve -> out-stub ~continues_as~ in-stub (S2) -> tank -> P-1 drawn again on S2
    items = [
        _item("S1:p", "Pump", "P-1"),
        _item("S1:v", "GateValve", operating_position="NC"),
        _item("S1:out", "FlowOutPipeOffPageConnector"),
        _item("S2:in", "FlowInPipeOffPageConnector"),
        _item("S2:t", "Tank", "T-1"),
        _item("S2:p", "Pump", "P-1"),
    ]
    edges = [
        _edge("S1:p", "S1:v", "send_to", '6"-A'),
        _edge("S1:v", "S1:out", "send_to", '6"-A'),
        _edge("S1:out", "S2:in", "continues_as"),
        _edge("S2:in", "S2:t", "send_to", '6"-A'),
        _edge("S2:t", "S2:p", "send_to", "8-B"),
        _edge("S2:p", "S1:p", "same_tagged_item_as"),
    ]
    graph = build_flow_graph(_FakeView(items, edges))
    assert set(graph.classes) == {"S1:p", "S1:v", "S2:t"}  # stubs gone, the pump merged
    assert graph.successors["S1:v"] == {"S2:t"}
    assert graph.successors["S2:t"] == {"S1:p"}  # the reference occurrence flows into the home one
    assert graph.positions == {"S1:v": "NC"}
    assert graph.lines["S1:v"] == {fold_line("6-A")}
    assert graph.occurrences["S1:p"] == ("S1:p", "S2:p")


def test_two_stubs_joined_by_a_pipe_are_refused() -> None:
    items = [
        _item("S1:a", "FlowOutPipeOffPageConnector"),
        _item("S1:b", "FlowInPipeOffPageConnector"),
    ]
    with pytest.raises(ValueError, match="stub-to-stub"):
        build_flow_graph(_FakeView(items, [_edge("S1:a", "S1:b", "send_to")]))


def test_the_folds() -> None:
    assert fold_tag("  p-101 ") == fold_tag("P-101") and fold_tag("A  B") == "A B"
    assert fold_line('6"-p-1203-A1A') == fold_line("6-P-1203-A1A")
    assert fold_class("Gate-Valve") == fold_class("GateValve") == fold_class("gate valve")


def test_the_class_lists_equal_the_schema_lists() -> None:
    """Drift guard only: the module's own lists are written from the definition, not imported."""
    assert OPERATED_CLASSES == OPERATED_VALVE_CLASSES
    assert MY_EQUIPMENT == EQUIPMENT_CLASSES


# ---- a generated plant, then damage -------------------------------------------------------------


@pytest.fixture(scope="module")
def untagged_check() -> PlantCheck:
    return dev_plant_check(1, 30, "untagged")


@pytest.fixture(scope="module")
def tagged_check() -> PlantCheck:
    return dev_plant_check(2, 30, "tagged")


def test_a_generated_untagged_plant_agrees_in_every_family(untagged_check: PlantCheck) -> None:
    assert untagged_check.disagreements == []
    assert all(t.total > 0 and t.agree == t.total for t in untagged_check.tallies)
    for row in untagged_check.candidates:
        assert not row.only_mine_kept and not row.only_stored_kept
        assert row.mine_candidates == row.stored_candidates


def test_a_generated_tagged_plant_agrees_in_every_family(tagged_check: PlantCheck) -> None:
    assert tagged_check.disagreements == []
    assert sum(t.total for t in tagged_check.tallies) > 0


def _damaged_run(damage: str) -> list[str]:
    """Rebuild the plant, damage one thing, and return the ids the check now flags."""
    from plantgraph.benchmark.v2.generate import generate_plant_v2
    from plantgraph.benchmark.v2.valve_positions import positions_of
    from plantgraph.ingest.headline_v22 import HeadlinePresetV22
    from plantgraph.ingest.pipeline import build_synthetic_corpus
    from plantgraph.qa.exp0009.dev_plants import forced_config
    from plantgraph.qa.questions.scope_x import scope_x_candidates
    from plantgraph.qa.v2tb.positions import read_operating_positions
    from plantgraph.qa.v2tb.store_b import positions_by_local_key
    from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB

    config = forced_config(30, 1, untagged=True)
    corpus = build_synthetic_corpus(config, HeadlinePresetV22().split_config(1))
    generated = generate_plant_v2(config)
    positions = positions_by_local_key(
        read_operating_positions(generated.model), corpus.occurrence_map
    )
    if damage == "position":  # the view says every NO valve is NC
        positions = {k: ("NC" if v == "NO" else v) for k, v in positions.items()}
    view = NetworkxGraphViewB("t", corpus.localized_sheets, corpus.resolution, positions)
    outcomes = scope_x_candidates(
        corpus.plant, corpus.manifest, corpus.sheets,
        positions_of(generated.plan.unit_plans), corpus_id="t", seed=31,
    )  # fmt: skip
    questions = [q for o in outcomes.values() for q in o.kept]
    if damage == "reference":  # the stored gold of one isolation question loses a valve
        first = next(q for q in questions if isinstance(q.reference, list) and len(q.reference) > 1)
        assert isinstance(first.reference, list)
        questions = [first.model_copy(update={"reference": first.reference[1:]})]
    _, gaps = tally(questions, CrossChecker(build_flow_graph(view)))
    return [g.question_id for g in gaps]


def test_a_stored_reference_missing_a_valve_is_flagged() -> None:
    assert len(_damaged_run("reference")) == 1


def test_a_wrong_position_in_the_view_is_flagged() -> None:
    flagged = _damaged_run("position")
    assert any("POSITION_OF_VALVE" in q for q in flagged)
    assert any("OPEN_VALVES" in q for q in flagged)
