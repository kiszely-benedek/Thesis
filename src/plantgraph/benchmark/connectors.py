"""The splitter's fourth step: cut cross-sheet edges apart with pairs of off-page connectors.

When an edge still runs between two sheets (not resolved by identity-based
duplication, see `splitter.py`), a stub node is placed on its behalf on each
sheet, and the two are linked in the answer key as one `ConnectorPair`
(`plant-generator.md` §5, finding 2a-2c).
"""

from __future__ import annotations

import random
from typing import Any

import networkx as nx

from plantgraph.benchmark.models import ConnectorKind, ConnectorPair, Direction, OffPageConnector
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import ConnectorLabelDetail, NumberingScheme, SplitConfig


def cut_remaining_edges(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    resolved_edges: set[tuple[str, str]],
    config: SplitConfig,
    rng: random.Random,
) -> list[ConnectorPair]:
    """Cut apart cross-sheet edges not resolved by duplication: pairs of off-page connectors."""
    counters: dict[str, int] = dict.fromkeys(sheets, 0)
    cross_edges = sorted(
        (source, target)
        for source, target in plant.edges()
        if node_sheet[source] != node_sheet[target] and (source, target) not in resolved_edges
    )
    return [
        _cut_one_edge(plant, sheets, node_sheet, source, target, counters, config, rng)
        for source, target in cross_edges
    ]


def _cut_one_edge(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    source: str,
    target: str,
    counters: dict[str, int],
    config: SplitConfig,
    rng: random.Random,
) -> ConnectorPair:
    """Cut one cross-sheet edge apart: two stub nodes, two OffPageConnectors, one pair."""
    sheet_source, sheet_target = node_sheet[source], node_sheet[target]
    edge_attrs = plant.edges[source, target]
    kind = _connector_kind(edge_attrs)
    loop_tag = _signal_loop_tag(plant, source, target) if kind is ConnectorKind.SIGNAL else None

    stub_out_id, tag_out = _new_stub(sheet_source, counters, config, rng)
    stub_in_id, tag_in = _new_stub(sheet_target, counters, config, rng)

    sheets[sheet_source].graph.add_node(
        stub_out_id,
        **_stub_node_attrs(
            _connector_class(kind, Direction.OUTGOING),
            tag_out,
            sheet_target,
            tag_in,
            edge_attrs,
            config,
            loop_tag,
        ),
    )
    sheets[sheet_source].graph.add_edge(source, stub_out_id, **edge_attrs)
    sheets[sheet_target].graph.add_node(
        stub_in_id,
        **_stub_node_attrs(
            _connector_class(kind, Direction.INCOMING),
            tag_in,
            sheet_source,
            tag_out,
            edge_attrs,
            config,
            loop_tag,
        ),
    )
    sheets[sheet_target].graph.add_edge(stub_in_id, target, **edge_attrs)

    connector_out = OffPageConnector(
        tag=tag_out,
        sheet_id=sheet_source,
        direction=Direction.OUTGOING,
        partner_sheet_id=sheet_target,
        partner_tag=tag_in,
        attached_node_id=stub_out_id,
        kind=kind,
        line_number=edge_attrs.get("line_number"),
        fluid_code=edge_attrs.get("fluid_code"),
        loop_tag=loop_tag,
    )
    connector_in = OffPageConnector(
        tag=tag_in,
        sheet_id=sheet_target,
        direction=Direction.INCOMING,
        partner_sheet_id=sheet_source,
        partner_tag=tag_out,
        attached_node_id=stub_in_id,
        kind=kind,
        line_number=edge_attrs.get("line_number"),
        fluid_code=edge_attrs.get("fluid_code"),
        loop_tag=loop_tag,
    )
    sheets[sheet_source].connectors.append(connector_out)
    sheets[sheet_target].connectors.append(connector_in)

    return ConnectorPair(
        from_key=connector_out.key, to_key=connector_in.key, original_edge=(source, target)
    )


def _connector_kind(edge_attrs: dict[str, Any]) -> ConnectorKind:
    """The cut edge's relation attribute decides the kind: send_to -> PIPE, else -> SIGNAL."""
    relation = edge_attrs.get("relation", "send_to")
    return ConnectorKind.PIPE if relation == "send_to" else ConnectorKind.SIGNAL


def _signal_loop_tag(plant: nx.DiGraph[str], source: str, target: str) -> str | None:
    """The control loop a signal cut belongs to: the source's loop_tag, else the target's.

    A signal line has no line number, so this loop number is what a real drawing
    prints on its off-page connector to tell two signal cuts apart (ADR-0027).
    """
    return plant.nodes[source].get("loop_tag") or plant.nodes[target].get("loop_tag")


def _connector_class(kind: ConnectorKind, direction: Direction) -> str:
    """The stub's node_class: direction and kind give the matching pyDEXPI connector class."""
    prefix = "FlowOut" if direction is Direction.OUTGOING else "FlowIn"
    suffix = "Pipe" if kind is ConnectorKind.PIPE else "Signal"
    return f"{prefix}{suffix}OffPageConnector"


def _stub_node_attrs(
    node_class: str,
    own_tag: str,
    partner_sheet_id: str,
    partner_tag: str,
    edge_attrs: dict[str, Any],
    config: SplitConfig,
    loop_tag: str | None,
) -> dict[str, Any]:
    """The stub node's visible labels (splitter.md finding 2b): what the resolver sees on the sheet.

    line_number/fluid_code are only added if they were really present on the cut
    edge — a measured_by/control edge doesn't carry them. loop_tag is set only
    on signal cuts (ADR-0027).
    """
    attrs: dict[str, Any] = {
        "node_class": node_class,
        "connector_number": own_tag,
        "referenced_drawing_number": partner_sheet_id,
    }
    for name in ("line_number", "fluid_code"):
        value = edge_attrs.get(name)
        if value is not None:
            attrs[name] = value
    if loop_tag is not None:
        attrs["loop_tag"] = loop_tag
    if config.connector_label_detail is ConnectorLabelDetail.FULL:
        attrs["referenced_connector_number"] = partner_tag
    return attrs


def _new_stub(
    sheet_id: str, counters: dict[str, int], config: SplitConfig, rng: random.Random
) -> tuple[str, str]:
    """Produce a unique stub identifier and label within the sheet.

    The counter guarantees uniqueness.
    """
    index = counters[sheet_id]
    counters[sheet_id] = index + 1
    node_id = f"opc:{sheet_id}:{index}"
    return node_id, _make_tag(config, sheet_id, index, rng)


def _make_tag(config: SplitConfig, sheet_id: str, index: int, rng: random.Random) -> str:
    """The connector's label, following the configured convention.

    The grammar is a generator parameter (splitter.md section 3).
    """
    if config.numbering_scheme is NumberingScheme.PID_STYLE:
        base = f"PID-{sheet_id}-{index}"
    else:
        base = f"SHEET-{sheet_id}-OPC-{index:02d}"
    if config.use_grid_reference:
        row = rng.choice("ABCDEFGH")
        column = rng.randint(1, 12)
        base = f"{base} ({row}-{column})"
    return base
