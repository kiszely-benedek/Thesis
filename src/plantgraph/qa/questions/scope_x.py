"""Scope X (extension) of EXP-0009: the gold side of the five families both V2T arms may be asked.

**Scope R** is EXP-0008's recipe re-run on v2.2 plants; there an untagged valve makes a candidate
refuse (`untagged.py`). **Scope X** adds what only a system that reads valve positions and names
untagged valves can answer (design `v2t-b-system-revision.md` §4):

- OPEN_VALVES_TO_ISOLATE (dev) and `_DOWNSTREAM` (held-out), answered as a VALVE_SET: the isolation
  walk's valves, minus those whose normal position is closed;
- UPSTREAM_ISOLATION_X (dev) and DOWNSTREAM_ISOLATION_X (held-out), VALVE_SET: the isolation walk's
  valves, drawn without the untagged refusal (S5);
- POSITION_OF_VALVE (dev), a POSITION: the position the plan drew for one tagged valve.

The walk is the registered one (first operated valve on every route). A **normal position** says how
a valve stands in ordinary operation (open, closed, car-sealed); the generator plan holds it, the
graph does not, so the builders take the plan's `positions` (`benchmark/v2/valve_positions.py`).

A candidate is **refused**, never reworded, when its answer cannot be written (R3, R8):
an untagged valve has no unique descriptor, or an OPEN_VALVES answer is empty (the answer protocol
cannot tell "close none" from an abstention). Every refusal is recorded, with the valves behind it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, nodes_of_classes, tagged_nodes_by_tag
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.families_heldout_reach import downstream_walk
from plantgraph.qa.questions.families_isolation import upstream_walk
from plantgraph.qa.questions.scope_x_references import (
    NamedValves,
    name_valves,
    require_round_trip,
)
from plantgraph.qa.questions.templates import upstream_isolation_text
from plantgraph.qa.questions.templates_heldout import downstream_isolation_text
from plantgraph.qa.questions.templates_x import (
    open_valves_downstream_text,
    open_valves_upstream_text,
    position_of_valve_text,
)
from plantgraph.qa.questions.untagged import printed_name
from plantgraph.qa.v2tb.descriptor import PlantIndex

_F = QuestionFamily
_TEMPLATE_VERSION = "1"

SCOPE_X_DEV_FAMILIES: tuple[QuestionFamily, ...] = (
    _F.OPEN_VALVES_TO_ISOLATE,
    _F.UPSTREAM_ISOLATION_X,
    _F.POSITION_OF_VALVE,
)
#: Sealed: never generated on a dev plant for tuning (design §6).
SCOPE_X_HELD_OUT_FAMILIES: tuple[QuestionFamily, ...] = (
    _F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM,
    _F.DOWNSTREAM_ISOLATION_X,
)
SCOPE_X_FAMILIES: tuple[QuestionFamily, ...] = (*SCOPE_X_DEV_FAMILIES, *SCOPE_X_HELD_OUT_FAMILIES)

#: The registered family whose need label each X family must receive (R9); POSITION_OF_VALVE has
#: no twin.
SCOPE_X_ROUTING_TWIN: dict[QuestionFamily, QuestionFamily] = {
    _F.OPEN_VALVES_TO_ISOLATE: _F.UPSTREAM_ISOLATION,
    _F.UPSTREAM_ISOLATION_X: _F.UPSTREAM_ISOLATION,
    _F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM: _F.DOWNSTREAM_ISOLATION,
    _F.DOWNSTREAM_ISOLATION_X: _F.DOWNSTREAM_ISOLATION,
}

#: Positions in which a valve is already closed, so an isolation list needs no action on it.
CLOSED_POSITIONS: frozenset[str] = frozenset({"NC", "LC", "CSC"})


class Walk(Protocol):
    """An isolation walk: valves to close, `send_to` edges crossed; `None` if a route has none."""

    def __call__(
        self, plant: nx.DiGraph[str], node_id: str, /
    ) -> tuple[frozenset[str], frozenset[tuple[str, str]]] | None:
        """Walk from `node_id`, as `upstream_walk` and `downstream_walk` do."""
        ...


class RefusalReason(str, Enum):
    """Why a candidate was refused."""

    NO_UNIQUE_DESCRIPTOR = "no_unique_descriptor"
    EMPTY_GOLD = "empty_gold"


class Refusal(BaseModel):
    """One refused candidate: whose question it was, why, and which valves were to blame."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    anchor: str
    reason: RefusalReason
    #: the untagged valves with no unique descriptor (empty for `EMPTY_GOLD`)
    valve_ids: tuple[str, ...] = ()


class QuestionFlags(BaseModel):
    """What the report counts per kept question (design §4, "Reported per X question")."""

    model_config = ConfigDict(frozen=True)

    holds_untagged: bool
    #: OPEN_VALVES only: the gold differs from the topological gold (the discriminating share)
    differs_from_topological: bool | None = None


class FamilyOutcome(BaseModel):
    """One family on one plant: its kept questions, its refusals and the flags of the kept ones."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    candidates: int = Field(ge=0)
    kept: list[Question]
    refusals: list[Refusal]
    flags: dict[str, QuestionFlags]

    @property
    def refused_share(self) -> float:
        """Refused over candidates; 0.0 when there were no candidates."""
        return len(self.refusals) / self.candidates if self.candidates else 0.0


@dataclass(frozen=True)
class _IsolationSpec:
    family: QuestionFamily
    walk: Walk
    text: Callable[[str], str]
    #: True drops the valves whose normal position is closed (the OPEN_VALVES families)
    open_only: bool


_ISOLATION_SPECS = (
    _IsolationSpec(_F.OPEN_VALVES_TO_ISOLATE, upstream_walk, open_valves_upstream_text, True),
    _IsolationSpec(_F.UPSTREAM_ISOLATION_X, upstream_walk, upstream_isolation_text, False),
    _IsolationSpec(
        _F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM, downstream_walk, open_valves_downstream_text, True
    ),
    _IsolationSpec(_F.DOWNSTREAM_ISOLATION_X, downstream_walk, downstream_isolation_text, False),
)


@dataclass(frozen=True)
class _Plant:
    """Everything a builder reads about one plant."""

    graph: nx.DiGraph[str]
    sheet_index: SheetIndex
    plant_index: PlantIndex
    positions: Mapping[str, OperatingPosition]
    corpus_id: str
    seed: int


def scope_x_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    positions: Mapping[str, OperatingPosition],
    *,
    corpus_id: str,
    seed: int,
    families: tuple[QuestionFamily, ...] = SCOPE_X_FAMILIES,
) -> dict[QuestionFamily, FamilyOutcome]:
    """Every scope X family on one plant: kept questions, refusals, flags.

    Args:
        plant: the unsplit gold plant graph.
        manifest: the splitter's answer key for `plant`.
        sheets: the raw sheets `manifest` describes.
        positions: node id -> normal position, `valve_positions.positions_of(plan.unit_plans)`.
        corpus_id: the id every question id starts with.
        seed: recorded in each question as `generator_seed`.
        families: which families to build; sealed ones are asked for only on sealed plants.

    Raises:
        ValueError: a family is not a scope X family, or a position names a node not in the plant.
    """
    unknown = [f for f in families if f not in SCOPE_X_FAMILIES]
    if unknown:
        raise ValueError(
            f"expected scope X families {[f.value for f in SCOPE_X_FAMILIES]}, got {unknown}"
        )
    _require_known_nodes(plant, positions)
    context = _Plant(
        graph=plant,
        sheet_index=SheetIndex.from_sheets(sheets, manifest),
        plant_index=PlantIndex(plant),
        positions=positions,
        corpus_id=corpus_id,
        seed=seed,
    )
    outcomes = {s.family: _isolation_outcome(s, context) for s in _ISOLATION_SPECS}
    outcomes[_F.POSITION_OF_VALVE] = _position_outcome(context)
    return {family: outcomes[family] for family in SCOPE_X_FAMILIES if family in families}


def _require_known_nodes(
    plant: nx.DiGraph[str], positions: Mapping[str, OperatingPosition]
) -> None:
    missing = sorted(node_id for node_id in positions if node_id not in plant)
    if missing:
        raise ValueError(f"expected every positioned valve in the plant, missing {missing[:5]}")


# ---- the four isolation families ----------------------------------------------------------------


def _isolation_outcome(spec: _IsolationSpec, plant: _Plant) -> FamilyOutcome:
    kept: list[Question] = []
    refusals: list[Refusal] = []
    flags: dict[str, QuestionFlags] = {}
    candidates = 0
    for node_id in nodes_of_classes(plant.graph, EQUIPMENT_CLASSES):
        walk = spec.walk(plant.graph, node_id)
        if walk is None:
            continue
        candidates += 1
        tag = printed_name(plant.graph, node_id)
        valves, edges = walk
        gold = _gold_valves(spec, plant, valves)
        named = _name_or_refuse(spec.family, plant, tag, gold)
        if isinstance(named, Refusal):
            refusals.append(named)
            continue
        question = _isolation_question(spec, plant, node_id, tag, edges, named)
        kept.append(question)
        differs = gold != valves if spec.open_only else None
        flags[question.question_id] = QuestionFlags(
            holds_untagged=named.holds_untagged, differs_from_topological=differs
        )
    return FamilyOutcome(
        family=spec.family, candidates=candidates, kept=kept, refusals=refusals, flags=flags
    )


def _gold_valves(spec: _IsolationSpec, plant: _Plant, valves: frozenset[str]) -> frozenset[str]:
    """The walk's valves; for OPEN_VALVES, minus those a position says are already closed."""
    if not spec.open_only:
        return valves
    return frozenset(v for v in valves if plant.positions.get(v) not in CLOSED_POSITIONS)


def _name_or_refuse(
    family: QuestionFamily, plant: _Plant, anchor: str, gold: frozenset[str]
) -> NamedValves | Refusal:
    if not gold:
        return Refusal(family=family, anchor=anchor, reason=RefusalReason.EMPTY_GOLD)
    named = name_valves(plant.plant_index, gold)
    if named.unnameable:
        return Refusal(
            family=family,
            anchor=anchor,
            reason=RefusalReason.NO_UNIQUE_DESCRIPTOR,
            valve_ids=named.unnameable,
        )
    require_round_trip(plant.plant_index, named, gold)
    return named


def _isolation_question(
    spec: _IsolationSpec,
    plant: _Plant,
    node_id: str,
    tag: str,
    edges: frozenset[tuple[str, str]],
    named: NamedValves,
) -> Question:
    nodes = frozenset({node_id, *(n for edge in edges for n in edge)})
    return build_question(
        corpus_id=plant.corpus_id,
        family=spec.family,
        template_id=spec.family.value,
        template_version=_TEMPLATE_VERSION,
        text=spec.text(tag),
        answer_type=AnswerType.VALVE_SET,
        reference=named.reference,
        evidence=Evidence(nodes=nodes, edges=edges),
        anchors=[tag],
        plant=plant.graph,
        index=plant.sheet_index,
        seed=plant.seed,
    )


# ---- POSITION_OF_VALVE --------------------------------------------------------------------------


def _position_outcome(plant: _Plant) -> FamilyOutcome:
    """One candidate per tagged valve the plan gave a position; none is ever refused."""
    kept = [
        _position_question(plant, node_id, tag)
        for node_id, tag in tagged_nodes_by_tag(plant.graph)
        if node_id in plant.positions
    ]
    flags = {q.question_id: QuestionFlags(holds_untagged=False) for q in kept}
    return FamilyOutcome(
        family=_F.POSITION_OF_VALVE, candidates=len(kept), kept=kept, refusals=[], flags=flags
    )


def _position_question(plant: _Plant, node_id: str, tag: str) -> Question:
    return build_question(
        corpus_id=plant.corpus_id,
        family=_F.POSITION_OF_VALVE,
        template_id=_F.POSITION_OF_VALVE.value,
        template_version=_TEMPLATE_VERSION,
        text=position_of_valve_text(tag),
        answer_type=AnswerType.POSITION,
        reference=plant.positions[node_id],
        evidence=Evidence(nodes=frozenset({node_id}), edges=frozenset()),
        anchors=[tag],
        plant=plant.graph,
        index=plant.sheet_index,
        seed=plant.seed,
    )


# ---- the A2 adapter -----------------------------------------------------------------------------


def for_a2(question: Question) -> Question:
    """The same question typed TAG_SET, which is the only list type A2's frozen code knows (§4).

    The reference list is unchanged: a descriptor string simply never matches a tag in A2's
    scorer, so A2 can be right only where the gold holds tagged valves alone.

    Raises:
        ValueError: the question is not a VALVE_SET question (A2 is not asked POSITION_OF_VALVE).
    """
    if question.answer_type is not AnswerType.VALVE_SET:
        raise ValueError(
            f"expected a VALVE_SET question for the A2 adapter, found {question.answer_type.value} "
            f"({question.question_id})"
        )
    return question.model_copy(update={"answer_type": AnswerType.TAG_SET})
