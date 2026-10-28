"""The data model of the V2T tuning report: one cascade variant, the Cypher tier's accept rule."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.limits import LimitSetting
from plantgraph.qa.cascade.report_models import Cell
from plantgraph.qa.cascade.tune_select import VariantChoice

#: The two secondary cutoffs the design asks for next to the uncut number (design 6, QT-6).
SECONDARY_CUTOFFS_S = (120.0, 300.0)


class VariantResult(BaseModel):
    """One cascade policy under one limit setting, scored against gold."""

    model_config = ConfigDict(frozen=True)

    policy: str
    n_questions: int
    #: Primary: correct answers with no latency limit at all (design R8).
    n_correct_uncut: int
    #: Correct answers within the setting's own limit (A: 120 s; B: the 900 s hang guard).
    n_correct_in_limit: int
    #: Questions slower than the setting's limit: wrong by the setting's rule, hung in B.
    n_beyond_limit: int
    #: Secondary: correct answers within each of `SECONDARY_CUTOFFS_S`, keyed by the seconds.
    n_correct_within: dict[str, int]
    latency_median_s: float
    latency_p90_s: float
    cost_per_question_usd: float
    #: Share of questions whose final answer came from each tier (plus "none").
    tier_shares: dict[str, float]
    #: Family -> correct answers (uncut) out of its questions.
    by_family: dict[str, Cell]


class CypherAcceptance(BaseModel):
    """What the accept rule did to the Cypher tier's answers (cascade_v4, every question tried)."""

    model_config = ConfigDict(frozen=True)

    n_tried: int
    n_accepted: int
    n_accepted_correct: int
    #: Rule value -> answers it rejected first ("answered", "rows", "not_abstained", "complete").
    rejected_by: dict[str, int]
    #: Rejected by `complete` although correct: answers a cut-off check throws away.
    n_cut_but_correct: int


class TuneReport(BaseModel):
    """Everything one tuning round reports for one corpus under one setting."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    setting: LimitSetting
    n_questions: int
    #: Questions either tier answered correctly: the ceiling of any policy on these runs.
    oracle_correct: int
    #: Policy name -> its result; the oracle gap is `oracle_correct - n_correct_uncut`.
    results: dict[str, VariantResult]
    cypher: CypherAcceptance
    #: Set only on the tuning set; `None` elsewhere because the rule is defined on T alone.
    choice: VariantChoice | None


class FamilyChange(BaseModel):
    """One family's correct count in two rounds, for the "revert a drop of 2" stop rule."""

    model_config = ConfigDict(frozen=True)

    family: str
    previous: int
    current: int

    @property
    def delta(self) -> int:
        """Current minus previous correct answers."""
        return self.current - self.previous
