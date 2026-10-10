"""One question running in a worker thread: its record, and the work that fills the record in."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from plantgraph.demo.app.answering import demo_answer
from plantgraph.demo.app.api_models import AskRequest, DemoAnswer, JobStatus
from plantgraph.demo.app.corpus_runtime import LoadedCorpus
from plantgraph.demo.app.models import CostEstimate, SpendStatus
from plantgraph.demo.app.spend import SessionSpend
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.harness.spend_cap import Reservation, SpendCapReached
from plantgraph.qa.strategies.base import AskedQuestion

_LOG = logging.getLogger(__name__)

JobState = Literal["running", "done", "needs_paid", "refused", "error"]


@dataclass
class Job:
    """The mutable record of one question.

    The worker sets `state` last, so a reader that sees a finished state also sees its result.
    """

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    result: DemoAnswer | None = None
    needs_paid: NeedsPaidCall | None = None
    estimate: CostEstimate | None = None
    message: str | None = None
    state: JobState = "running"

    def end(self, state: JobState) -> None:
        """Close the job in `state` (set last, after the result fields)."""
        self.finished = time.monotonic()
        self.state = state

    def status(self, spend: SpendStatus) -> JobStatus:
        """The job as the API shows it, with the current spend."""
        elapsed = (self.finished or time.monotonic()) - self.started
        return JobStatus(
            job_id=self.job_id,
            state=self.state,
            running_tier=None,
            elapsed_s=elapsed,
            result=self.result,
            needs_paid=self.needs_paid,
            estimate=self.estimate,
            spend=spend,
            message=self.message,
        )


def run_job(
    job: Job,
    corpus: LoadedCorpus,
    request: AskRequest,
    asked: AskedQuestion,
    session: SessionSpend,
) -> None:
    """Answer the question and record the outcome on `job`; never raises."""
    reservation: Reservation | None = None
    spent_before = session.guard.spent_usd
    try:
        # a confirmed paid question sets money aside first, so the cap holds even in a race
        reservation = session.reserve() if request.allow_paid else None
        asker = corpus.source.asker(paid=request.allow_paid, tier2_only=request.tier2_only)
        _record(job, corpus, asked, asker.ask(asked))
    except SpendCapReached as error:
        job.message = str(error)
        job.end("refused")
    except Exception as error:  # the page must show any failure, not hang on "running"
        _LOG.exception("demo question failed")
        job.message = f"{type(error).__name__}: {error}"
        job.end("error")
    finally:
        if reservation is not None:
            session.release(reservation, session.guard.spent_usd - spent_before)


def _record(
    job: Job, corpus: LoadedCorpus, asked: AskedQuestion, result: LiveAnswer | NeedsPaidCall
) -> None:
    if isinstance(result, NeedsPaidCall):
        job.needs_paid = result
        job.estimate = corpus.estimate
        job.end("needs_paid")
        return
    job.result = demo_answer(corpus, result, asked)
    job.end("done")
