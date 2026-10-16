"""One question running in a worker thread: its record, and the work that fills the record in."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from plantgraph.demo.app.answering import demo_answer
from plantgraph.demo.app.api_models import DemoAnswer, JobStatus
from plantgraph.demo.app.corpus_runtime import LoadedCorpus
from plantgraph.demo.app.models import SpendStatus
from plantgraph.demo.app.spend import SessionSpend
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.harness.spend_cap import Reservation, SpendCapReached
from plantgraph.qa.strategies.base import AskedQuestion

_LOG = logging.getLogger(__name__)

JobState = Literal["running", "done", "refused", "error"]


@dataclass
class Job:
    """The mutable record of one question.

    The worker sets `state` last, so a reader that sees a finished state also sees its result.
    """

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    finished: float | None = None
    result: DemoAnswer | None = None
    #: Seconds spent emptying the model cache before the ask (not part of the answer time).
    clear_s: float | None = None
    message: str | None = None
    state: JobState = "running"

    def end(self, state: JobState) -> None:
        """Close the job in `state` (set last, after the result fields)."""
        self.finished = time.perf_counter()
        self.state = state

    def status(self, spend: SpendStatus) -> JobStatus:
        """The job as the API shows it, with the current spend."""
        elapsed = (self.finished or time.perf_counter()) - self.started
        return JobStatus(
            job_id=self.job_id,
            state=self.state,
            running_tier=None,
            elapsed_s=elapsed,
            clear_s=self.clear_s,
            result=self.result,
            spend=spend,
            message=self.message,
        )


def run_job(job: Job, corpus: LoadedCorpus, asked: AskedQuestion, session: SessionSpend) -> None:
    """Answer the question live and record the outcome on `job`; never raises.

    Money is set aside first, so the session cap holds even when questions race. The cascade is
    kept open between asks; its model cache is emptied first. The reservation is released with the
    real spend.
    """
    reservation: Reservation | None = None
    spent_before = session.guard.spent_usd
    try:
        reservation = session.reserve()
        live = _ask_live(job, corpus, asked)
        job.result = demo_answer(corpus, live, asked)
        if job.result.cache_hit_detected:
            _LOG.error(
                "a stored answer was used for %r: the live-only guard failed", live.question_text
            )
        job.end("done")
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


def _ask_live(job: Job, corpus: LoadedCorpus, asked: AskedQuestion) -> LiveAnswer:
    """Empty the model cache, then ask the corpus's open cascade once."""
    cascade, job.clear_s = corpus.source.begin_ask()
    result = cascade.ask(asked)
    if isinstance(result, NeedsPaidCall):  # a live client never raises CacheMiss
        raise RuntimeError(f"expected a live answer, found a missing cache entry: {result.reason}")
    return result
