"""The request and response types of the demo's HTTP API (what the page sends and receives)."""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from plantgraph.demo.app.models import CostEstimate, SheetLink, SpendStatus
from plantgraph.demo.app.store_probe import StoreState
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.models import AnswerType, AnswerValue, Outcome, QuestionFamily


class AskRequest(BaseModel):
    """One question to ask: the text in the box, and the example it was filled from, if any.

    The visitor never picks an answer form: the server decides it (`answering.asked_question`).
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    corpus_id: str
    text: str = ""
    #: The example the text came from. Asked with its text unchanged, the example runs as itself
    #: (stored answer type, reference answer, free replay); otherwise the text is free text.
    #: `benchmark_question_id` is the old name, still sent by the pre-DP-T6 page.
    example_id: str | None = Field(
        default=None, validation_alias=AliasChoices("example_id", "benchmark_question_id")
    )
    #: Skip tier 1 even if the store holds the corpus.
    tier2_only: bool = False

    @model_validator(mode="after")
    def _needs_a_question(self) -> AskRequest:
        # A blank text with an example id is the old page's "ask this example" shape.
        if not self.text.strip() and self.example_id is None:
            raise ValueError("expected a question text or an example_id, found neither")
        return self


class QuestionSummary(BaseModel):
    """One example question in the picker: no reference answer, no gold, no answer form."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: QuestionFamily
    #: The family in plain Hungarian, for grouping the list; the family code itself is not shown.
    topic: str
    text: str


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
    #: Why the database tier can or cannot answer; `None` until the corpus is loaded.
    store: StoreState | None
    #: Sheets (pages of the drawing index) in the corpus; `None` until it is loaded.
    n_sheets: int | None
    #: Seconds each cascade took to open, by mode (`{}` until loaded).
    open_s: dict[str, float]
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
