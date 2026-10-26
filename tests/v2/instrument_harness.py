"""Helpers for the instrument-template tests: graph lookups and motor-driven hosts.

Not a test module (no `test_` prefix). Builds on `trim_harness.TrimHarness`, which writes every plan
to the graph oracle and the DEXPI builder at once.
"""

from __future__ import annotations

import networkx as nx
from trim_harness import TrimHarness

from plantgraph.benchmark.v2.plan_models import EquipmentSpec, LineItemSpec
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.graph.schema import CLASS_SPECS, NodeClass, Relation


def motor_machine(h: TrimHarness, node_class: str = "CentrifugalPump") -> str:
    """Add one motor-driven machine (a pump, compressor or agitator) to unit 1; returns its id."""
    prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix or "P"
    node_id = f"motor-host-{len(h.oracle.graph)}"
    spec = EquipmentSpec(
        node_id=node_id,
        node_class=node_class,
        unit_no=1,
        tag=h.ctx.numbering.equipment_tag(prefix),
        has_motor=True,
    )
    h.builder.add_equipment(spec)
    return node_id


def item_spec(graph: nx.DiGraph[str], node_id: str) -> LineItemSpec:
    """The plan item of a node already in the graph (to attach a loop to a valve a trim built)."""
    data = graph.nodes[node_id]
    return LineItemSpec(node_id=node_id, node_class=data["node_class"], tag=data.get("tag"))


def targets(graph: nx.DiGraph[str], source: str, relation: Relation) -> list[str]:
    """The nodes `source` points to over `relation`, sorted."""
    return sorted(
        target
        for _, target, data in graph.out_edges(source, data=True)
        if data["relation"] == relation.value
    )


def sources(graph: nx.DiGraph[str], target: str, relation: Relation) -> list[str]:
    """The nodes that point to `target` over `relation`, sorted."""
    return sorted(
        source
        for source, _, data in graph.in_edges(target, data=True)
        if data["relation"] == relation.value
    )


def number_of(graph: nx.DiGraph[str], node_id: str) -> int:
    """The loop number in the node's tag (`LIC-12005` gives 5 with 3-digit sequences)."""
    parsed = parse_tag(graph.nodes[node_id]["tag"])
    assert parsed is not None, graph.nodes[node_id]["tag"]
    return parsed.sequence


def tags(graph: nx.DiGraph[str], node_ids: list[str]) -> list[str]:
    """The tag of each node, in the order given."""
    return [graph.nodes[node_id]["tag"] for node_id in node_ids]


def solenoids(h: TrimHarness) -> dict[str, str | None]:
    """On-off valve id -> the sub-tag of its solenoid `ControlledActuator`, from the DEXPI model."""
    model = h.dexpi.build()
    return {
        system.operatedValveReference.valve.id: (
            system.controlledActuator.subTagName if system.controlledActuator else None
        )
        for system in model.conceptualModel.actuatingSystems
    }
