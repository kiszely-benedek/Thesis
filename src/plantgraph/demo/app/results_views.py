"""What `/api/results` returns: the Results tab's views, typed (no number here is typed in)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

#: How a row's confidence interval was made. A single plant's accuracy gets a Wilson interval
#: (a closed-form range that stays inside 0..1); a pooled figure over several plants gets a
#: two-stage cluster bootstrap (resample plants, then questions within them).
IntervalMethod = Literal["wilson", "two-stage bootstrap"]


class Interval(BaseModel):
    """A proportion with its 95 % confidence interval; the row says which method made it."""

    estimate: float
    ci_low: float
    ci_high: float


class Provenance(BaseModel):
    """Which file a view was read from, so the figure's caption can cite it."""

    path: str
    sha256: str
    modified: datetime
    #: The row(s) of the experiment results table that record this run.
    result_row: str


class ClaimLine(BaseModel):
    """One registered claim and its verdict, as the report wrote them."""

    claim_id: str
    #: As written in the report: PASS, FAIL, REPORTED, NOT_RUN, FLAG.
    verdict: str
    text: str


class LadderPoint(BaseModel):
    """One arm (a retrieval strategy) on one corpus size of the scale ladder."""

    corpus_id: str
    n_sheets: int
    arm: str
    n: int
    accuracy: Interval
    cost_mean_usd: float
    latency_median_s: float


class LadderView(BaseModel):
    """The scale ladder: accuracy, cost and latency of each arm as the corpus grows."""

    scope: Literal["common", "all"]
    n_families: int
    cutoff_s: float
    #: The sheet count at which the whole drawing set stops fitting in one prompt.
    wall_sheets: float
    points: tuple[LadderPoint, ...]
    #: Arm/size cells the experiment has no run for (shown, never silently dropped).
    absent: tuple[str, ...]
    #: Empty for a report that predates claim lines.
    claims: tuple[ClaimLine, ...]
    source: Provenance


class SealedRow(BaseModel):
    """One policy on one sealed-test corpus (a single plant, or a pool of plants) and scope."""

    corpus_id: str
    n_sheets: int
    policy: str
    #: The configured label of the source the row came from, e.g. "V2T-A2".
    source_label: str
    #: Which question families the row covers: `headline` or `held-out`.
    scope: str
    n_questions: int
    n_correct: int
    accuracy: Interval
    cost_per_question_usd: float
    latency_median_s: float
    latency_p90_s: float
    pooled: bool
    #: Plants behind a pooled row; `None` for a single plant.
    n_plants: int | None
    interval_method: IntervalMethod


class SealedView(BaseModel):
    """The sealed test: the frozen cascade against single-tier policies and its predecessor."""

    scopes: tuple[str, ...]
    rows: tuple[SealedRow, ...]
    #: The first source's claims; later sources (the F1 baseline) judge another policy.
    claims: tuple[ClaimLine, ...]
    sources: tuple[Provenance, ...]


class InfraRowView(BaseModel):
    """One infrastructure measure at the small and the large plant."""

    name: str
    #: `count`, `s`, `bytes` or `usd`, as configured.
    unit: str
    from_corpus: str
    to_corpus: str
    from_value: float
    to_value: float


class InfraView(BaseModel):
    """What building and running a plant costs as it grows, with the report's self-checks."""

    rows: tuple[InfraRowView, ...]
    #: Every self-check with its status (PASS, FAIL, FLAG); the caption must name the non-PASS ones.
    checks: tuple[ClaimLine, ...]
    machine: str
    source: Provenance


class E2EArm(BaseModel):
    """One end-to-end arm's accuracy, pooled over the plants or on one plant."""

    label: str
    #: `pooled` or the plant's id.
    corpus: str
    n: int
    n_correct: int
    accuracy: Interval
    interval_method: IntervalMethod


class E2EView(BaseModel):
    """Tag identity end to end: the arms' accuracy and the registered claims E1 to E4."""

    arms: tuple[E2EArm, ...]
    claims: tuple[ClaimLine, ...]
    source: Provenance


class ResultsView(BaseModel):
    """The result views; a view is `None` when its report is not configured."""

    ladder: LadderView | None
    sealed: SealedView | None
    infra: InfraView | None = None
    e2e: E2EView | None = None
