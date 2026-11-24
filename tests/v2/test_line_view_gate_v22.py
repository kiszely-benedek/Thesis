"""Task T6b (design 17.15 S7): LINE-01 for v2.2, and the frozen A2 layers on an untagged plant."""

from __future__ import annotations

from corpus_v2 import corpus as v21_corpus
from t6b_plants import corpus

from plantgraph.qa.exp0009.line_view_gate import (
    LineSide,
    compare_sides,
    gold_side,
    system_side,
)
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.line_view_fidelity import (
    compare_line_views,
    gold_line_view,
    system_line_view,
)
from plantgraph.qa.plant_api.item_graph import build_item_graph
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.store.neo4j_plan import build_load_plan


def _view(synthetic: object) -> NetworkxGraphView:
    return NetworkxGraphView("T6B", synthetic.localized_sheets, synthetic.resolution)  # type: ignore[attr-defined]


def test_on_a_v21_plant_the_gate_gives_the_frozen_result() -> None:
    synthetic = v21_corpus(30)
    graph = build_item_graph(_view(synthetic))
    frozen = compare_line_views("T6B", system_line_view(graph), gold_line_view(synthetic.plant))
    gate = compare_sides("T6B", system_side(graph), gold_side(synthetic.plant))
    assert gate.fidelity == frozen
    assert gate.passed and gate.n_untagged_items == 0 and gate.key_collisions == 0


def test_on_an_untagged_plant_the_views_agree_edge_for_edge() -> None:
    synthetic = corpus(1, untagged=True)
    graph = build_item_graph(_view(synthetic))
    gate = compare_sides("T6B", system_side(graph), gold_side(synthetic.plant))
    assert gate.n_untagged_items > 0
    assert (gate.fidelity.precision, gate.fidelity.recall) == (1.0, 1.0)
    assert not gate.fidelity.items_only_in_system and not gate.fidelity.items_only_in_gold
    assert gate.key_collisions == 0 and gate.passed


def _side(
    tags: dict[str, str | None], classes: dict[str, str], flow: list[tuple[str, str]]
) -> LineSide:
    """A side whose line edges are its flow edges between line items (no fittings in between)."""
    line_edges = [(s, t, 0) for s, t in flow if s in tags and t in tags]
    return LineSide(tags, line_edges, classes, flow)


_PUMP, _GATE, _TEE, _BLIND = "CentrifugalPump", "GateValve", "PipeTee", "BlindFlange"


def test_two_untagged_twins_between_the_same_items_collide() -> None:
    classes = {"p": _PUMP, "a": _GATE, "b": _GATE, "fa": _BLIND, "fb": _BLIND}
    flow = [("p", "a"), ("p", "b"), ("a", "fa"), ("b", "fb")]
    side = _side({"p": "P-1", "a": None, "b": None}, classes, flow)
    assert side.names()["a"] == side.names()["b"]
    assert compare_sides("T6B", side, side).key_collisions == 1


def test_what_hangs_off_a_valve_tells_two_untagged_valves_apart() -> None:
    classes = {"p": _PUMP, "a": _GATE, "b": _GATE, "fa": _BLIND, "tb": _TEE}
    flow = [("p", "a"), ("p", "b"), ("a", "fa"), ("b", "tb")]
    names = _side({"p": "P-1", "a": None, "b": None}, classes, flow).names()
    assert names["a"] != names["b"] and names["p"] == "P-1"


def test_a_swapped_untagged_edge_is_caught() -> None:
    classes = {"p": _PUMP, "q": _PUMP, "a": _GATE}
    tags: dict[str, str | None] = {"p": "P-1", "a": None, "q": "P-2"}
    system = _side(tags, classes, [("p", "a")])
    gold = _side(tags, classes, [("q", "a")])
    result = compare_sides("T6B", system, gold)
    assert not result.passed and result.fidelity.precision == 0.0


def test_the_colouring_does_not_depend_on_node_ids() -> None:
    classes = {"p": _PUMP, "a": _GATE, "f": _BLIND}
    renamed = {"x": _PUMP, "y": _GATE, "z": _BLIND}
    first = _side({"p": "P-1", "a": None}, classes, [("p", "a"), ("a", "f")]).names()["a"]
    second = _side({"x": "P-1", "y": None}, renamed, [("x", "y"), ("y", "z")]).names()["y"]
    assert first == second


def test_the_frozen_layers_that_use_no_model_run_on_an_untagged_plant() -> None:
    synthetic = corpus(1, untagged=True)
    view = _view(synthetic)
    plain = build_item_graph(view)
    lined = build_item_graph(view, line_view=True)
    assert plain.all_ids() and lined.line_edges
    for profile in ("plant", "plant_lines"):
        plan = build_load_plan(
            "T6B", synthetic.localized_sheets, synthetic.resolution, profile=profile
        )
        assert build_schema_text(plan)
