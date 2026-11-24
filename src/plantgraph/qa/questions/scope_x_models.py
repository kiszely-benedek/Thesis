"""The typed pieces the scope X builders share: refusals, per-question flags, family outcomes.

They live apart from `scope_x.py` so the isolation builders and the POSITION_OF_VALVE builder
(`scope_x_position.py`) can both use them without importing each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.evidence import SheetIndex
from plantgraph.qa.v2tb.descriptor import PlantIndex

TEMPLATE_VERSION = "1"


class RefusalReason(str, Enum):
    """Why a candidate was refused."""

    NO_UNIQUE_DESCRIPTOR = "no_unique_descriptor"
    EMPTY_GOLD = "empty_gold"


class NamedBy(str, Enum):
    """How a POSITION_OF_VALVE question names its valve (design `v2t-b` §10 R11)."""

    TAG = "tag"
    DESCRIPTOR = "descriptor"


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
    #: POSITION_OF_VALVE only: whether the text names the valve by its tag or by a descriptor
    named_by: NamedBy | None = None


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
class XPlant:
    """Everything a scope X builder reads about one plant."""

    graph: nx.DiGraph[str]
    sheet_index: SheetIndex
    plant_index: PlantIndex
    positions: Mapping[str, OperatingPosition]
    corpus_id: str
    seed: int
