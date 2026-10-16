"""The route of an ask as a graph the page can step through (data half; the SVG is `route.js`).

A node is a plant item the model saw (in a step of its trace), the question names, or the answer
names. An edge is a **direct** connection between two shown items on the drawings; no path is
searched, so the picture never claims a route the model did not take. For a `TAG_PATH` answer,
two consecutive answer items with no direct connection get a "gap" edge, which checks the answer
against the drawings without inventing a link.

Pure functions over `ItemGraph` and `AskTrace`: no I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.demo.app.evidence import items_in_text, read_sheet_links
from plantgraph.demo.app.models import SheetLink
from plantgraph.demo.app.trace_models import AgentStep, AskTrace, CypherStep
from plantgraph.graph.schema import CLASS_SPECS, NodeCategory
from plantgraph.qa.cascade.live_models import LiveAnswer
from plantgraph.qa.models import AnswerType
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord, sheet_of_key

NodeFamily = Literal["equipment", "valve", "instrument", "other"]
EdgeRelation = Literal["send_to", "send_signal_to", "control", "measured_by", "none"]

#: Caps that keep the picture readable (answer items are kept first, then the earliest steps).
MAX_NODES = 150
MAX_EDGES = 300
#: Longest step label; the full arguments stay in the step list of the details.
_LABEL_CHARS = 60

#: Answer types whose answer is made of tags or free text that may name items.
_ITEM_ANSWERS = (AnswerType.TAG, AnswerType.TAG_SET, AnswerType.TAG_PATH, AnswerType.FREE_TEXT)

_INSTRUMENT_CLASSES = frozenset(
    node_class.value
    for node_class, spec in CLASS_SPECS.items()
    if spec.category is NodeCategory.INSTRUMENTATION
)


class RouteNode(BaseModel):
    """One plant item in the route picture."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    tag: str | None
    node_class: str
    family: NodeFamily
    unit_id: str | None
    sheets: tuple[SheetLink, ...]
    #: 0-based index into `RouteView.steps` of the step that first showed it to the model;
    #: `None` when it appears only in the question or the answer.
    first_step: int | None
    in_answer: bool
    in_question: bool


class RouteEdge(BaseModel):
    """A direct connection between two shown items, or a gap in an answer path."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    #: `none` marks a path gap: no direct connection on the drawings.
    relation: EdgeRelation
    #: Sheets of the off-page connectors the edge passes through (empty on one sheet).
    crossed_sheets: tuple[str, ...]
    on_answer_path: bool


class RouteView(BaseModel):
    """What the page needs to draw and step through the route."""

    model_config = ConfigDict(frozen=True)

    #: One short label per step, for the slider: Cypher steps first, then agent tool calls.
    steps: tuple[str, ...]
    nodes: tuple[RouteNode, ...]
    edges: tuple[RouteEdge, ...]
    #: Item ids in answer order for a `TAG_PATH` answer, else empty.
    answer_path: tuple[str, ...]
    #: Items left out by the node cap.
    omitted_nodes: int


def route_view(
    question_text: str,
    live: LiveAnswer,
    trace: AskTrace,
    item_graph: ItemGraph,
    pages: Mapping[str, int],
) -> RouteView | None:
    """The route picture of one ask; `None` when no plant item is named anywhere.

    Raises:
        ValueError: a sheet of a shown item is missing from `pages`.
    """
    steps, step_items = _steps(trace, item_graph)
    in_question = _ids_of_texts([question_text], item_graph)
    path = _answer_path(live, item_graph)
    in_answer = _answer_ids(live, item_graph) if not path else list(dict.fromkeys(path))
    ordered = _ordered_ids(step_items, in_question, in_answer)
    if not ordered:
        return None
    kept = _kept_ids(ordered, set(in_answer))
    first_step = _first_steps(step_items)
    nodes = tuple(
        _node(i, item_graph, pages, first_step.get(i), i in in_answer, i in in_question)
        for i in kept
    )
    edges = _edges(kept, path, item_graph)
    return RouteView(
        steps=steps,
        nodes=nodes,
        edges=edges,
        answer_path=tuple(path),
        omitted_nodes=len(ordered) - len(kept),
    )


# --- steps and the items each one showed --------------------------------------


def _steps(trace: AskTrace, item_graph: ItemGraph) -> tuple[tuple[str, ...], list[list[str]]]:
    """Step labels and, per step, the item ids it showed: Cypher steps first, then agent steps."""
    labels: list[str] = []
    items: list[list[str]] = []
    for query in trace.cypher:
        rows = _rows_text(query)
        labels.append(f"Cypher query: {len(query.rows)} rows")
        items.append(_ids_of_texts([rows], item_graph))
    for call in trace.agent:
        labels.append(_agent_label(call))
        items.append(_resolve_all(call.items, item_graph))
    return tuple(labels), items


def _rows_text(query: CypherStep) -> str:
    """The text to find items in: the rows as JSON, or the whole context if they did not parse."""
    if query.rows:
        return json.dumps(list(query.rows), default=str)
    return "" if query.parsed else query.context


def _agent_label(call: AgentStep) -> str:
    if not call.tool:
        return f"unreadable reply {call.index}"
    args = ", ".join(f"{key}: {value}" for key, value in call.args.items())
    label = f"{call.tool} {{{args}}}"
    return label if len(label) <= _LABEL_CHARS else label[: _LABEL_CHARS - 3] + "..."


def _first_steps(step_items: Sequence[Sequence[str]]) -> dict[str, int]:
    first: dict[str, int] = {}
    for index, ids in enumerate(step_items):
        for item_id in ids:
            first.setdefault(item_id, index)
    return first


# --- naming items: question, answer, steps ------------------------------------


def _resolve(name: str, item_graph: ItemGraph) -> list[str]:
    """Item ids a name stands for: an item id itself, else every item with that tag."""
    if item_graph.has_item(name):
        return [name]
    return item_graph.ids_for_tag(name)


def _resolve_all(names: Iterable[str], item_graph: ItemGraph) -> list[str]:
    found = [item_id for name in names for item_id in _resolve(name, item_graph)]
    return list(dict.fromkeys(found))


def _ids_of_texts(texts: Iterable[str], item_graph: ItemGraph) -> list[str]:
    """Ids of the items named in free text."""
    names = [name for text in texts for name in items_in_text(text, item_graph)]
    return _resolve_all(names, item_graph)


def _answer_texts(live: LiveAnswer) -> list[str]:
    """The answer's parts as text; empty for answer types that cannot name an item."""
    answer = live.final_answer
    if answer is None or live.answer_type not in _ITEM_ANSWERS:
        return []
    value: Any = answer.answer
    if isinstance(value, list):
        return [str(part) for part in value]
    return [] if value is None else [str(value)]


def _answer_ids(live: LiveAnswer, item_graph: ItemGraph) -> list[str]:
    """Ids of the items the answer names (a whole part first as a tag, else words inside it)."""
    found: list[str] = []
    for text in _answer_texts(live):
        found += _resolve(text.strip(), item_graph) or _ids_of_texts([text], item_graph)
    return list(dict.fromkeys(found))


def _answer_path(live: LiveAnswer, item_graph: ItemGraph) -> list[str]:
    """One item id per `TAG_PATH` answer entry, in order; entries naming no item are skipped."""
    if live.answer_type is not AnswerType.TAG_PATH:
        return []
    path: list[str] = []
    for text in _answer_texts(live):
        ids = _resolve(text.strip(), item_graph)
        if ids:
            path.append(ids[0])  # a tag shared by several items: the first by sort order
    return path


# --- which nodes, in which order ----------------------------------------------


def _ordered_ids(
    step_items: Sequence[Sequence[str]], in_question: Sequence[str], in_answer: Sequence[str]
) -> list[str]:
    """Question-only items, then each step's items, then answer-only items; no repeats."""
    seen_in_steps = {item_id for ids in step_items for item_id in ids}
    question_first = [i for i in in_question if i not in seen_in_steps]
    in_steps = [item_id for ids in step_items for item_id in ids]
    answer_last = [i for i in in_answer if i not in seen_in_steps and i not in question_first]
    return list(dict.fromkeys(question_first + in_steps + answer_last))


def _kept_ids(ordered: list[str], in_answer: set[str]) -> list[str]:
    """Apply the node cap: answer items first, then the earliest others; original order kept."""
    if len(ordered) <= MAX_NODES:
        return ordered
    answer_items = [i for i in ordered if i in in_answer][:MAX_NODES]
    room = MAX_NODES - len(answer_items)
    others = [i for i in ordered if i not in in_answer][:room]
    keep = set(answer_items) | set(others)
    return [i for i in ordered if i in keep]


def _node(
    item_id: str,
    item_graph: ItemGraph,
    pages: Mapping[str, int],
    first_step: int | None,
    in_answer: bool,
    in_question: bool,
) -> RouteNode:
    record = item_graph.item(item_id)
    return RouteNode(
        item_id=item_id,
        tag=record.tag,
        node_class=record.node_class,
        family=_family(record),
        unit_id=record.unit_id,
        sheets=read_sheet_links(record.sheets, pages),
        first_step=first_step,
        in_answer=in_answer,
        in_question=in_question,
    )


def _family(record: ItemRecord) -> NodeFamily:
    if "Equipment" in record.labels:
        return "equipment"
    if any(label.endswith("Valve") for label in record.labels):
        return "valve"
    if record.node_class in _INSTRUMENT_CLASSES:
        return "instrument"
    return "other"


# --- edges ----------------------------------------------------------------------


def _edges(
    kept: Sequence[str], path: Sequence[str], item_graph: ItemGraph
) -> tuple[RouteEdge, ...]:
    """Direct edges among the kept items, then path gaps; answer-path edges survive the cap."""
    shown = set(kept)
    hops = {frozenset(pair) for pair in zip(path, path[1:], strict=False) if pair[0] != pair[1]}
    direct = [
        _route_edge(neighbour_edge, hops)
        for item_id in kept
        for neighbour, neighbour_edge in item_graph.steps(item_id, "downstream", "any")
        if neighbour in shown
    ]
    joined = {frozenset((e.source, e.target)) for e in direct}
    gaps = [
        _gap(a, b) for a, b in zip(path, path[1:], strict=False) if _is_gap(a, b, joined, shown)
    ]
    on_path = [e for e in direct if e.on_answer_path] + gaps
    others = [e for e in direct if not e.on_answer_path]
    return tuple((on_path + others)[:MAX_EDGES])


def _route_edge(edge: ItemEdge, hops: set[frozenset[str]]) -> RouteEdge:
    return RouteEdge(
        source=edge.source,
        target=edge.target,
        relation=edge.relation,
        crossed_sheets=_crossed_sheets(edge),
        on_answer_path=frozenset((edge.source, edge.target)) in hops,
    )


def _crossed_sheets(edge: ItemEdge) -> tuple[str, ...]:
    """Sheets of the off-page stubs on the edge (`via` keys read `<sheet>:<id>`), no repeats."""
    return tuple(dict.fromkeys(sheet_of_key(key) for key in edge.via))


def _is_gap(a: str, b: str, joined: set[frozenset[str]], shown: set[str]) -> bool:
    return a != b and a in shown and b in shown and frozenset((a, b)) not in joined


def _gap(source: str, target: str) -> RouteEdge:
    return RouteEdge(
        source=source, target=target, relation="none", crossed_sheets=(), on_answer_path=True
    )
