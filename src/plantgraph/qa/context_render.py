"""Turn selected sheets into the text a strategy sends, as occurrence or plant graph (ADR-0039).

Strategies *select* drawings (whole sheets, plus single drawings on "through-line" sheets);
a **renderer** writes that selection out. Two representations exist:

- **occurrence**: one node per drawn symbol, with the off-page connector stubs that join
  sheets (the graph as drawn);
- **plant**: one node per plant item, even if it is drawn on several sheets, and one direct
  edge per connection, so a line that crosses sheets is a single edge. Items one edge outside
  the selection (the **frontier**) are included, so a line leaving the excerpt still says where
  it goes.

Each representation can start with a short fixed **legend** (`prompts/legend_*.txt`) that says
how to read it. The plant one always does; the occurrence one is off unless asked, so the
occurrence text stays byte-identical to what earlier runs sent.

Only the resolver-built view and its item graph are read, never a gold field.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, Protocol

import networkx as nx

from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemEdge, PropertyValue, sheet_of_key
from plantgraph.qa.serialize import serialize_attributed_graph, serialize_graph

Representation = Literal["occurrence", "plant"]
REPRESENTATIONS: tuple[Representation, ...] = ("occurrence", "plant")

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class Rendered:
    """The text and what it holds, for the trace."""

    text: str
    #: Sheets with selected content, full or through-line, sorted.
    sheets: tuple[str, ...]
    through_line_sheets: tuple[str, ...]
    #: Local keys of every drawing behind the text, sorted (plant: all drawings of each shown item).
    keys: tuple[str, ...]
    #: Plant items written, frontier included; 0 for the occurrence representation.
    items: int
    frontier_items: int
    #: Every sheet any shown node is drawn on, sorted (plant: a frontier item adds its sheets).
    context_sheets: tuple[str, ...]


class ContextRenderer(Protocol):
    """Writes a selection of drawings as text."""

    representation: Representation

    def render(
        self, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]
    ) -> Rendered:
        """`full_sheets` whole, plus on each `through` sheet only the listed drawing keys."""
        ...


@cache
def legend_text(representation: Representation) -> str:
    """The fixed legend of a representation, without its trailing newline."""
    path = _PROMPTS_DIR / f"legend_{representation}.txt"
    return path.read_text(encoding="utf-8").strip()


def _with_legend(representation: Representation, body: str) -> str:
    return f"{legend_text(representation)}\n\n{body}"


def subgraph_with_through_lines(
    view: GraphView, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]
) -> nx.DiGraph[str]:
    """Whole sheets plus, on each through-line sheet, only its listed occurrences.

    Taking the induced graph of all sheets first and then deleting the unlisted
    nodes keeps the edges between a through-line and its neighbouring sheets.
    """
    graph = view.subgraph([*full_sheets, *through])
    kept = {key for keys in through.values() for key in keys}
    unlisted = [
        key for key in graph.nodes if graph.nodes[key]["sheet_id"] in through and key not in kept
    ]
    graph.remove_nodes_from(unlisted)
    return graph


class OccurrenceRenderer:
    """The graph as drawn: every selected symbol, off-page connector stubs included."""

    representation: Representation = "occurrence"

    def __init__(self, view: GraphView, *, legend: bool = False) -> None:
        self._view = view
        self._legend = legend

    def render(
        self, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]
    ) -> Rendered:
        """Serialize the selected symbols as drawn, then add the legend if asked."""
        graph = subgraph_with_through_lines(self._view, full_sheets, through)
        text = serialize_graph(graph).text
        if self._legend:
            text = _with_legend("occurrence", text)
        return Rendered(
            text=text,
            sheets=tuple(sorted(full_sheets | set(through))),
            through_line_sheets=tuple(sorted(through)),
            keys=tuple(sorted(graph.nodes)),
            items=0,
            frontier_items=0,
            context_sheets=tuple(sorted({graph.nodes[key]["sheet_id"] for key in graph.nodes})),
        )


class PlantRenderer:
    """The merged plant: selected drawings become items, joined by direct item edges."""

    representation: Representation = "plant"

    def __init__(self, item_graph: ItemGraph) -> None:
        self._graph = item_graph
        self._items_on_sheet: dict[str, set[str]] = defaultdict(set)
        self._edges_of: dict[str, list[ItemEdge]] = defaultdict(list)
        for item_id in item_graph.all_ids():
            for key in item_graph.item(item_id).occurrence_keys:
                self._items_on_sheet[sheet_of_key(key)].add(item_id)
        for edge in item_graph.edges:
            self._edges_of[edge.source].append(edge)
            self._edges_of[edge.target].append(edge)

    def render(
        self, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]
    ) -> Rendered:
        """Map the selection to items, add their edges and the frontier, and write them out."""
        selected = self._selected_items(full_sheets, through)
        edges = self._edges_touching(selected)
        frontier = {end for edge in edges for end in (edge.source, edge.target)} - selected
        shown = selected | frontier
        nodes = {item_id: self._node_attributes(item_id) for item_id in shown}
        body = serialize_attributed_graph(nodes, _edge_rows(edges))
        records = [self._graph.item(item_id) for item_id in shown]
        return Rendered(
            text=_with_legend("plant", body),
            sheets=tuple(sorted(full_sheets | set(through))),
            through_line_sheets=tuple(sorted(through)),
            keys=tuple(sorted(key for record in records for key in record.occurrence_keys)),
            items=len(shown),
            frontier_items=len(frontier),
            context_sheets=tuple(sorted({s for record in records for s in record.sheets})),
        )

    def _selected_items(
        self, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]
    ) -> set[str]:
        """Items with a drawing on a full sheet or among the through-line keys.

        A paired off-page connector stub belongs to no item, so it drops out here.
        """
        selected: set[str] = set()
        for sheet in full_sheets:
            selected |= self._items_on_sheet.get(sheet, set())
        for keys in through.values():
            found = (self._graph.item_of_key(key) for key in keys)
            selected |= {item_id for item_id in found if item_id is not None}
        return selected

    def _edges_touching(self, items: set[str]) -> list[ItemEdge]:
        """Edges with at least one end in `items`, each once; the far ends are the frontier."""
        unique = {
            (e.source, e.target, e.relation): e for i in items for e in self._edges_of.get(i, ())
        }
        return [unique[key] for key in sorted(unique)]

    def _node_attributes(self, item_id: str) -> dict[str, PropertyValue]:
        record = self._graph.item(item_id)
        return {
            **record.properties,
            "node_class": record.node_class,
            "sheets": "|".join(record.sheets),
        }


def _edge_rows(
    edges: list[ItemEdge],
) -> list[tuple[str, str, dict[str, PropertyValue]]]:
    """One GraphML edge per (source, target); two relations between one pair are joined by `|`."""
    by_pair: dict[tuple[str, str], list[ItemEdge]] = defaultdict(list)
    for edge in edges:
        by_pair[(edge.source, edge.target)].append(edge)
    return [
        (source, target, _edge_attributes(group)) for (source, target), group in by_pair.items()
    ]


def _edge_attributes(group: list[ItemEdge]) -> dict[str, PropertyValue]:
    first = group[0]
    attributes: dict[str, PropertyValue] = {
        **first.properties,
        "relation": "|".join(sorted({edge.relation for edge in group})),
    }
    if first.via:  # no sheet draws this edge whole: say which sheets it joins
        attributes["crossed_sheets"] = (
            f"{sheet_of_key(first.via[0])} to {sheet_of_key(first.via[-1])}"
        )
    return attributes
