"""Independent cross-check of the scope X gold answers of EXP-0009 (a validation tool).

The stored gold of the five scope X families is computed once: `qa/questions/scope_x*.py` walks the
generator's plant and reads the plan's positions. This module recomputes every answer from the **B
view of the built corpus** instead: the occurrence graph the system sees, with `operating_position`
read from the DEXPI file. The walk and the valve naming are written from the definitions
(`gold_crosscheck_walks.py`), and the view is folded back into one flow graph
(`gold_crosscheck_graph.py`). The comparison is valve set against valve set, never string against
string: each stored reference item is resolved with this module's own resolver.

Two checks per plant:

1. **Answers** - for every stored X question, my gold equals the stored reference (POSITION: the
   code in the view equals the reference code).
2. **Candidates** (when the builder's outcomes are at hand) - which candidates are kept and which
   are refused is the same, so no question was silently lost or invented.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0009.gold_crosscheck_graph import FlowGraph, fold_class, fold_line, fold_tag
from plantgraph.qa.exp0009.gold_crosscheck_walks import (
    CLOSED_POSITIONS,
    EQUIPMENT_CLASSES,
    Descriptor,
    Namer,
    isolation_valves,
)
from plantgraph.qa.models import Question, QuestionFamily

_F = QuestionFamily
#: family -> (walks upstream, keeps only the valves that are not already closed)
ISOLATION_FAMILIES: dict[QuestionFamily, tuple[bool, bool]] = {
    _F.OPEN_VALVES_TO_ISOLATE: (True, True),
    _F.UPSTREAM_ISOLATION_X: (True, False),
    _F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM: (False, True),
    _F.DOWNSTREAM_ISOLATION_X: (False, False),
}
X_FAMILIES: tuple[QuestionFamily, ...] = (*ISOLATION_FAMILIES, _F.POSITION_OF_VALVE)
NO_POSITION = "(no position in the view)"


class Disagreement(BaseModel):
    """One stored question whose reference differs from the recomputed answer."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: QuestionFamily
    mine: list[str]
    stored: list[str]
    only_mine: list[str]
    only_stored: list[str]
    note: str


class FamilyTally(BaseModel):
    """Answers compared in one family."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    total: int
    agree: int
    disagree: int


class CandidateTally(BaseModel):
    """Candidate and kept counts of one family, mine against the builder's."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    mine_candidates: int
    stored_candidates: int
    mine_kept: int
    stored_kept: int
    only_mine_kept: list[str]
    only_stored_kept: list[str]


class PlantCheck(BaseModel):
    """The cross-check of one plant."""

    model_config = ConfigDict(frozen=True)

    plant_id: str
    tagging: str
    tallies: list[FamilyTally]
    disagreements: list[Disagreement]
    candidates: list[CandidateTally]
    seconds: float


class CrossChecker:
    """Recomputes scope X gold on one flow graph; `roles` (node -> role) only annotates reports."""

    def __init__(self, graph: FlowGraph, roles: Mapping[str, str] | None = None) -> None:
        self.graph = graph
        self.namer = Namer(graph)
        self._roles = roles or {}

    # ---- naming a valve in a report ----

    def label(self, node: str) -> str:
        """`tag-or-untagged, class, node key, role` of a valve, for a disagreement record."""
        tag = self.graph.tags.get(node, "untagged")
        keys = self.graph.occurrences[node]
        role = next((self._roles[k] for k in keys if k in self._roles), "role unknown")
        return f"{tag} | {self.graph.classes[node]} | {node} | {role}"

    # ---- one stored question ----

    def check(self, question: Question) -> Disagreement | None:
        """`None` when the recomputed answer equals the stored one, else the record of the gap."""
        if question.family in ISOLATION_FAMILIES:
            return self._check_isolation(question)
        if question.family is _F.POSITION_OF_VALVE:
            return self._check_position(question)
        raise ValueError(f"expected a scope X family, found {question.family.value}")

    def _check_isolation(self, question: Question) -> Disagreement | None:
        mine, problem = self._my_isolation_gold(question)
        stored, unresolved = self._resolve_reference(question)
        notes = [n for n in (problem, *unresolved) if n]
        if mine is not None and mine == stored and not notes:
            return None
        return self._record(question, mine or frozenset(), stored, notes)

    def _my_isolation_gold(self, question: Question) -> tuple[frozenset[str] | None, str]:
        """My gold valves for the question, or `None` and why there are none."""
        upstream, open_only = ISOLATION_FAMILIES[question.family]
        starts = self.equipment_with_tag(question.anchors[0])
        if len(starts) != 1:
            return None, f"anchor {question.anchors[0]!r} names {len(starts)} equipment items"
        valves = isolation_valves(self.graph, next(iter(starts)), upstream=upstream)
        if valves is None:
            return None, "my walk finds a route with no operated valve: not a candidate"
        return self.open_only(valves) if open_only else valves, ""

    def open_only(self, valves: Iterable[str]) -> frozenset[str]:
        """The valves whose normal position is not closed (a valve with no position is open)."""
        return frozenset(v for v in valves if self.graph.positions.get(v) not in CLOSED_POSITIONS)

    def equipment_with_tag(self, tag: str) -> frozenset[str]:
        """The equipment nodes that print this tag (one node per physical item)."""
        tagged = self.graph.nodes_with_tag(fold_tag(tag))
        return frozenset(n for n in tagged if self.graph.classes[n] in EQUIPMENT_CLASSES)

    def _resolve_reference(self, question: Question) -> tuple[frozenset[str], list[str]]:
        """The valves the stored reference names, and a note per item that is not exactly one."""
        reference = question.reference
        if not isinstance(reference, list):
            raise ValueError(f"expected a list reference, found {reference!r}")
        nodes: set[str] = set()
        notes: list[str] = []
        for item in reference:
            found = self.namer.resolve_item(str(item))
            if len(found) != 1:
                notes.append(f"stored item {item!r} resolves to {len(found)} valves")
            nodes |= found
        return frozenset(nodes), notes

    def _record(
        self, question: Question, mine: frozenset[str], stored: frozenset[str], notes: list[str]
    ) -> Disagreement:
        return Disagreement(
            question_id=question.question_id,
            family=question.family,
            mine=sorted(self.label(n) for n in mine),
            stored=sorted(self.label(n) for n in stored),
            only_mine=sorted(self.label(n) for n in mine - stored),
            only_stored=sorted(self.label(n) for n in stored - mine),
            note="; ".join(notes),
        )

    # ---- POSITION_OF_VALVE ----

    def position_valve(self, question: Question) -> frozenset[str]:
        """The valves a POSITION question names: by its tag, or by the descriptor in its id."""
        name = question.question_id.partition(f":{question.family.value}:")[2]
        parts = name.split("|")
        if len(parts) == 4:  # descriptor form: next_to | side | class | line (`scope_x_position`)
            next_to, side, class_name, line = parts
            return self.namer.resolve(
                Descriptor(fold_class(class_name), fold_line(line), fold_tag(next_to), side)
            )
        return self.namer.resolve_item(question.anchors[0])

    def _check_position(self, question: Question) -> Disagreement | None:
        valves = self.position_valve(question)
        if len(valves) != 1:
            return self._record(question, frozenset(), frozenset(), [f"names {len(valves)} valves"])
        mine = self.graph.positions.get(next(iter(valves)), NO_POSITION)
        if mine == str(question.reference):
            return None
        note = f"view says {mine}, stored reference says {question.reference}"
        return self._record(question, valves, valves, [note])

    # ---- candidate sets (what was kept, what was refused) ----

    def my_isolation_kept(self, family: QuestionFamily) -> tuple[int, set[str]]:
        """My candidates and kept anchors (folded tags) for one isolation family."""
        upstream, open_only = ISOLATION_FAMILIES[family]
        candidates, kept = 0, set()
        for node, class_name in self.graph.classes.items():
            if class_name not in EQUIPMENT_CLASSES or node not in self.graph.tags:
                continue
            valves = isolation_valves(self.graph, node, upstream=upstream)
            if valves is None:
                continue
            candidates += 1
            gold = self.open_only(valves) if open_only else valves
            if gold and self._all_nameable(gold):
                kept.add(self.graph.tags[node])
        return candidates, kept

    def _all_nameable(self, valves: Iterable[str]) -> bool:
        return all(v in self.graph.tags or self.namer.is_nameable(v) for v in valves)

    def my_position_kept(self) -> tuple[int, set[str]]:
        """My candidates (positioned valves) and the kept ones, as node keys."""
        positioned = self.graph.positions
        kept = {v for v in positioned if v in self.graph.tags or self.namer.is_nameable(v)}
        return len(positioned), kept


def tally(
    questions: Sequence[Question], checker: CrossChecker
) -> tuple[list[FamilyTally], list[Disagreement]]:
    """Check every question; count per family and keep the records of the gaps."""
    gaps = [(q, checker.check(q)) for q in questions]
    disagreements = [gap for _, gap in gaps if gap is not None]
    total = Counter(q.family for q, _ in gaps)
    wrong = Counter(q.family for q, gap in gaps if gap is not None)
    tallies = [
        FamilyTally(family=f, total=total[f], agree=total[f] - wrong[f], disagree=wrong[f])
        for f in X_FAMILIES
    ]
    return tallies, disagreements


def candidate_tallies(
    checker: CrossChecker, stored: Mapping[QuestionFamily, tuple[int, list[Question]]]
) -> list[CandidateTally]:
    """Compare my kept sets with the builder's `(candidates, kept questions)` per family."""
    rows = []
    for family, (stored_candidates, kept_questions) in stored.items():
        if family is _F.POSITION_OF_VALVE:
            mine_n, mine_kept = checker.my_position_kept()
            stored_kept = {n for q in kept_questions for n in checker.position_valve(q)}
        else:
            mine_n, mine_kept = checker.my_isolation_kept(family)
            stored_kept = {fold_tag(q.anchors[0]) for q in kept_questions}
        rows.append(
            CandidateTally(
                family=family,
                mine_candidates=mine_n,
                stored_candidates=stored_candidates,
                mine_kept=len(mine_kept),
                stored_kept=len(stored_kept),
                only_mine_kept=sorted(mine_kept - stored_kept),
                only_stored_kept=sorted(stored_kept - mine_kept),
            )
        )
    return rows
