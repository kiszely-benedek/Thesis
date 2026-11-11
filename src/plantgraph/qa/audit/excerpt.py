"""The plant excerpt the judge reads: a gold-side subgraph JSON turned into plain text.

The JSON comes from `scripts/audit_export_subgraphs.py`, which cuts it out of the ground-truth
plant graph (the unsplit graph the question generator reads). The JSON is the only hand-over
between the plant and this package, so the audit runs the same way on plants that can no longer
be rebuilt by the current code.

Terms for a reader new to P&IDs (piping and instrumentation diagrams): a *tag* is the short name
printed next to a part, like `P-101` for a pump. A *fitting* (tee, reducer, ...) is a pipe part
that has no tag. The judge must be able to count fittings along a route, so they are shown as
numbered untagged parts, never hidden and never named by an internal id.

A question that counts along a route between two parts carries that route (`routes`), written
out part by part before the rest. Such a route can run through hundreds of parts, more than the
excerpt can show with all their connections, and the judge cannot count what it cannot follow.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: Longest excerpt handed to the judge (review-fixes §5.3).
MAX_EXCERPT_CHARS = 24_000

#: Node properties that are shown through the label already, or are internal bookkeeping.
_HIDDEN_NODE_PROPERTIES = frozenset({"plant_id", "node_class", "tag", "unit_id"})


class ExcerptTooLarge(ValueError):
    """What must be shown (the routes, or else the evidence parts) alone exceeds the cap."""


class SubgraphNode(BaseModel):
    """One part of the plant, as exported."""

    model_config = ConfigDict(frozen=True)

    id: str
    node_class: str
    #: The printed tag; `None` for a fitting or an untagged actuator.
    tag: str | None = None
    unit_id: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)
    #: 0 for evidence and for parts on a route between evidence; else hops to the nearest of those.
    distance: int = Field(ge=0)


class SubgraphEdge(BaseModel):
    """One directed connection between two exported parts."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relation: str
    properties: dict[str, str] = Field(default_factory=dict)


class SubgraphRoute(BaseModel):
    """One route between the two parts a count question names, in flow order."""

    model_config = ConfigDict(frozen=True)

    #: Which reading of "between" this route answers, in words the judge reads.
    basis: str
    node_ids: list[str] = Field(min_length=2)


class QuestionSubgraph(BaseModel):
    """The plant around one question's gold evidence."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    corpus_id: str
    evidence_ids: list[str]
    nodes: list[SubgraphNode]
    edges: list[SubgraphEdge]
    #: Empty unless the question counts along a route; every route node is also in `nodes`.
    routes: list[SubgraphRoute] = Field(default_factory=list)


class SubgraphFile(BaseModel):
    """The export script's output: one subgraph per question."""

    model_config = ConfigDict(frozen=True)

    subgraphs: list[QuestionSubgraph]


def render_excerpt(subgraph: QuestionSubgraph, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Text of the subgraph, nearest parts first, cut at `max_chars`.

    Without routes, the evidence parts (distance 0) must all be shown. With routes, the routes
    must all be shown and the parts and connections fill what room is left.

    Raises:
        ExcerptTooLarge: what must be shown does not fit.
    """
    ranked = sorted(subgraph.nodes, key=lambda node: (node.distance, node.id))
    routes_text = _render_routes(subgraph, _labels(ranked))
    room = max_chars - len(routes_text)
    must_keep = 0 if subgraph.routes else sum(1 for node in ranked if node.distance == 0)
    if len(_render_prefix(subgraph, ranked, must_keep)) > room:
        raise ExcerptTooLarge(
            f"expected the routes and evidence parts of {subgraph.question_id!r} to fit in "
            f"{max_chars} characters, found {len(subgraph.routes)} routes and {must_keep} "
            "parts that do not"
        )
    keep = _largest_fitting_count(subgraph, ranked, must_keep, room)
    return routes_text + _render_prefix(subgraph, ranked, keep)


def _render_routes(subgraph: QuestionSubgraph, labels: dict[str, str]) -> str:
    """The routes, one tagged part a line under its process unit; empty when there is none.

    Untagged fittings are left out: nothing asks for them, and a route is half fittings. The
    unit headings break a route of a hundred parts into runs short enough to count.
    """
    if not subgraph.routes:
        return ""
    by_id = {node.id: node for node in subgraph.nodes}
    first = subgraph.routes[0].node_ids
    lines = [
        f"Routes from {labels[first[0]]} to {labels[first[-1]]}, found by following the "
        "connections in flow direction. Each route lists its tagged parts in order, both ends "
        "included; the untagged pipe fittings between them are left out.",
    ]
    for number, route in enumerate(subgraph.routes, start=1):
        steps = [by_id[node_id] for node_id in route.node_ids if by_id[node_id].tag is not None]
        lines += ["", f"Route {number}: {route.basis} ({len(steps)} tagged parts):"]
        lines += _route_step_lines(steps)
    return "\n".join(lines) + "\n\n"


def _route_step_lines(steps: list[SubgraphNode]) -> list[str]:
    """Numbered parts of one route, with a heading line wherever the process unit changes."""
    lines: list[str] = []
    unit: str | None = None
    for number, node in enumerate(steps, start=1):
        if number == 1 or node.unit_id != unit:
            unit = node.unit_id
            lines.append(f"in unit {unit}:" if unit is not None else "in no unit:")
        lines.append(f"{number}. {node.tag} [{node.node_class}]")
    return lines


def _largest_fitting_count(
    subgraph: QuestionSubgraph, ranked: list[SubgraphNode], low: int, max_chars: int
) -> int:
    """Binary search: more parts means a longer text, so the largest fitting count is found fast."""
    high = len(ranked)
    while low < high:
        middle = (low + high + 1) // 2
        if len(_render_prefix(subgraph, ranked, middle)) <= max_chars:
            low = middle
        else:
            high = middle - 1
    return low


def _render_prefix(subgraph: QuestionSubgraph, ranked: list[SubgraphNode], count: int) -> str:
    kept = ranked[:count]
    labels = _labels(kept)
    evidence = set(subgraph.evidence_ids)
    part_lines = [_part_line(node, labels[node.id], node.id in evidence) for node in kept]
    edge_lines = [
        _edge_line(edge, labels)
        for edge in subgraph.edges
        if {edge.source, edge.target} <= labels.keys()
    ]
    omitted = len(ranked) - count
    lines = ["Parts (* marks the parts the benchmark names as evidence):", *part_lines]
    lines += ["", "Connections (from -> to):", *sorted(edge_lines)]
    if omitted:
        lines += ["", f"[{omitted} more distant parts left out to keep the excerpt short]"]
    return "\n".join(lines)


def _labels(nodes: list[SubgraphNode]) -> dict[str, str]:
    """Tag for a tagged part; `(untagged Class #n)` for the rest, numbered per class."""
    labels: dict[str, str] = {}
    counts: dict[str, int] = {}
    for node in nodes:
        if node.tag is not None:
            labels[node.id] = node.tag
            continue
        counts[node.node_class] = counts.get(node.node_class, 0) + 1
        labels[node.id] = f"(untagged {node.node_class} #{counts[node.node_class]})"
    return labels


def _part_line(node: SubgraphNode, label: str, is_evidence: bool) -> str:
    unit = f", unit {node.unit_id}" if node.unit_id is not None else ""
    extras = "".join(
        f"; {name}={value}"
        for name, value in sorted(node.properties.items())
        if name not in _HIDDEN_NODE_PROPERTIES
    )
    return f"{'*' if is_evidence else '-'} {label} [{node.node_class}{unit}{extras}]"


def _edge_line(edge: SubgraphEdge, labels: dict[str, str]) -> str:
    details = "".join(f"; {name}={value}" for name, value in sorted(edge.properties.items()))
    return f"{labels[edge.source]} -> {labels[edge.target]} [{edge.relation}{details}]"
