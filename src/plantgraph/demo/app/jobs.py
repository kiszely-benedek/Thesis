"""One question running in a worker thread: its record, and the work that fills the record in."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from plantgraph.demo.app.answering import demo_answer
from plantgraph.demo.app.api_models import DemoAnswer, JobStatus
from plantgraph.demo.app.ask_trace import build_trace
from plantgraph.demo.app.corpus_runtime import LoadedCorpus
from plantgraph.demo.app.models import SpendStatus
from plantgraph.demo.app.progress import live_progress
from plantgraph.demo.app.progress_models import LiveProgress
from plantgraph.demo.app.spend import SessionSpend
from plantgraph.demo.app.trace_models import AskTrace
from plantgraph.demo.app.trace_recorder import TraceWindow
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
    #: Where this ask's recorded model traffic begins; set as soon as the ask is opened.
    window: TraceWindow | None = None
    #: The model attempts, frozen when the job ends (the recorder goes on to serve later asks).
    final_progress: LiveProgress | None = None

    def end(self, state: JobState) -> None:
        """Close the job in `state` (set last, after the result fields)."""
        self.finished = time.perf_counter()
        self.final_progress = self._progress()
        self.state = state

    def _progress(self) -> LiveProgress | None:
        """The attempts so far; a failure to read them must never hide the answer."""
        if self.window is None:
            return None
        try:
            return live_progress(self.window)
        except Exception:  # progress is a courtesy; the job itself goes on
            _LOG.exception("reading the ask's progress failed")
            return None

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
            progress=self.final_progress if self.finished else self._progress(),
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
        live, window = _ask_live(job, corpus, asked)
        job.result = demo_answer(corpus, live, asked, _trace_of(window, corpus))
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


def _ask_live(
    job: Job, corpus: LoadedCorpus, asked: AskedQuestion
) -> tuple[LiveAnswer, TraceWindow]:
    """Empty the model cache, then ask the corpus's open cascade once."""
    handle = corpus.source.begin_ask()
    job.clear_s = handle.clear_s
    job.window = handle.window  # from here on the page can poll the attempts
    result = handle.cascade.ask(asked)
    if isinstance(result, NeedsPaidCall):  # a live client never raises CacheMiss
        raise RuntimeError(f"expected a live answer, found a missing cache entry: {result.reason}")
    return result, handle.window


def _trace_of(window: TraceWindow, corpus: LoadedCorpus) -> AskTrace:
    """The ask's route, read now (before any late reply of an abandoned call can change it).

    A trace that cannot be built must not discard the answer, so the failure is carried in it.
    """
    try:
        return build_trace(window.exchanges(), window.log_lines(), corpus.item_graph)
    except Exception as error:  # the answer is already paid for; show it without a route
        _LOG.exception("building the ask trace failed")
        return AskTrace(error=f"{type(error).__name__}: {error}")
