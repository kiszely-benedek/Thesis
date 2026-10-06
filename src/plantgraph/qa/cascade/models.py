"""The cascade's data model: tiers, policies, the gold-free `Signals`, and `Decision`."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.models import Outcome
from plantgraph.qa.need.labels import NeedLabel


class AcceptRule(str, Enum):
    """One condition a tier's answer must meet to be accepted (all listed rules must hold)."""

    #: The outcome is ANSWERED, so no parse failure, runaway or retrieval error.
    ANSWERED = "answered"
    #: The Cypher query returned at least one row (Cypher tiers only).
    ROWS = "rows"
    #: The final answer does not say "not present in the diagram".
    NOT_ABSTAINED = "not_abstained"


class TierSpec(BaseModel):
    """One tier: which strategy, under which model pin, and when its answer is accepted."""

    model_config = ConfigDict(frozen=True)

    #: Short name used in decisions and file paths, e.g. "cypher-low", "need-default".
    name: str
    #: Registry name of the strategy whose rows this tier reads.
    strategy: str
    #: `ModelPin.pin_hash()` of the run's answer pin; the join checks the run against it.
    pin_sha256: str
    accept: frozenset[AcceptRule]


class CascadePolicy(BaseModel):
    """An ordered list of tiers; the first tier whose answer is accepted settles the question."""

    model_config = ConfigDict(frozen=True)

    name: str
    tiers: tuple[TierSpec, ...]
    #: When no tier is accepted, the first tier's answer (if it was ANSWERED) is the result.
    fallback_to_first_answer: bool = True
    #: Variants only: skip the tiers before this index for a question with this need label.
    start_tier_by_label: dict[NeedLabel, int] = Field(default_factory=dict)


class Signals(BaseModel):
    """Everything a policy may read about one tier's answer; no gold field by construction."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    tier: str
    outcome: Outcome
    #: Rows the Cypher query returned; `None` for a tier that runs no query.
    n_rows: int | None
    #: The answer abstains; `None` when the tier produced no final answer.
    not_present: bool | None
    #: The answer ran away: a parse failure, or the output hit the pin's token cap.
    runaway: bool
    #: Final call plus retrieval-side calls (query writing, unit router).
    cost_usd: float
    latency_s: float
    #: Rules need label; `None` when no run recorded one and no anchor finder was given.
    need_label: NeedLabel | None


class Decision(BaseModel):
    """What a policy decided for one question; the input of the evaluation."""

    model_config = ConfigDict(frozen=True)

    policy: str
    question_id: str
    tiers_tried: tuple[str, ...]
    #: Tier whose answer is final; `None` when the question fails.
    answered_by: str | None
    cost_usd: float
    latency_s: float
