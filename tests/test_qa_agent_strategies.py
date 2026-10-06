"""Prompts, seed map, `GraphAgent`, `HierAgent` and their registry entries, offline (QAR-T6)."""

from __future__ import annotations

from typing import Any

import pytest

from plantgraph.graph import schema
from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.agent.prompts import first_user_message, plant_summary, render_system_prompt
from plantgraph.qa.agent.seed import build_seed
from plantgraph.qa.agent.strategies import GraphAgent, HierAgent
from plantgraph.qa.context_render import legend_text
from plantgraph.qa.harness.registry import LlmDeps, build_strategy
from plantgraph.qa.need.classifiers import NeedDecision, NeedInput
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord, PlantApiError
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import item_line
from plantgraph.qa.primer import primer_block, primer_text
from qa_agent_fakes import DONE, PIN, ScriptedModel, call
from qa_need_toy import ISOLATION_QUESTION, PATH_QUESTION, need_toy

_PARAMS = AgentParams()


def _plant() -> tuple[Any, ItemGraph]:
    view = need_toy().view()
    return view, build_item_graph(view)


# --- prompts ------------------------------------------------------------------------


def test_primer_off_leaves_no_primer_text_and_on_adds_exactly_its_block() -> None:
    off = render_system_prompt(_PARAMS, primer=False, seeded=False)
    on = render_system_prompt(_PARAMS, primer=True, seeded=False)

    assert primer_text() not in off and "General P&ID reading conventions" not in off
    assert primer_block() in on
    assert on.replace(primer_block() + "\n\n", "") == off  # nothing else differs
    for text in (off, on):
        assert "<<" not in text  # every slot was filled or removed


def test_the_seed_rule_appears_only_for_the_seeded_agent() -> None:
    graph_prompt = render_system_prompt(_PARAMS, primer=False, seeded=False)
    hier_prompt = render_system_prompt(_PARAMS, primer=False, seeded=True)

    assert "seed map" not in graph_prompt
    assert "seed map" in hier_prompt
    assert hier_prompt.startswith(graph_prompt.split("\n\nRules.")[0])


def test_the_prompt_lists_every_tool_and_the_step_limit() -> None:
    prompt = render_system_prompt(AgentParams(max_steps=4), primer=False, seeded=False)

    for name in ("find", "neighbours", "traverse", "path", "filter", "aggregate"):
        assert f"\n{name}(" in prompt
    assert "at most 4 replies" in prompt


def test_the_reading_direction_sentence_matches_the_plant_legend() -> None:
    # the agent prompt restates the legend's loop sentence; if the legend changes, so must it
    chain = (
        "equipment -measured_by-> transmitter -send_signal_to-> controller "
        "-send_signal_to-> actuator -control-> valve"
    )

    assert chain in legend_text("plant")
    assert chain in render_system_prompt(_PARAMS, primer=False, seeded=False)


def test_the_plant_summary_names_the_sheets_units_and_labels() -> None:
    _, graph = _plant()

    summary = plant_summary(graph)

    assert summary.startswith('The plant has 3 sheets (for example "S1") and 3 units')
    assert "BallValve" in summary and "CentrifugalPump" in summary


def test_the_first_message_orders_summary_question_seed() -> None:
    assert first_user_message("SUM", "Q?", None) == "SUM\n\nQuestion:\nQ?"
    assert first_user_message("SUM", "Q?", "SEED") == "SUM\n\nQuestion:\nQ?\n\nSEED"


# --- untagged items ------------------------------------------------------------------


def _untagged_actuator_graph() -> ItemGraph:
    """FIC -> actuator (no tag) -> BV1; the actuator can only be named by its id."""
    classes = {
        "FIC": schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        "S1:act": schema.NodeClass.ACTUATING_FUNCTION.value,
        "BV1": schema.NodeClass.BALL_VALVE.value,
    }
    records = [
        ItemRecord(
            item_id=item_id,
            tag=None if item_id == "S1:act" else item_id,
            node_class=node_class,
            labels=schema.labels_for(node_class),
            unit_id="1",
            sheets=("S1",),
            occurrence_keys=(f"S1:{item_id.lower()}",),
        )
        for item_id, node_class in classes.items()
    ]
    edges = [
        ItemEdge(source="FIC", target="S1:act", relation="send_signal_to"),
        ItemEdge(source="S1:act", target="BV1", relation="control"),
    ]
    return ItemGraph(records, edges, {"fic": ("FIC",), "bv1": ("BV1",)})


def test_an_untagged_actuator_is_listed_by_its_id_and_that_id_works_as_a_reference() -> None:
    api = PlantApi(_untagged_actuator_graph())

    around = api.neighbours("BV1", "upstream", "signal")
    shown = around.render()
    onward = api.neighbours("S1:act", "downstream", "signal")

    assert "S1:act (ActuatingFunction, unit 1, sheets S1)" in shown
    assert "S1:act -control-> BV1" in shown
    assert [m.item.tag for m in onward.members] == ["BV1"]


def test_an_unknown_reference_error_names_the_three_kinds_of_reference() -> None:
    with pytest.raises(PlantApiError, match="id of an untagged item or a handle"):
        PlantApi(_untagged_actuator_graph()).neighbours("S9:zz", "both", "any")


# --- the seed map --------------------------------------------------------------------


def test_the_seed_runs_the_rules_program_and_lists_named_items_first() -> None:
    view, graph = _plant()

    seed = build_seed(ISOLATION_QUESTION, view, graph, seed_chars=12_000)

    lines = seed.text.splitlines()
    assert seed.label == "UPSTREAM_TO_FIRST_VALVE" and seed.program_skipped is None
    assert lines[2].startswith("P-3 (") and lines[2].endswith("[named in the question]")
    assert any(line.startswith("P-2 (") and "[hop 1]" in line for line in lines)
    assert any(line.startswith("XV-1 (") and "[hop 2]" in line for line in lines)
    assert any(line.startswith("P-2 -send_to-> P-3") for line in lines)
    assert any("traverse" in call_text for call_text in seed.program)
    assert "S3:t" in seed.touched_keys and "S1:a" not in seed.touched_keys  # beyond the valve


def test_a_question_with_no_recognised_shape_seeds_only_the_named_items() -> None:
    view, graph = _plant()

    seed = build_seed("Please tell me more about P-2.", view, graph, seed_chars=12_000)

    assert seed.label == "GENERIC" and seed.program_skipped == "generic"
    assert seed.n_items_shown == 1 and "P-2 (" in seed.text


def test_a_question_naming_nothing_says_so() -> None:
    view, graph = _plant()

    seed = build_seed("Which pump is the biggest?", view, graph, seed_chars=12_000)

    assert seed.n_items_shown == 0 and "No item the question names was found" in seed.text


def test_a_program_that_cannot_run_is_skipped_with_the_reason() -> None:
    view, graph = _plant()

    seed = build_seed(PATH_QUESTION.replace(" to P-3", ""), view, graph, 12_000)

    assert seed.label == "PATH" and (seed.program_skipped or "").startswith("precondition")
    assert seed.n_items_shown == 1


def test_a_seed_over_its_cap_is_cut_with_a_note_and_counts_only_what_it_shows() -> None:
    view, graph = _plant()
    full = build_seed(ISOLATION_QUESTION, view, graph, seed_chars=12_000)

    cut = build_seed(ISOLATION_QUESTION, view, graph, seed_chars=len(full.text) - 80)

    assert len(cut.text) <= len(full.text) - 80
    assert "more lines not shown" in cut.text
    assert set(cut.touched_keys) < set(full.touched_keys)


def test_the_seed_uses_the_injected_classifier() -> None:
    view, graph = _plant()

    class _Fixed:
        name = "fixed"

        def classify(self, need_input: NeedInput) -> NeedDecision:
            return NeedDecision(label=NeedLabel.NEIGHBOURS_UPSTREAM, classifier="fixed")

    seed = build_seed(ISOLATION_QUESTION, view, graph, 12_000, classifier=_Fixed())

    assert seed.label == "NEIGHBOURS_UPSTREAM"
    assert any(line.startswith("P-2 (") for line in seed.text.splitlines())


def test_item_lines_in_the_seed_use_the_shared_plant_api_format() -> None:
    view, graph = _plant()
    record = graph.item(graph.ids_for_tag("P-3")[0])

    assert item_line(record) in build_seed(ISOLATION_QUESTION, view, graph, 12_000).text


# --- the strategies -------------------------------------------------------------------


def test_graph_agent_gathers_what_the_model_asks_for_and_reports_it_in_the_trace() -> None:
    _, graph = _plant()
    model = ScriptedModel(
        [call("traverse", start="P-3", direction="upstream", relations="flow"), DONE]
    )
    agent = GraphAgent(graph, PIN, model)

    result = agent.retrieve(ISOLATION_QUESTION)

    assert result.failure is None and result.context is not None
    assert result.context.startswith("Tool results gathered for this question:")
    assert "XV-1 (BallValve" in result.context and "Call: traverse(" in result.context
    trace = result.trace
    assert trace["stop_reason"] == "done" and trace["n_steps"] == 2
    assert trace["routed_sheets"] == ["S1", "S2", "S3"]
    assert {"S1:a", "S3:t"} <= set(trace["serialized_keys"])
    assert trace["context_chars"] == len(result.context) and "seed_label" not in trace
    assert [s["tool"] for s in trace["agent_steps"]] == ["traverse", None]
    # the model saw the question text after the plant summary, nothing else about the question
    first_user = model.requests[0].messages[1].content
    assert first_user.endswith(f"Question:\n{ISOLATION_QUESTION}")
    assert agent.name == "graph_agent"


def test_graph_agent_that_calls_nothing_still_returns_a_context() -> None:
    _, graph = _plant()

    result = GraphAgent(graph, PIN, ScriptedModel([DONE])).retrieve("Anything?")

    assert result.context is not None and result.context.endswith("(no tool calls were made)")
    assert result.trace["routed_sheets"] == [] and result.trace["serialized_keys"] == []


def test_two_questions_never_share_handles() -> None:
    _, graph = _plant()
    agent = GraphAgent(graph, PIN, ScriptedModel([call("find", limit=1), DONE] * 2))

    agent.retrieve("one")
    second = agent.retrieve("two")

    # each question has a fresh `PlantApi`, so its first result is `$r1` again
    assert second.context is not None and "$r1:" in second.context


def test_hier_agent_may_stop_at_once_on_its_seed_and_the_seed_is_the_context() -> None:
    view, graph = _plant()
    model = ScriptedModel([DONE])
    agent = HierAgent(view, graph, PIN, model)

    result = agent.retrieve(ISOLATION_QUESTION)

    assert agent.name == "hier_agent" and len(model.requests) == 1
    assert result.context is not None and result.context.startswith("Seed map")
    assert "XV-1 (" in result.context
    first_user = model.requests[0].messages[1].content
    assert first_user.index("Question:") < first_user.index("Seed map")
    trace = result.trace
    assert trace["seed_label"] == "UPSTREAM_TO_FIRST_VALVE" and trace["seed_items"] >= 3
    assert {"S2:m", "S3:t"} <= set(trace["serialized_keys"])  # seed items count as evidence


def test_hier_agent_can_fetch_more_after_its_seed() -> None:
    view, graph = _plant()
    fetch = call("neighbours", of="XV-1", direction="upstream", relations="flow")
    model = ScriptedModel([fetch, DONE])

    result = HierAgent(view, graph, PIN, model).retrieve(ISOLATION_QUESTION)

    assert len(model.requests) == 2 and result.trace["n_steps"] == 2
    assert "S1:a" in result.trace["serialized_keys"]  # P-1, fetched beyond the seed


def test_the_primer_flag_reaches_the_system_prompt() -> None:
    _, graph = _plant()
    model = ScriptedModel([DONE])

    GraphAgent(graph, PIN, model, primer=True).retrieve("q")

    assert primer_block() in model.requests[0].messages[0].content


# --- the registry ----------------------------------------------------------------------


def test_the_registry_builds_both_agents_and_passes_the_primer_flag() -> None:
    view = need_toy().view()
    deps = LlmDeps(PIN, ScriptedModel([DONE]), primer=True)

    graph_agent = build_strategy("graph_agent", {}, view, llm=deps)
    hier_agent = build_strategy("hier_agent", {"max_steps": 3}, view, llm=deps)

    assert isinstance(graph_agent, GraphAgent) and graph_agent.name == "graph_agent"
    assert isinstance(hier_agent, HierAgent) and hier_agent.params.max_steps == 3
    assert primer_block() in graph_agent.system_prompt


def test_the_registry_refuses_an_agent_without_a_model_or_with_an_unknown_parameter() -> None:
    view = need_toy().view()
    deps = LlmDeps(PIN, ScriptedModel([]))

    with pytest.raises(ValueError, match="expected a model sender for graph_agent"):
        build_strategy("graph_agent", {}, view)
    with pytest.raises(ValueError, match="max_stepz"):
        build_strategy("graph_agent", {"max_stepz": 3}, view, llm=deps)
    with pytest.raises(ValueError, match="graph_agent.*hier_agent"):
        build_strategy("no_such_strategy", {}, view)
