"""The pair card: one text describing two candidate occurrences, read by every context decider.

Terms: an **occurrence** is one drawing symbol of an equipment item on one sheet (a drawing page).
A **candidate pair** is two occurrences on different sheets that might be the same physical item
although their tags are written differently (`P-1203A` vs `12-P-03A`). The card shows what a human
reader would see on the two drawings: the tag, the class, the sheet, the printed unit and the
items drawn next to it. It is built only from visible properties of localized sheets and the
resolver's own connector pairs. It never contains an occurrence id, the split manifest or a
variant draw (design `exp0004-v2.md` section 5.1).
"""

from __future__ import annotations

from typing import Any, NamedTuple

from plantgraph.benchmark.sheet_graph import SheetGraph

#: neighbours listed per occurrence; the closest ones by tag, so the card stays short
MAX_NEIGHBOURS = 6

#: relation -> (phrase when the occurrence is the edge's source, phrase when it is the target)
_RELATION_PHRASES: dict[str, tuple[str, str]] = {
    "send_to": ("sends to", "receives from"),
    "send_signal_to": ("sends signal to", "receives signal from"),
    "control": ("controls", "controlled by"),
    "measured_by": ("measured by", "measures"),
    "has_agitator": ("has agitator", "agitator of"),
}


class OccurrenceDescription(NamedTuple):
    """Everything the card says about one occurrence (all of it visible on the drawing)."""

    sheet_id: str
    tag: str
    node_class: str
    property_count: int  # how many printed properties; a bare reference has few
    unit: str | None  # None: the symbol does not print its unit (a reference does not)
    units_on_sheet: tuple[str, ...]
    neighbours: tuple[str, ...]  # already rendered, e.g. 'GTV-12107 (sends to, line 6-P-1)'


def describe_occurrence(sheet: SheetGraph, node_id: str) -> OccurrenceDescription:
    """Read one occurrence's visible properties and its 1-hop neighbourhood off its sheet."""
    attributes = sheet.graph.nodes[node_id]
    unit = attributes.get("unit_id")
    return OccurrenceDescription(
        sheet_id=sheet.sheet_id,
        tag=str(attributes["tag"]),
        node_class=str(attributes["node_class"]),
        property_count=len(attributes),
        unit=None if unit is None else str(unit),
        units_on_sheet=_units_on_sheet(sheet),
        neighbours=_rendered_neighbours(sheet, node_id),
    )


def richer_first(
    one: OccurrenceDescription, other: OccurrenceDescription
) -> tuple[OccurrenceDescription, OccurrenceDescription]:
    """Order a pair as (A, B): A has more properties; a tie goes to the lower sheet id.

    The order only depends on what is printed, so every decider gets the same A and B.
    """
    first, second = sorted((one, other), key=lambda o: (-o.property_count, o.sheet_id))
    return first, second


def render_pair_card(
    first: OccurrenceDescription, second: OccurrenceDescription, joining_connector_pairs: int
) -> str:
    """The card text for the pair (A, B); the count is of connector pairs between their sheets."""
    return "\n".join(
        [
            f"Occurrence A: {_render_occurrence(first)}",
            f"Occurrence B: {_render_occurrence(second)}",
            _render_sheet_link(first.sheet_id, second.sheet_id, joining_connector_pairs),
        ]
    )


def _render_occurrence(occurrence: OccurrenceDescription) -> str:
    fields = [
        f'tag "{occurrence.tag}"',
        f"class {occurrence.node_class}",
        f"sheet {occurrence.sheet_id}",
        _render_unit(occurrence),
        f"drawn next to: {_render_neighbours(occurrence.neighbours)}",
    ]
    return "; ".join(fields)


def _render_unit(occurrence: OccurrenceDescription) -> str:
    if occurrence.unit is not None:
        return f"unit {occurrence.unit}"
    # a reference prints no unit; the units of the other items on its sheet are the next best hint
    units = ", ".join(occurrence.units_on_sheet) or "none"
    return f"unit not printed; units on sheet {occurrence.sheet_id}: {units}"


def _render_neighbours(neighbours: tuple[str, ...]) -> str:
    return ", ".join(neighbours) if neighbours else "nothing"


def _render_sheet_link(first_sheet: str, second_sheet: str, joining_connector_pairs: int) -> str:
    if joining_connector_pairs == 0:
        return f"No off-page connector pair joins sheets {first_sheet} and {second_sheet}."
    noun = "pair" if joining_connector_pairs == 1 else "pairs"
    return (
        f"Sheets {first_sheet} and {second_sheet} are joined by "
        f"{joining_connector_pairs} off-page connector {noun}."
    )


def _units_on_sheet(sheet: SheetGraph) -> tuple[str, ...]:
    """The units printed by the items on the sheet (references and connectors print none)."""
    units = {str(data["unit_id"]) for _, data in sheet.graph.nodes(data=True) if "unit_id" in data}
    return tuple(sorted(units))


def _rendered_neighbours(sheet: SheetGraph, node_id: str) -> tuple[str, ...]:
    """Tagged 1-hop neighbours, sorted, at most MAX_NEIGHBOURS (untagged connectors are skipped)."""
    graph = sheet.graph
    found: list[str] = []
    for _, target, edge in graph.out_edges(node_id, data=True):
        found += _render_neighbour(graph.nodes[target], edge, outgoing=True)
    for source, _, edge in graph.in_edges(node_id, data=True):
        found += _render_neighbour(graph.nodes[source], edge, outgoing=False)
    return tuple(sorted(found)[:MAX_NEIGHBOURS])


def _render_neighbour(
    neighbour: dict[str, Any], edge: dict[str, Any], *, outgoing: bool
) -> list[str]:
    tag = neighbour.get("tag")
    if not tag:
        return []
    phrase = _relation_phrase(str(edge.get("relation", "linked to")), outgoing)
    line_number = edge.get("line_number")
    detail = phrase if not line_number else f"{phrase}, line {line_number}"
    return [f"{tag} ({detail})"]


def _relation_phrase(relation: str, outgoing: bool) -> str:
    phrases = _RELATION_PHRASES.get(relation)
    if phrases is not None:
        return phrases[0] if outgoing else phrases[1]
    # an unlisted relation (e.g. the related_to fallback) keeps its own name, with the direction
    name = relation.replace("_", " ")
    return name if outgoing else f"{name} (incoming)"
