"""The running app's state: corpora loading in the background, one question job at a time."""

from __future__ import annotations

import logging
import threading
import time
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
    PlantStatus,
    QuestionSummary,
    TagLookup,
)
from plantgraph.demo.app.config import DemoConfig, DemoCorpus, resolve_policy
from plantgraph.demo.app.corpus_runtime import CorpusLoader, CorpusLoadFn, LoadedCorpus
from plantgraph.demo.app.estimate import estimate_cost
from plantgraph.demo.app.jobs import Job, run_job
from plantgraph.demo.app.live_cascades import NO_API_KEY, NoApiKey
from plantgraph.demo.app.models import CostEstimate
from plantgraph.demo.app.spend import SessionSpend
from plantgraph.demo.app.store_loader import (
    PlantSwitcher,
    PlantTracker,
    recorded_load_seconds,
    switch_plant_from_env,
)
from plantgraph.demo.app.store_probe import HeldCorporaProbe, held_corpus_ids_from_env
from plantgraph.demo.app.tag_lookup import TagIndex, lookup
from plantgraph.demo.app.topics import topic_of
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


class PlantNotLoaded(RuntimeError):
    """The graph database does not hold the asked plant; the visitor must select it first."""


class UnknownJob(LookupError):
    """No job has this id."""


LoadState = Literal["waiting", "loading", "ready", "error"]


@dataclass
class _Slot:
    """Loading state of one corpus."""

    state: LoadState = "waiting"
    message: str | None = None
    #: Code of the failure when it has a label of its own (for example `no_api_key`).
    error_code: str | None = None
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
        held_corpora_probe: HeldCorporaProbe = held_corpus_ids_from_env,
        plant_switcher: PlantSwitcher = switch_plant_from_env,
    ) -> None:
        self.config = config
        self.policy = policy
        self.session = session
        self._loader = loader
        self._slots = {c.corpus_id: _Slot() for c in config.corpora}
        self._jobs: dict[str, Job] = {}
        # a corpus's tag index, built on the first lookup; tied to the loaded corpus it came from
        self._tag_indexes: dict[str, tuple[LoadedCorpus, TagIndex]] = {}
        self._tag_index_lock = threading.Lock()
        # one lock for asks and plant switches: neither can start while the other runs
        self._busy = threading.Lock()
        self._plant_switcher = plant_switcher
        self._plants = PlantTracker(held_corpora_probe, _recorded_load_seconds(config))

    # --- loading -------------------------------------------------------------------------

    def start_loading(self) -> threading.Thread:
        """Load the corpora in config order on a background thread; the PDFs serve at once."""
        thread = threading.Thread(target=self.load_all, name="corpus-loader", daemon=True)
        thread.start()
        return thread

    def load_all(self) -> None:
        """Read which plant the database holds, then load every configured corpus.

        A failure is recorded on the corpus's slot, not raised.
        """
        self._plants.refresh_held()
        for corpus in self.config.corpora:
            self._load_one(corpus)

    def _load_one(self, corpus: DemoCorpus) -> None:
        slot = self._slots[corpus.corpus_id]
        slot.state = "loading"
        try:
            loaded = self._loader(corpus)
        except NoApiKey as error:  # no corpus can answer without a key; say so by code
            _LOG.error("loading %s failed: %s", corpus.corpus_id, error)
            slot.message, slot.error_code = str(error), NO_API_KEY
            slot.state = "error"
            return
        except Exception as error:  # shown in the status; the other corpora still load
            _LOG.exception("loading %s failed", corpus.corpus_id)
            slot.message = f"{type(error).__name__}: {error}"
            slot.state = "error"
            return
        if slot.loaded is not None:  # a reload: free the old cascade and its cache file
            slot.loaded.source.close()
        slot.loaded = loaded
        slot.state = "ready"

    def close(self) -> None:
        """Close every corpus's open cascade (on shutdown)."""
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
            spend=self.session.status(),
            plant=self._plants.status(),
        )

    def plant_status(self) -> PlantStatus:
        """The plant switch: what the database holds, a running load, the last timing."""
        return self._plants.status()

    def _corpus_status(self, corpus: DemoCorpus) -> CorpusStatus:
        slot, loaded = self._slots[corpus.corpus_id], self._slots[corpus.corpus_id].loaded
        return CorpusStatus(
            corpus_id=corpus.corpus_id,
            state=slot.state,
            pdf_present=corpus.pdf_path.exists(),
            tiers=loaded.source.tiers if loaded else (),
            tier1_store=loaded.source.tier1_store if loaded else False,
            store=loaded.source.store if loaded else None,
            n_sheets=len(loaded.pages) if loaded else None,
            n_benchmark_questions=len(loaded.questions) if loaded else 0,
            message=slot.message,
            error_code=slot.error_code,
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
        """The example picker's entries: id, family, topic, text; no gold, no answer form."""
        return [
            QuestionSummary(
                question_id=q.question_id, family=q.family, topic=topic_of(q.family), text=q.text
            )
            for q in self.ready_corpus(corpus_id).questions.values()
        ]

    def tag_lookup(self, corpus_id: str, query: str) -> TagLookup:
        """Where the tag `query` is drawn, from the corpus's in-memory item graph (no database).

        Raises:
            UnknownCorpus, CorpusNotReady: as `ready_corpus`.
        """
        corpus = self.ready_corpus(corpus_id)
        return lookup(query, corpus.item_graph, self._tag_index(corpus), corpus.pages)

    def _tag_index(self, corpus: LoadedCorpus) -> TagIndex:
        corpus_id = corpus.config.corpus_id
        with self._tag_index_lock:
            cached = self._tag_indexes.get(corpus_id)
            if cached is not None and cached[0] is corpus:
                return cached[1]
            started = time.perf_counter()
            index = TagIndex.build(corpus.item_graph)
            _LOG.info(
                "built the %s tag index (%d tags) in %.3f s",
                corpus_id, len(index.pairs), time.perf_counter() - started,
            )  # fmt: skip
            self._tag_indexes[corpus_id] = (corpus, index)
            return index

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
            raise Busy("a question or a plant switch is running; wait for it to finish")
        if not self._store_allows(corpus):
            self._busy.release()
            raise PlantNotLoaded(
                f"expected {corpus.config.corpus_id} in the graph database, "
                f"found {list(self._plants.status().held)}; select the plant to load it"
            )
        job = Job()
        self._jobs[job.job_id] = job
        threading.Thread(
            target=self._work, args=(job, corpus, asked), name="ask-job", daemon=True
        ).start()
        return job.job_id

    def _work(self, job: Job, corpus: LoadedCorpus, asked: AskedQuestion) -> None:
        try:
            run_job(job, corpus, asked, self.session)
        finally:
            self._busy.release()

    def _store_allows(self, corpus: LoadedCorpus) -> bool:
        """A corpus whose policy has a database step needs its plant in the database."""
        if corpus.source.store.kind == "not_needed":
            return True
        return self._plants.holds(corpus.config.corpus_id)

    # --- the plant switch ----------------------------------------------------------------

    def start_plant_switch(self, corpus_id: str) -> PlantStatus:
        """Load `corpus_id` into the graph database on a worker thread (a no-op if it is there).

        Raises:
            UnknownCorpus, CorpusNotReady: the plan comes from a loaded corpus.
            Busy: a question or another switch is running.
        """
        corpus = self.ready_corpus(corpus_id)
        if self._plants.only_holds(corpus_id):
            return self._plants.status()
        if not self._busy.acquire(blocking=False):
            raise Busy("a question or a plant switch is running; wait for it to finish")
        self._plants.begin(corpus_id)
        threading.Thread(
            target=self._switch_work, args=(corpus,), name="plant-switch", daemon=True
        ).start()
        return self._plants.status()

    def _switch_work(self, corpus: LoadedCorpus) -> None:
        try:
            self._plants.run(corpus.config.corpus_id, corpus.load_plan, self._plant_switcher)
            self.reopen_cascades()
        finally:
            self._plants.end()
            self._busy.release()

    def reopen_cascades(self) -> None:
        """Reopen every loaded corpus's cascade, so each sees the database as it is now.

        The chosen plant gets its database step back; the wiped plant's old Cypher source (which
        would read an emptied database) is replaced by one opened against the new contents, which
        leaves that plant on the agent step only.
        """
        for slot in self._slots.values():
            if slot.loaded is not None:
                self._reopen_one(slot, slot.loaded)

    def _reopen_one(self, slot: _Slot, loaded: LoadedCorpus) -> None:
        try:
            loaded.source = loaded.source.reopen()
        except Exception as error:  # the old cascade is closed; the plant cannot answer now
            _LOG.exception("reopening the %s cascade failed", loaded.config.corpus_id)
            slot.message = f"{type(error).__name__}: {error}"
            slot.loaded, slot.state = None, "error"

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
    session_cap_usd: float | None = None,
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
    transport: httpx2.BaseTransport | None = None,
    held_corpora_probe: HeldCorporaProbe = held_corpus_ids_from_env,
    plant_switcher: PlantSwitcher = switch_plant_from_env,
) -> AppState:
    """Wire a real app: policy, spend guard and the corpus loader. Every ask is live.

    Raises:
        NoCostEvidence: a tier has no recorded run to estimate its cost from.
    """
    # every ask is a paid call; the cap is the safety net (the config's, unless overridden)
    cap_usd = config.session_cap_usd if session_cap_usd is None else session_cap_usd
    policy = resolve_policy(config.policy)
    estimates = {c.corpus_id: _estimate(policy, c) for c in config.corpora}
    # one guard serves every corpus, so its reservation is the dearest corpus's
    dearest = max(estimates.values(), key=lambda e: e.reservation_usd)
    session = SessionSpend(cap_usd, dearest, config.calls_log_path)
    loader = CorpusLoader(
        config,
        policy,
        session.guard,
        cypher_source_factory=cypher_source_factory,
        transport=transport,
        held_corpora_probe=held_corpora_probe,
    )
    return AppState(
        config,
        policy,
        session,
        loader,
        held_corpora_probe=held_corpora_probe,
        plant_switcher=plant_switcher,
    )


def _recorded_load_seconds(config: DemoConfig) -> dict[str, float]:
    """Each plant's load seconds from its ingest record: the page's first "last time"."""
    recorded = {c.corpus_id: recorded_load_seconds(c.ingest_json) for c in config.corpora}
    return {corpus_id: seconds for corpus_id, seconds in recorded.items() if seconds is not None}


def _estimate(policy: CascadePolicy, corpus: DemoCorpus) -> CostEstimate:
    return estimate_cost(policy, list(corpus.tier_runs.values()), corpus.corpus_id)
