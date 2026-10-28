"""`graph_agent_lines`: the V2T agent over the line view, and F1's prompt left untouched."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from corpus_v2 import corpus

from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.agent.prompts import plant_summary, render_system_prompt
from plantgraph.qa.agent.strategies import GraphAgent, GraphAgentLines
from plantgraph.qa.agent.tool_text import compact_tool_reference
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.registry import LlmDeps, build_strategy
from plantgraph.qa.plant_api.item_graph import build_item_graph
from qa_agent_fakes import PIN, ScriptedModel
from qa_plant_api_toy import toy_graph

_ROOT = Path(__file__).resolve().parents[2]
_PARAMS_FILE = _ROOT / "data/runs/exp0007/inputs/params_agent_v2t.json"


def _view() -> NetworkxGraphView:
    built = corpus()
    return NetworkxGraphView("T", built.localized_sheets, built.resolution)


def test_the_registry_builds_the_lines_agent_over_the_line_view() -> None:
    deps = LlmDeps(PIN, ScriptedModel([]))

    agent = build_strategy("graph_agent_lines", {}, _view(), llm=deps)

    assert isinstance(agent, GraphAgentLines) and agent.name == "graph_agent_lines"
    assert "line_to" in agent.system_prompt and "kind valve" in agent.system_prompt


def test_the_lines_agent_refuses_a_graph_without_the_line_view() -> None:
    with pytest.raises(ValueError, match="line view for graph_agent_lines"):
        GraphAgentLines(toy_graph(), PIN, ScriptedModel([]))


def test_the_v1_agents_prompt_and_tool_reference_do_not_mention_the_line_view() -> None:
    prompt = render_system_prompt(AgentParams(), primer=False, seeded=False)

    for word in ("line_to", "kind?", "kind valve", "[no inflow]"):
        assert word not in prompt
    assert "relations: flow|signal|any," in prompt
    assert compact_tool_reference() == compact_tool_reference(line_view=False)


def test_the_plant_summary_names_the_line_relation_and_the_valve_label() -> None:
    summary = plant_summary(build_item_graph(_view(), line_view=True))

    assert "line (line_to)" in summary and "Valve" in summary
    assert "line_to" not in plant_summary(build_item_graph(_view()))


def test_the_v2t_params_file_sets_the_agreed_limits_under_the_lines_name() -> None:
    entry = json.loads(_PARAMS_FILE.read_text(encoding="utf-8"))["graph_agent_lines"]
    params = AgentParams.model_validate(entry)

    assert (params.observation_chars, params.max_items_listed) == (32_000, 400)
    assert params.max_prompt_chars_total == 600_000
    assert (params.max_steps, params.step_effort, params.final_reserve_s) == (40, "low", 30.0)


def test_graph_agent_stays_the_plain_class() -> None:
    deps = LlmDeps(PIN, ScriptedModel([]))
    agent = build_strategy("graph_agent", {}, _view(), llm=deps)

    assert type(agent) is GraphAgent and "line_to" not in agent.system_prompt
