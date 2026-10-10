"""The running app's state: corpora loading in the background, one question job at a time."""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import httpx2

from plantgraph.demo.app.answering import asked_question
from plantgraph.demo.app.api_models import (
    AppStatus,
    AskRequest,
    CorpusStatus,
    JobStatus,
    QuestionSummary,
)
from plantgraph.demo.app.config import DemoConfig, DemoCorpus, resolve_policy
from plantgraph.demo.app.corpus_runtime import CorpusLoader, CorpusLoadFn, LoadedCorpus
from plantgraph.demo.app.estimate import estimate_cost
from plantgraph.demo.app.jobs import Job, run_job
from plantgraph.demo.app.models import CostEstimate
from plantgraph.demo.app.spend import SessionSpend
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.strategies.base import AskedQuestion

_LOG = logging.getLogger(__name__)


class UnknownCorpus(LookupError):
    """The id is not in the config."""


class CorpusNotReady(RuntimeError):
    """The corpus is still loading, or failed to load."""


class Busy(RuntimeError):
    """A question is already running; the demo answers one at a time."""


class UnknownJob(LookupError):
    """No job has this id."""


LoadState = Literal["waiting", "loading", "ready", "error"]


@dataclass
class _Slot:
    """Loading state of one corpus."""

    state: LoadState = "waiting"
    message: str | None = None
    loaded: LoadedCorpus | None = None


class AppState:
    """Corpora, the session's spend and the single running question."""

    def __init__(
        self,
        config: DemoConfig,
        policy: CascadePolicy,
        session: SessionSpend,
        loader: CorpusLoadFn,
        *,
        allow_paid_calls: bool,
    ) -> None:
        self.config = config
        self.policy = policy
        self.session = session
        self.allow_paid_calls = allow_paid_calls
        self._loader = loader
        self._slots = {c.corpus_id: _Slot() for c in config.corpora}
        self._jobs: dict[str, Job] = {}
        self._busy = threading.Lock()

    # --- loading -------------------------------------------------------------------------

    def start_loading(self) -> threading.Thread:
        """Load the corpora in config order on a background thread; the PDFs serve at once."""
        thread = threading.Thread(target=self.load_all, name="corpus-loader", daemon=True)
        thread.start()
        return thread

    def load_all(self) -> None:
        """Load every configured corpus; a failure is recorded on its slot, not raised."""
        for corpus in self.config.corpora:
            self._load_one(corpus)

    def _load_one(self, corpus: DemoCorpus) -> None:
        slot = self._slots[corpus.corpus_id]
        slot.state = "loading"
        try:
            slot.loaded = self._loader(corpus)
        except Exception as error:  # shown in the status; the other corpora still load
            _LOG.exception("loading %s failed", corpus.corpus_id)
            slot.message = f"{type(error).__name__}: {error}"
            slot.state = "error"
            return
        slot.state = "ready"

    def close(self) -> None:
        """Close the cascades of every loaded corpus."""
        for slot in self._slots.values():
            if slot.loaded is not None:
                slot.loaded.source.close()

    # --- reading -------------------------------------------------------------------------

    def status(self) -> AppStatus:
        """Corpus states, policy, paid flag and spend, for `GET /api/status`."""
        return AppStatus(
            corpora=tuple(self._corpus_status(c) for c in self.config.corpora),
            policy=self.policy.name,
            policy_tiers=tuple(t.name for t in self.policy.tiers),
            cutoff_s=self.config.question_deadline_s,
            paid_allowed=self.allow_paid_calls,
            spend=self.session.status(),
        )

    def _corpus_status(self, corpus: DemoCorpus) -> CorpusStatus:
        slot, loaded = self._slots[corpus.corpus_id], self._slots[corpus.corpus_id].loaded
        return CorpusStatus(
            corpus_id=corpus.corpus_id,
            state=slot.state,
            pdf_present=corpus.pdf_path.exists(),
            tiers=loaded.source.tiers if loaded else (),
            tier1_store=loaded.source.tier1_store if loaded else False,
            n_benchmark_questions=len(loaded.questions) if loaded else 0,
            message=slot.message,
        )

    def ready_corpus(self, corpus_id: str) -> LoadedCorpus:
        """The loaded corpus.

        Raises:
            UnknownCorpus: not in the config.
            CorpusNotReady: still loading or failed.
        """
        slot = self._slots.get(corpus_id)
        if slot is None:
            raise UnknownCorpus(f"expected one of {sorted(self._slots)}, found {corpus_id!r}")
        if slot.loaded is None:
            raise CorpusNotReady(f"{corpus_id} is {slot.state}: {slot.message or 'not loaded yet'}")
        return slot.loaded

    def configured_corpus(self, corpus_id: str) -> DemoCorpus:
        """The config entry (usable before loading finishes, for the PDF and its index)."""
        corpus = self.config.corpus(corpus_id)
        if corpus is None:
            raise UnknownCorpus(f"expected one of {sorted(self._slots)}, found {corpus_id!r}")
        return corpus

    def question_list(self, corpus_id: str) -> Sequence[QuestionSummary]:
        """The benchmark picker's entries: id, family, text, answer type; no gold."""
        return [
            QuestionSummary(
                question_id=q.question_id, family=q.family, text=q.text, answer_type=q.answer_type
            )
            for q in self.ready_corpus(corpus_id).questions.values()
        ]

    # --- asking --------------------------------------------------------------------------

    def start_ask(self, request: AskRequest) -> str:
        """Start a question job on a worker thread and return its id.

        Raises:
            UnknownCorpus, CorpusNotReady, UnknownBenchmarkQuestion: bad target.
            Busy: another question is running.
        """
        corpus = self.ready_corpus(request.corpus_id)
        asked = asked_question(corpus, request)
        if not self._busy.acquire(blocking=False):
            raise Busy("a question is already running; wait for it to finish")
        job = Job()
        self._jobs[job.job_id] = job
        threading.Thread(
            target=self._work, args=(job, corpus, request, asked), name="ask-job", daemon=True
        ).start()
        return job.job_id

    def _work(
        self, job: Job, corpus: LoadedCorpus, request: AskRequest, asked: AskedQuestion
    ) -> None:
        try:
            run_job(job, corpus, request, asked, self.session, allow_paid=self.allow_paid_calls)
        finally:
            self._busy.release()

    def job_status(self, job_id: str) -> JobStatus:
        """The job's status.

        Raises:
            UnknownJob: no job has this id.
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise UnknownJob(f"expected a job id returned by /api/ask, found {job_id!r}")
        return job.status(self.session.status())


def build_app_state(
    config: DemoConfig,
    *,
    allow_paid_calls: bool = True,
    session_cap_usd: float | None = None,
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
    http_client: httpx2.Client | None = None,
) -> AppState:
    """Wire a real app: policy, cost estimates, spend guard and the corpus loader.

    Raises:
        NoCostEvidence: a tier has no recorded run to estimate its cost from.
    """
    # paid calls are on by default; the cap is the safety net (the config's, unless overridden)
    cap_usd = config.session_cap_usd if session_cap_usd is None else session_cap_usd
    policy = resolve_policy(config.policy)
    estimates = {c.corpus_id: _estimate(policy, c) for c in config.corpora}
    # one guard serves every corpus, so its reservation is the dearest corpus's
    dearest = max(estimates.values(), key=lambda e: e.reservation_usd)
    session = SessionSpend(cap_usd if allow_paid_calls else None, dearest, config.calls_log_path)
    loader = CorpusLoader(
        config,
        policy,
        estimates,
        session.guard,
        allow_paid_calls=allow_paid_calls,
        cypher_source_factory=cypher_source_factory,
        http_client=http_client,
    )
    return AppState(config, policy, session, loader, allow_paid_calls=allow_paid_calls)


def _estimate(policy: CascadePolicy, corpus: DemoCorpus) -> CostEstimate:
    return estimate_cost(policy, list(corpus.tier_runs.values()), corpus.corpus_id)
