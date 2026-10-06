"""The seed map of `hier_agent`: a free, rule-made first guess at the evidence (design §6.1).

Before the model's first reply, the question's anchors (the tags and units it names) are found
and the rule classifier (`need/rules.py`, no model call) picks the evidence shape the question
seems to need ("everything upstream of X up to the first valve", ...). That shape's fixed
program of plant-API primitives (`need/programs.py`) runs, and the items and edges it reached
are written in the same compact format as a tool result. The agent may stop at once or fetch
more. When the rules recognise no shape, the seed is only the items the question names.
"""

from __future__ import annotations

from dataclasses import dataclass

from plantgraph.qa.anchors import Anchors, extract_anchors
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.need.classifiers import NeedClassifier, build_need_input
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.programs import NeedPreconditionError, NeedSelection, run_program
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemRecord
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import edge_line, item_line

#: A program's result is not cut by the API's listing limit; `seed_chars` does the cutting.
_UNCAPPED = 2**62
#: Room kept for the "(N more not shown)" note when the seed is cut.
_NOTICE_ROOM = 90
_HEADER = (
    "Seed map (a rule-based guess made before any tool call; it may be incomplete or off target)."
)


@dataclass(frozen=True)
class Seed:
    """The seed text and what it holds, for the context and the trace."""

    text: str
    #: The need label the rules gave (`GENERIC` when none fits).
    label: str
    #: Why the seed holds only the named items, or `None` when the label's program ran.
    program_skipped: str | None
    #: The primitive calls the program made, as text.
    program: tuple[str, ...]
    #: Occurrence keys of every item and every off-page stub shown in `text`.
    touched_keys: tuple[str, ...]
    n_items_shown: int


@dataclass(frozen=True)
class _Entry:
    """One line of the seed and the occurrence keys it shows."""

    line: str
    keys: tuple[str, ...]
    is_item: bool


def build_seed(
    question_text: str,
    view: GraphView,
    graph: ItemGraph,
    seed_chars: int,
    classifier: NeedClassifier | None = None,
) -> Seed:
    """Find the anchors, run the label's program, and write the result within `seed_chars`."""
    anchors = extract_anchors(question_text, view)
    decision = (classifier or RuleNeedClassifier()).classify(
        build_need_input(question_text, anchors)
    )
    selection, skipped = _run_label(decision.label, anchors, graph)
    named = _named_items(anchors, graph)
    entries = _entries(named, selection)
    head = _head(decision.label, anchors)
    kept = _fit(head, entries, seed_chars)
    text = _write(head, kept, hidden=len(entries) - len(kept))
    return Seed(
        text=text,
        label=decision.label.value,
        program_skipped=skipped,
        program=selection.program,
        touched_keys=tuple(sorted({key for entry in kept for key in entry.keys})),
        n_items_shown=sum(entry.is_item for entry in kept),
    )


def _run_label(
    label: NeedLabel, anchors: Anchors, graph: ItemGraph
) -> tuple[NeedSelection, str | None]:
    """The label's program, or an empty selection and the reason it was not run."""
    nothing = NeedSelection(program=(), items=(), edges=())
    if label is NeedLabel.GENERIC:
        return nothing, "generic"
    if anchors.is_empty:
        return nothing, "no_anchor"
    try:
        return run_program(label, anchors, PlantApi(graph, max_items=_UNCAPPED)), None
    except NeedPreconditionError as error:
        return nothing, f"precondition: {error}"


def _named_items(anchors: Anchors, graph: ItemGraph) -> list[ItemRecord]:
    """The items carrying the tags the question names, in text order, each once."""
    found: dict[str, ItemRecord] = {}
    for tag in anchors.tags:
        for item_id in graph.ids_for_tag(tag.text):
            found.setdefault(item_id, graph.item(item_id))
    return list(found.values())


def _entries(named: list[ItemRecord], selection: NeedSelection) -> list[_Entry]:
    """Named items first, then the program's items nearest first, then its edges."""
    entries = [_item_entry(item, "[named in the question]") for item in named]
    shown = {item.item_id for item in named}
    reached = [s for s in selection.items if s.item.item_id not in shown]
    entries += [_item_entry(s.item, f"[hop {s.distance}]") for s in reached]
    records = {item.item_id: item for item in named}
    records.update({s.item.item_id: s.item for s in selection.items})
    for edge in selection.edges:
        entries.append(_Entry(edge_line(edge, records), edge.via, is_item=False))
    return entries


def _item_entry(item: ItemRecord, note: str) -> _Entry:
    return _Entry(f"{item_line(item)} {note}", item.occurrence_keys, is_item=True)


def _head(label: NeedLabel, anchors: Anchors) -> list[str]:
    head = [_HEADER, f"Question type guessed by the rules: {label.value}."]
    return head + [f"Unit {unit.unit_id} is named in the question." for unit in anchors.units]


def _fit(head: list[str], entries: list[_Entry], seed_chars: int) -> list[_Entry]:
    """The longest prefix of `entries` that, after `head` and a cut note, fits `seed_chars`."""
    used = sum(len(line) + 1 for line in head) + _NOTICE_ROOM
    kept: list[_Entry] = []
    for entry in entries:
        used += len(entry.line) + 1
        if used > seed_chars:
            break
        kept.append(entry)
    return kept


def _write(head: list[str], kept: list[_Entry], hidden: int) -> str:
    lines = list(head)
    if hidden:
        lines.append(f"({hidden} more lines not shown; fetch them with the tools.)")
    elif not kept:
        lines.append("(No item the question names was found in the plant.)")
    lines += [entry.line for entry in kept]
    return "\n".join(lines)
