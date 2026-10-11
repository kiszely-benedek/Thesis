"""The data model of the sealed-claims part of the cascade report (tables T1-T4 of the design)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.cascade.evaluate import Comparison, Summary
from plantgraph.qa.cascade.report_models import AcceptanceResult, Cell, Report, Verdict
from plantgraph.qa.cascade.stats import Interval


class ScopeRow(BaseModel):
    """T1: one policy on one corpus over one scope (headline or held-out)."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    scope: str
    policy: str
    #: Summary over the scope's questions only (its `n_questions` is the scope size).
    summary: Summary
    #: acc@C of the scope with a Wilson interval.
    accuracy: Interval
    #: acc@C over every question of the corpus, for comparison with the dev /180 numbers.
    n_all_questions: int
    n_all_correct_at_cutoff: int
    latency_verdicts: list[Verdict]
    #: Tier-1 acceptance on the scope; `None` for one-tier and label-routed policies.
    acceptance: AcceptanceResult | None = None
    #: Percentile-bootstrap intervals of the latency median and p90 (K3 reads them).
    latency_median: Interval
    latency_p90: Interval


class SplitRow(BaseModel):
    """T2: one policy's acc@C on one split of one corpus."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    split: str
    cell: Cell
    accuracy: Interval


class GapRow(BaseModel):
    """T2: generalisation gap, dev splits minus held-out, with an unpaired bootstrap interval."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    dev: Cell
    held_out: Cell
    gap: Interval


class ScaleRow(BaseModel):
    """T3: one policy from the small to the large corpus, over one scope."""

    model_config = ConfigDict(frozen=True)

    scope: str
    policy: str
    small_corpus: str
    large_corpus: str
    sheets_small: int
    sheets_large: int
    accuracy_small: Interval
    accuracy_large: Interval
    #: acc@C large minus small, unpaired bootstrap.
    accuracy_diff: Interval
    cost_per_question_small_usd: float
    cost_per_question_large_usd: float
    elasticity: Interval
    #: Large over small.
    latency_median_ratio: float
    latency_p90_ratio: float


class KBinRow(BaseModel):
    """T3: tier-1 acceptance on the headline questions of one k-bin."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    k_bin: str
    n_questions: int
    n_accepted: int
    n_accepted_correct: int


class PairedRow(BaseModel):
    """K1, K2 or Q5: policy minus reference per question, with bootstrap intervals."""

    model_config = ConfigDict(frozen=True)

    claim: str
    corpus_id: str
    scope: str
    policy: str
    reference: str
    comparison: Comparison


class SealedReport(BaseModel):
    """Everything `--sealed-claims` adds to the report."""

    model_config = ConfigDict(frozen=True)

    #: The claims corpus (last `--corpus`) and the scale pair (first -> last).
    claims_corpus: str
    small_corpus: str
    sheets: dict[str, int]
    #: corpus -> scope -> number of questions; a corpus without `splits.json` has no held-out.
    scope_sizes: dict[str, dict[str, int]]
    scope_rows: list[ScopeRow]
    split_rows: list[SplitRow] = Field(default_factory=list)
    gap_rows: list[GapRow] = Field(default_factory=list)
    scale_rows: list[ScaleRow]
    k_bin_rows: list[KBinRow]
    paired_rows: list[PairedRow]
    claims: list[Verdict]
    notes: list[str] = Field(default_factory=list)


class SealedClaimsReport(Report):
    """The cascade report under `--sealed-claims`: the usual corpus tables plus the sealed part."""

    sealed: SealedReport
