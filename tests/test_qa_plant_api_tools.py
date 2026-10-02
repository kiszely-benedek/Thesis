"""The tool registry and the contraction's error paths."""

from __future__ import annotations

import pytest

from plantgraph.graph.schema import NodeClass
from plantgraph.qa.graph_view import EdgeRecord
from plantgraph.qa.plant_api.contraction import contract
from plantgraph.qa.plant_api.model import PlantApiError
from plantgraph.qa.plant_api.results import ItemSet, PathResult, Subgraph, Table
from plantgraph.qa.plant_api.tool_registry import TOOLS, call_tool, tool_reference
from qa_plant_api_toy import member_tags, toy_api

_OUT = NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value
_IN = NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value
_PUMP = NodeClass.CENTRIFUGAL_PUMP.value


def test_the_registry_has_exactly_the_six_primitives() -> None:
    assert sorted(TOOLS) == ["aggregate", "filter", "find", "neighbours", "path", "traverse"]
    reference = tool_reference()
    assert all(f"{name}:" in reference for name in TOOLS)
    assert '"where"' in reference  # the filter's schema is part of the reference


def test_call_tool_runs_each_tool_from_json_arguments_and_handles_compose() -> None:
    api = toy_api()

    found = call_tool(api, "find", {"where": {"label": "OperatedValve"}})
    nearby = call_tool(
        api, "neighbours", {"of": "$r1", "direction": "downstream", "relations": "flow"}
    )
    reached = call_tool(
        api,
        "traverse",
        {"start": "T1", "direction": "downstream", "relations": "flow", "stop_at": {"unit": "2"}},
    )
    route = call_tool(api, "path", {"source": "T1", "target": "V2"})
    narrowed = call_tool(api, "filter", {"items": reached.handle, "where": {"sheet": "S2"}})
    grouped = call_tool(api, "aggregate", {"items": reached.handle, "group_by": "unit"})

    assert isinstance(found, ItemSet) and isinstance(nearby, Subgraph)
    assert isinstance(reached, Subgraph) and isinstance(route, PathResult)
    assert isinstance(narrowed, ItemSet) and isinstance(grouped, Table)
    assert member_tags(nearby) == ["P1", "V2"]
    assert ("GV2", True) in [(m.item.tag, m.is_stop) for m in reached.members]
    assert "V2" not in member_tags(reached)  # beyond the stop


def test_call_tool_defaults_match_the_primitives() -> None:
    result = call_tool(toy_api(), "path", {"source": "T1", "target": "BV1"})

    assert isinstance(result, PathResult) and result.hops == 1  # flow, directed


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("shortest", {}, "expected one of the tools.*'shortest'"),
        ("find", {"where": {"lable": "Pump"}}, "invalid arguments for find: where.lable"),
        ("neighbours", {"of": "P1"}, "invalid arguments for neighbours: direction"),
        ("neighbours", {"of": "P1", "direction": "sideways", "relations": "flow"}, "direction"),
        ("find", {"limit": "many"}, "limit"),
    ],
)
def test_call_tool_rejects_bad_input_with_what_was_expected(
    name: str, arguments: dict[str, object], message: str
) -> None:
    with pytest.raises(PlantApiError, match=message):
        call_tool(toy_api(), name, arguments)


def test_an_api_error_from_a_primitive_passes_through_call_tool() -> None:
    with pytest.raises(PlantApiError, match="known label"):
        call_tool(toy_api(), "find", {"where": {"label": "Valve"}})


# --- contraction error paths --------------------------------------------------


def _edge(source: str, target: str, relation: str) -> EdgeRecord:
    return EdgeRecord(source=source, target=target, relation=relation)


def test_an_identity_loop_is_an_error_naming_the_keys() -> None:
    classes = {"S1:a": _PUMP, "S2:b": _PUMP}
    edges = [
        _edge("S1:a", "S2:b", "same_tagged_item_as"),
        _edge("S2:b", "S1:a", "same_tagged_item_as"),
    ]

    with pytest.raises(ValueError, match="identity links loop"):
        contract(classes, edges)


def test_a_stub_pair_without_an_outgoing_end_is_an_error() -> None:
    classes = {"S1:i1": _IN, "S2:i2": _IN}

    with pytest.raises(ValueError, match="joins no outgoing stub"):
        contract(classes, [_edge("S1:i1", "S2:i2", "continues_as")])


def test_an_edge_leaving_a_paired_outgoing_stub_is_an_error() -> None:
    classes = {"S1:o": _OUT, "S2:i": _IN, "S2:x": _PUMP}
    edges = [_edge("S1:o", "S2:i", "continues_as"), _edge("S1:o", "S2:x", "send_to")]

    with pytest.raises(ValueError, match="leaves a paired outgoing stub"):
        contract(classes, edges)


def test_a_chain_of_stub_pairs_contracts_to_one_edge_through_every_stub() -> None:
    classes = {
        "S1:a": _PUMP,
        "S1:o1": _OUT,
        "S2:i1": _IN,
        "S2:o2": _OUT,
        "S3:i2": _IN,
        "S3:b": _PUMP,
    }
    edges = [
        _edge("S1:a", "S1:o1", "send_to"),
        _edge("S1:o1", "S2:i1", "continues_as"),
        _edge("S2:i1", "S2:o2", "send_to"),
        _edge("S2:o2", "S3:i2", "continues_as"),
        _edge("S3:i2", "S3:b", "send_to"),
    ]

    contracted = contract(classes, edges)

    assert [(e.source, e.target, e.via) for e in contracted.edges] == [
        ("S1:a", "S3:b", ("S1:o1", "S2:i1", "S2:o2", "S3:i2"))
    ]
