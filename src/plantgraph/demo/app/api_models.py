"""The request and response types of the demo's HTTP API (what the page sends and receives)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from plantgraph.demo.app.models import CostEstimate, SheetLink, SpendStatus
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.models import AnswerType, AnswerValue, Outcome, QuestionFamily


class AskRequest(BaseModel):
    """One question to answer: typed text, or the id of a benchmark question."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    text: str = ""
    answer_type: AnswerType = AnswerType.FREE_TEXT
    #: When set, the benchmark question's own text and answer type are used.
    benchmark_question_id: str | None = None
    #: The user's confirmation that this question may spend money (needs the server flag too).
    allow_paid: bool = False
    #: Skip tier 1 even if the store holds the corpus.
    tier2_only: bool = False

    @model_validator(mode="after")
    def _needs_a_question(self) -> AskRequest:
        if not self.text.strip() and self.benchmark_question_id is None:
            raise ValueError("expected a question text or a benchmark_question_id, found neither")
        return self


class QuestionSummary(BaseModel):
    """One line of the benchmark picker: no reference answer, no gold evidence."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: QuestionFamily
    text: str
    answer_type: AnswerType


class RecordedAnswer(BaseModel):
    """One answer a finished experiment run gave to the question."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    strategy: str
    outcome: Outcome
    correct: bool
    answer: AnswerValue
    cost_usd: float | None
    latency_s: float


class BenchmarkView(BaseModel):
    """A benchmark question with its gold facts: shown next to the answer, never fed to a tier."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: QuestionFamily
    text: str
    answer_type: AnswerType
    answerable: bool
    reference: AnswerValue
    #: The sheets the question truly depends on, as PDF pages.
    gold_sheets: tuple[SheetLink, ...]
    #: Cross-sheet difficulty (`Question.k` and its two parts) and units crossed.
    k: int | None
    k_connector: int | None
    k_identity: int | None
    u: int | None
    #: Whether the live answer was right; `None` when no live answer is attached.
    correct: bool | None = None
    recorded: tuple[RecordedAnswer, ...] = ()


class DemoAnswer(BaseModel):
    """A finished question: the cascade's answer plus the sheets to show next to it."""

    model_config = ConfigDict(frozen=True)

    live: LiveAnswer
    answer_sheets: tuple[SheetLink, ...]
    read_sheets: tuple[SheetLink, ...]
    benchmark: BenchmarkView | None = None


class JobStatus(BaseModel):
    """Where a question stands; the page polls this once a second."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    state: Literal["running", "done", "needs_paid", "refused", "error"]
    #: Always `None` for now: the cascade offers no progress hook (the page shows a timer).
    running_tier: str | None
    elapsed_s: float
    result: DemoAnswer | None
    needs_paid: NeedsPaidCall | None
    estimate: CostEstimate | None
    spend: SpendStatus
    #: Why the job was refused or failed.
    message: str | None


class CorpusStatus(BaseModel):
    """One configured corpus: loading state, what can be shown and which tiers can answer."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    state: Literal["waiting", "loading", "ready", "error"]
    pdf_present: bool
    #: Tiers that can answer (tier 1 is missing when the store does not hold the corpus).
    tiers: tuple[str, ...]
    #: False when the policy's database tier is left out ("tier 2 only" runs).
    tier1_store: bool
    n_benchmark_questions: int
    message: str | None


class AppStatus(BaseModel):
    """What `GET /api/status` returns."""

    model_config = ConfigDict(frozen=True)

    corpora: tuple[CorpusStatus, ...]
    policy: str
    #: The policy's tiers in order, as evaluated.
    policy_tiers: tuple[str, ...]
    cutoff_s: float
    paid_allowed: bool
    spend: SpendStatus
