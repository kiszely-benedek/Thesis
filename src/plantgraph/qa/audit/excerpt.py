"""The plant excerpt the judge reads: a gold-side subgraph JSON turned into plain text.

The JSON comes from `scripts/audit_export_subgraphs.py`, which cuts it out of the ground-truth
plant graph (the unsplit graph the question generator reads). The JSON is the only hand-over
between the plant and this package, so the audit runs the same way on plants that can no longer
be rebuilt by the current code.

Terms for a reader new to P&IDs (piping and instrumentation diagrams): a *tag* is the short name
printed next to a part, like `P-101` for a pump. A *fitting* (tee, reducer, ...) is a pipe part
that has no tag. The judge must be able to count fittings along a route, so they are shown as
numbered untagged parts, never hidden and never named by an internal id.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: Longest excerpt handed to the judge (review-fixes §5.3).
MAX_EXCERPT_CHARS = 24_000

#: Node properties that are shown through the label already, or are internal bookkeeping.
_HIDDEN_NODE_PROPERTIES = frozenset({"plant_id", "node_class", "tag", "unit_id"})


class ExcerptTooLarge(ValueError):
    """The parts that must be shown (evidence and route) alone exceed the character cap."""


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


class QuestionSubgraph(BaseModel):
    """The plant around one question's gold evidence."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    corpus_id: str
    evidence_ids: list[str]
    nodes: list[SubgraphNode]
    edges: list[SubgraphEdge]


class SubgraphFile(BaseModel):
    """The export script's output: one subgraph per question."""

    model_config = ConfigDict(frozen=True)

    subgraphs: list[QuestionSubgraph]


def render_excerpt(subgraph: QuestionSubgraph, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Text of the subgraph, nearest parts first, cut at `max_chars`.

    Raises:
        ExcerptTooLarge: the distance-0 parts alone do not fit.
    """
    ranked = sorted(subgraph.nodes, key=lambda node: (node.distance, node.id))
    must_keep = sum(1 for node in ranked if node.distance == 0)
    if len(_render_prefix(subgraph, ranked, must_keep)) > max_chars:
        raise ExcerptTooLarge(
            f"expected the evidence and route parts of {subgraph.question_id!r} to fit in "
            f"{max_chars} characters, found {must_keep} parts that do not"
        )
    keep = _largest_fitting_count(subgraph, ranked, must_keep, max_chars)
    return _render_prefix(subgraph, ranked, keep)


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
