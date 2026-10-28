"""How the line view shows up in the text the agent reads (kind, line-end marks, passed parts).

All three return an empty string for a graph without the line view, so the v1 rendering is
unchanged byte for byte.
"""

from __future__ import annotations

from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord


def kind_part(item: ItemRecord) -> str:
    """`, kind valve` inside an item line's parentheses."""
    return "" if item.kind is None else f", kind {item.kind}"


def marks_suffix(item: ItemRecord) -> str:
    """` [no inflow]` / ` [no outflow]` after an item line."""
    return "".join(f" {mark}" for mark in item.line_marks)


def via_suffix(edge: ItemEdge) -> str:
    """` [via STR-1, MX-2]` for the tagged parts a line edge passes through."""
    return f" [via {', '.join(edge.via_tags)}]" if edge.via_tags else ""
