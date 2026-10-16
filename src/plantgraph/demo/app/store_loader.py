"""The plant switch: put one plant into the graph database, wiping whatever it held.

The graph database (Neo4j) holds one plant at a time. Selecting a plant in the demo is the load:
`switch_plant` wipes the plants the database holds and loads the chosen one with the frozen loader
(`store.neo4j_loader`). `PlantTracker` remembers what the page shows about it: what is held, a
running load, and the last measured seconds.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.demo.app.api_models import PlantLoad, PlantStatus
from plantgraph.demo.app.store_probe import HeldCorporaProbe
from plantgraph.store.neo4j_loader import load_corpus, wipe_corpus
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env

_LOG = logging.getLogger(__name__)

#: Error code of a switch that failed (the label table has its text).
PLANT_LOAD_FAILED = "plant_load_failed"

#: Does the whole switch for a plant: wipe the held plants, load the chosen one.
PlantSwitcher = Callable[[str, LoadPlan, HeldCorporaProbe], PlantLoad]


def switch_plant(
    corpus_id: str, plan: LoadPlan, held: HeldCorporaProbe, settings: Neo4jSettings
) -> PlantLoad:
    """Wipe every other plant the database holds, then load `corpus_id` from `plan`.

    `load_corpus` wipes the plant's own earlier copy itself, so only the others are wiped here.
    """
    others = tuple(held_id for held_id in held() if held_id != corpus_id)
    started = time.perf_counter()
    for other in others:
        wipe_corpus(settings, other)
    wipe_s = time.perf_counter() - started
    report = load_corpus(settings, plan)
    return PlantLoad(corpus_id=corpus_id, wiped=others, wipe_s=wipe_s, load_s=report.total_s)


def switch_plant_from_env(corpus_id: str, plan: LoadPlan, held: HeldCorporaProbe) -> PlantLoad:
    """`switch_plant` with the `NEO4J_*` settings of the environment.

    Raises:
        ValueError: the settings are absent.
    """
    settings = from_env()
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found them unset")
    return switch_plant(corpus_id, plan, held, settings)


class _IngestStages(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stage_seconds: dict[str, float] = {}


def recorded_load_seconds(ingest_json: Path) -> float | None:
    """The load stage's seconds in an ingest record (`stage_seconds.load_total`), if present."""
    if not ingest_json.exists():
        return None
    record = _IngestStages.model_validate(json.loads(ingest_json.read_text(encoding="utf-8")))
    return record.stage_seconds.get("load_total")


class PlantTracker:
    """What the page shows about the database's plant; safe to read while a switch runs."""

    def __init__(self, probe: HeldCorporaProbe, last_load_s: dict[str, float]) -> None:
        self._probe = probe
        self._lock = threading.Lock()
        self._held: tuple[str, ...] = ()
        self._loading: str | None = None
        self._started = 0.0
        self._last: PlantLoad | None = None
        self._error: str | None = None
        self._last_load_s = dict(last_load_s)

    def refresh_held(self) -> None:
        """Read which plants the database holds; an unreadable database counts as empty."""
        try:
            held = self._probe()
        except Exception as error:  # unreachable or unconfigured: the store state says so
            _LOG.warning("could not read the plants the database holds: %s", error)
            held = ()
        with self._lock:
            self._held = held

    def holds(self, corpus_id: str) -> bool:
        """Whether the database holds this plant now."""
        with self._lock:
            return corpus_id in self._held

    def only_holds(self, corpus_id: str) -> bool:
        """Whether the database holds exactly this plant (a switch to it would do nothing)."""
        with self._lock:
            return self._held == (corpus_id,)

    def begin(self, corpus_id: str) -> None:
        """Mark a load as running."""
        with self._lock:
            self._loading, self._started, self._error = corpus_id, time.perf_counter(), None

    def run(self, corpus_id: str, plan: LoadPlan, switcher: PlantSwitcher) -> None:
        """Do the switch (after `begin`); a failure is recorded as an error code, not raised.

        `loading` stays set until `end`, so the page keeps asking disabled meanwhile.
        """
        try:
            result = switcher(corpus_id, plan, self._probe)
        except Exception:  # shown as plant_load_failed; the held plants are read again below
            _LOG.exception("loading %s into the graph database failed", corpus_id)
            self._finish(error=PLANT_LOAD_FAILED)
            return
        self._finish(result=result)

    def _finish(self, *, result: PlantLoad | None = None, error: str | None = None) -> None:
        self.refresh_held()  # the database may be half-changed after a failure
        with self._lock:
            if result is not None:
                self._last = result
                self._last_load_s[result.corpus_id] = result.load_s
            self._error = error

    def end(self) -> None:
        """Mark the load as over (after the cascades were reopened, so asking is safe again)."""
        with self._lock:
            self._loading = None

    def status(self) -> PlantStatus:
        """The switch as the API shows it."""
        with self._lock:
            elapsed = time.perf_counter() - self._started if self._loading else None
            return PlantStatus(
                held=self._held,
                loading=self._loading,
                elapsed_s=elapsed,
                last=self._last,
                error=self._error,
                last_load_s=dict(self._last_load_s),
            )
