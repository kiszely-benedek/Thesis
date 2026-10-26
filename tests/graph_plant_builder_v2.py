"""Test-only `PlantBuilderV2`: builds a schema-conformant `nx.DiGraph` straight from the plan.

The oracle that the DEXPI backend's output is later compared against; not a second production
path. Every call adds nodes or edges with exactly the properties `graph.schema` fixes, so it is
as simple as it can be. No `test_` prefix: pytest must not collect it as a test module.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
)
from plantgraph.graph.schema import Relation


class GraphPlantBuilderV2:
    """A schema-conformant, test-only implementation of the `PlantBuilderV2` protocol."""

    backend_version = "graph-test-builder-v2"

    def __init__(self, plant_id: str) -> None:
        self.plant_id = plant_id
        self.graph: nx.DiGraph[str] = nx.DiGraph()
        self.section_names: dict[int, str] = {}

    def add_section(self, unit_no: int, name: str) -> None:
        """A unit is structure, not a node here; only its title is kept."""
        self.section_names[unit_no] = name

    def add_equipment(self, spec: EquipmentSpec) -> None:
        """Add one equipment node (the motor is not a node: pyDEXPI drops it too)."""
        self._add_node(
            spec.node_id, node_class=spec.node_class, tag=spec.tag, unit_id=str(spec.unit_no)
        )

    def add_line(self, spec: LineSpec) -> None:
        """Add the inline items and chain `send_to` edges: `src -> item ... -> dst`."""
        for end_id in (spec.src_id, spec.dst_id):
            if end_id is not None:
                self._require_node(end_id, f"line {spec.line_number!r}")
        for item in spec.items:
            self._add_line_item(item, spec.unit_no)
        chain = [spec.src_id, *(item.node_id for item in spec.items), spec.dst_id]
        known = [node_id for node_id in chain if node_id is not None]
        for upstream, downstream in zip(known, known[1:], strict=False):
            self.graph.add_edge(
                upstream,
                downstream,
                relation=Relation.SEND_TO.value,
                line_number=spec.line_number,
                fluid_code=spec.fluid_code,
            )

    def add_instrument(self, spec: InstrumentSpec) -> None:
        """Add one instrument node; an actuator has no tag, so the key is left out."""
        self._add_node(
            spec.node_id,
            node_class=spec.node_class,
            tag=spec.tag,
            unit_id=str(spec.unit_no),
            loop_tag=spec.loop_tag,
            measured_variable=spec.measured_variable,
        )

    def add_link(self, spec: LinkSpec) -> None:
        """Add the edge; both ends must exist already."""
        context = f"{spec.relation.value} link"
        self._require_node(spec.source_id, context)
        self._require_node(spec.target_id, context)
        self.graph.add_edge(spec.source_id, spec.target_id, relation=spec.relation.value)

    def _add_line_item(self, item: LineItemSpec, unit_no: int) -> None:
        self._add_node(item.node_id, node_class=item.node_class, tag=item.tag, unit_id=str(unit_no))

    def _add_node(self, node_id: str, tag: str | None, **properties: str) -> None:
        if node_id in self.graph:
            raise ValueError(f"node id {node_id!r} added twice")
        self.graph.add_node(node_id, plant_id=self.plant_id, **properties)
        if tag is not None:  # an untagged part leaves the key out, as the importer does
            self.graph.nodes[node_id]["tag"] = tag

    def _require_node(self, node_id: str, context: str) -> None:
        if node_id not in self.graph:
            raise ValueError(f"{context} names node {node_id!r}, which was not added yet")
