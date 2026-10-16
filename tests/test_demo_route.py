"""The route view of an ask (DP-T18): which items, in which step, joined by which direct edges.

Built over the hand-made toy plant `qa_plant_api_toy` (see its docstring for the drawing) and
hand-made traces: no model, no network.
"""

from __future__ import annotations

from plantgraph.demo.app.route import MAX_EDGES, MAX_NODES, RouteView, route_view
from plantgraph.demo.app.trace_models import AgentStep, AskTrace, CypherStep
from plantgraph.qa.cascade.live_models import LiveAnswer
from plantgraph.qa.models import AnswerType, AnswerValue, FinalAnswer, Outcome
from plantgraph.qa.plant_api.item_graph import ItemGraph
from qa_plant_api_toy import NC, build_graph, item_id, toy_graph

PAGES = {"S1": 1, "S2": 2, "S3": 3}
QUESTION = "What is downstream of P1?"


def _live(
    answer: AnswerValue, answer_type: AnswerType = AnswerType.TAG_SET, question: str = QUESTION
) -> LiveAnswer:
    return LiveAnswer(
        question_text=question,
        corpus_id="toy",
        answer_type=answer_type,
        policy="p",
        evaluated_policy=True,
        notice=None,
        outcome=Outcome.ANSWERED,
        final_answer=FinalAnswer(answer=answer, not_present=False),
        answered_by="t",
        fell_back=False,
        tiers=(),
        latency_s=0.0,
        wall_s=0.0,
        cost_usd=0.0,
        spent_usd=0.0,
        from_cache=False,
        trace_sheets=(),
    )


def _agent(index: int, tool: str, args: dict[str, object], *tags: str) -> AgentStep:
    return AgentStep(
        index=index,
        tier="agent",
        reply="",
        tool=tool,
        args=args,
        observation="",
        items=tags,
    )


def _route(live: LiveAnswer, trace: AskTrace, graph: ItemGraph | None = None) -> RouteView | None:
    return route_view(live.question_text, live, trace, graph or toy_graph(), PAGES)


def _by_tag(view: RouteView) -> dict[str | None, int | None]:
    return {node.tag: node.first_step for node in view.nodes}


def _pairs(view: RouteView) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in view.edges}


def test_first_step_is_the_earliest_step_that_showed_the_item() -> None:
    trace = AskTrace(
        agent=(
            _agent(1, "find", {"tag": "T1"}, "T1"),
            _agent(2, "neighbours", {"item": "T1"}, "BV1", "T1"),
            _agent(3, "neighbours", {"item": "BV1"}, "P1", "BV1"),
        )
    )
    view = _route(_live(["P1"]), trace)
    assert view is not None
    assert view.steps[0] == "find {tag: T1}"
    assert _by_tag(view) == {"T1": 0, "BV1": 1, "P1": 2}


def test_items_only_in_the_question_or_answer_have_no_first_step() -> None:
    trace = AskTrace(agent=(_agent(1, "find", {"tag": "T1"}, "T1"),))
    view = _route(_live(["V2"]), trace)
    assert view is not None
    by_tag = {node.tag: node for node in view.nodes}
    assert by_tag["P1"].first_step is None and by_tag["P1"].in_question
    assert by_tag["V2"].first_step is None and by_tag["V2"].in_answer
    assert by_tag["T1"].first_step == 0 and not by_tag["T1"].in_answer
    # question-only first, then the steps, then answer-only
    assert [node.tag for node in view.nodes] == ["P1", "T1", "V2"]


def test_an_item_id_in_a_step_is_resolved_like_a_tag() -> None:
    trace = AskTrace(agent=(_agent(1, "neighbours", {"item": item_id("CHV")}, item_id("CHV")),))
    view = _route(_live("1", AnswerType.UNIT_ID), trace)
    assert view is not None and "CHV" in _by_tag(view)


def test_only_direct_edges_among_shown_items_are_drawn() -> None:
    # T1 and P1 are connected only through BV1, which is not shown: no edge may join them
    trace = AskTrace(agent=(_agent(1, "find", {}, "T1", "P1", "V1"),))
    view = _route(_live(["V1"]), trace)
    assert view is not None
    assert _pairs(view) == set()


def test_an_edge_keeps_its_relation_and_the_sheets_it_crosses() -> None:
    trace = AskTrace(agent=(_agent(1, "find", {}, "T1", "BV1", "P1", "FT"),))
    view = _route(_live(["P1"]), trace)
    assert view is not None
    edges = {(e.source, e.target): e for e in view.edges}
    crossing = edges[(item_id("BV1"), item_id("P1"))]
    assert (crossing.relation, crossing.crossed_sheets) == ("send_to", ("S1", "S2"))
    assert edges[(item_id("T1"), item_id("BV1"))].crossed_sheets == ()
    assert edges[(item_id("T1"), item_id("FT"))].relation == "measured_by"


def test_a_tag_path_answer_orders_its_items_and_marks_a_gap_where_no_edge_exists() -> None:
    path = ["T1", "BV1", "P1", "V2"]  # P1 -> GV2 -> V2: GV2 is skipped, so P1-V2 is a gap
    view = _route(_live(path, AnswerType.TAG_PATH), AskTrace())
    assert view is not None
    assert view.answer_path == tuple(item_id(tag) for tag in path)
    by_pair = {(e.source, e.target): e for e in view.edges}
    gap = by_pair[(item_id("P1"), item_id("V2"))]
    assert gap.relation == "none" and gap.on_answer_path
    assert by_pair[(item_id("T1"), item_id("BV1"))].on_answer_path
    assert by_pair[(item_id("T1"), item_id("BV1"))].relation == "send_to"
    assert len(view.edges) == 3


def test_a_set_answer_has_no_answer_path_and_no_gaps() -> None:
    view = _route(_live(["T1", "V2"]), AskTrace())
    assert view is not None
    assert view.answer_path == ()
    assert view.edges == ()


def test_a_cypher_only_answer_is_one_step_naming_the_items_in_the_rows() -> None:
    rows = ({"tag": "P1", "unit": "1"}, {"tag": "V1", "unit": "1"})
    cypher = CypherStep(tier="cypher", query="MATCH ...", context="...", rows=rows)
    view = _route(_live(["V1"]), AskTrace(cypher=(cypher,)))
    assert view is not None
    assert view.steps == ("Cypher query: 2 rows",)
    assert _by_tag(view) == {"P1": 0, "V1": 0}


def test_the_node_and_edge_caps_keep_answer_items_and_count_the_rest() -> None:
    graph = _long_chain(200)
    names = tuple(f"N{i}" for i in range(200))
    trace = AskTrace(agent=(_agent(1, "find", {}, *names),))
    view = _route(_live(["N199"], question="Which is the last?"), trace, graph)
    assert view is not None
    tags = [node.tag for node in view.nodes]
    assert len(tags) == MAX_NODES and "N199" in tags and "N0" in tags
    assert view.omitted_nodes == 200 - MAX_NODES
    assert len(view.edges) == MAX_EDGES  # 150 nodes of a 3-step-reach chain give far more


def test_no_item_anywhere_gives_no_route() -> None:
    live = _live("1", AnswerType.UNIT_ID, question="Is it fine?")
    assert _route(live, AskTrace()) is None


def test_a_route_serialises_to_json_for_the_page() -> None:
    trace = AskTrace(agent=(_agent(1, "find", {"tag": "BV1"}, "BV1", "P1"),))
    view = _route(_live(["P1"]), trace)
    assert view is not None
    data = view.model_dump(mode="json")
    assert data["steps"] == ["find {tag: BV1}"]
    assert data["nodes"][0]["family"] in {"valve", "equipment"}
    assert data["omitted_nodes"] == 0


def _long_chain(size: int) -> ItemGraph:
    """`size` tanks N0..; each sends to the next three, so 150 of them hold over 300 edges."""
    items = {f"N{i}": (NC.TANK.value, "1", ("S1",)) for i in range(size)}
    edges = [
        (f"N{i}", "send_to", f"N{i + step}", ())
        for i in range(size)
        for step in (1, 2, 3)
        if i + step < size
    ]
    return build_graph(items, edges)
