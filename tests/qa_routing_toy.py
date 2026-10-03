"""A hand-built corpus for the routing tests: sheets, items, cuts and identity links, all by name.

Built straight into `SheetGraph`s with already-opaque node ids and handed to
`NetworkxGraphView` with a hand-written `Resolution`, so each test states in
one line which sheets touch and how. Node ids are the local ids; the view's
local key is `"<sheet>:<id>"`.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.resolution.models import Resolution, ResolutionReport

_OUT_STUB = NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value
_IN_STUB = NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value


def key(sheet: str, node: str) -> str:
    return f"{sheet}:{node}"


class ToyCorpus:
    """Add sheets' items, `send_to` edges, cuts and identity groups, then call `view()`."""

    def __init__(self) -> None:
        self._graphs: dict[str, nx.DiGraph[str]] = {}
        self._pairs: list[ConnectorPair] = []
        self._groups: list[IdentityGroup] = []

    def sheet(self, sheet: str) -> None:
        self._graphs.setdefault(sheet, nx.DiGraph())

    def item(
        self,
        sheet: str,
        node: str,
        tag: str,
        *,
        node_class: NodeClass = NodeClass.CENTRIFUGAL_PUMP,
        **properties: str,
    ) -> None:
        self.sheet(sheet)
        self._graphs[sheet].add_node(node, node_class=node_class.value, tag=tag, **properties)

    def flow(self, sheet: str, source: str, target: str, **properties: str) -> None:
        self._graphs[sheet].add_edge(source, target, relation=Relation.SEND_TO.value, **properties)

    def cut(self, sheet_a: str, node_a: str, sheet_b: str, node_b: str, name: str) -> None:
        """Replace the pipe `node_a -> node_b` by `node_a -> out-stub ~ in-stub -> node_b`."""
        out_id, in_id = f"out_{name}", f"in_{name}"
        self.sheet(sheet_b)
        self._graphs[sheet_a].add_node(out_id, node_class=_OUT_STUB)
        self._graphs[sheet_b].add_node(in_id, node_class=_IN_STUB)
        self.flow(sheet_a, node_a, out_id)
        self.flow(sheet_b, in_id, node_b)
        self._pairs.append(ConnectorPair(from_key=key(sheet_a, out_id), to_key=key(sheet_b, in_id)))

    def dangling_stub(self, sheet: str, node: str, name: str) -> None:
        """An outgoing stub after `node` that the resolver found no partner for."""
        stub_id = f"out_{name}"
        self._graphs[sheet].add_node(stub_id, node_class=_OUT_STUB)
        self.flow(sheet, node, stub_id)

    def identity(self, tag: str, home: tuple[str, str], references: list[tuple[str, str]]) -> None:
        self._groups.append(
            IdentityGroup(
                tag=tag,
                home=key(*home),
                references=[key(sheet, node) for sheet, node in references],
            )
        )

    def view(self) -> NetworkxGraphView:
        sheets = [SheetGraph(sheet_id=sid, graph=graph) for sid, graph in self._graphs.items()]
        report = ResolutionReport(
            n_sheets=len(sheets),
            n_occurrences=0,
            n_connectors=0,
            pairs_by_rule={},
            unresolved_by_reason={},
            n_identity_groups=len(self._groups),
            ambiguous_tag_keys=0,
            edge_attribute_conflicts=0,
        )
        resolution = Resolution(
            plant=nx.DiGraph(),
            connector_pairs=self._pairs,
            identity_groups=self._groups,
            unresolved=[],
            report=report,
        )
        return NetworkxGraphView("toy", sheets, resolution)
