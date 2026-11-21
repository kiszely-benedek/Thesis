"""The fields read from the experiment report files, and how a file is read (rest ignored)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from plantgraph.demo.app.results_views import Interval, Provenance


class _Parsed(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Cell(_Parsed):
    """One arm on one corpus size and scope of the ladder."""

    corpus_id: str
    policy: str
    scope: str
    n: int
    acc_at_120: Interval
    cost_mean: float
    latency_median: float


class Size(_Parsed):
    """A ladder corpus and its sheet count."""

    corpus_id: str
    n_sheets: int


class LadderClaim(_Parsed):
    """A registered ladder claim and its verdict."""

    id: str
    wording: str
    value: str
    verdict: str


class LadderReport(_Parsed):
    """The ladder report file."""

    cutoff_s: float
    wall_sheets: float
    absent: list[str]
    sizes: list[Size]
    #: Scope name (`common`, `all`) -> the question families it covers.
    scope_families: dict[str, list[str]]
    cells: list[Cell]
    claims: list[LadderClaim] = []


class Summary(_Parsed):
    """Counts, cost and latency of one policy on one corpus."""

    n_questions: int
    n_correct_at_cutoff: int
    cost_per_question_usd: float
    latency_median_s: float
    latency_p90_s: float


class ScopeRow(_Parsed):
    """One policy on one corpus and question scope."""

    corpus_id: str
    scope: str
    policy: str
    summary: Summary
    accuracy: Interval


class SealedClaim(_Parsed):
    """A registered sealed-test claim and its status."""

    rule: str
    status: str
    #: Reads like "K1 [headline]: ..."; the bracket names the scope.
    headline: str


class Sealed(_Parsed):
    """The `sealed` block of a sealed-test report."""

    #: Sheet counts of the *pooled* ids (S100, S1000) only; a plant's count is in its ingest record.
    sheets: dict[str, int]
    #: Pooled id -> its plants. Absent in a report that predates pooling.
    scales: dict[str, list[str]] = {}
    scope_rows: list[ScopeRow]
    claims: list[SealedClaim] = []


class SealedReport(_Parsed):
    """A sealed-test report file."""

    sealed: Sealed


class IngestCounts(_Parsed):
    """Counts from a plant's ingest record."""

    n_sheets: int


class IngestRecord(_Parsed):
    """A plant's ingest record (`ingest.json`)."""

    counts: IngestCounts


class GrowthRow(_Parsed):
    """One measure on the small and the large plant of the infrastructure report."""

    name: str
    from_corpus: str
    to_corpus: str
    from_value: float
    to_value: float


class InfraCheck(_Parsed):
    """One self-check of the infrastructure report."""

    name: str
    #: `pass`, `fail` or `flag`.
    status: str
    detail: str


class InfraReport(_Parsed):
    """The infrastructure report file (its other blocks are not read)."""

    machine_summary: str
    checks: list[InfraCheck]
    growth: list[GrowthRow]


class E2EArmRow(_Parsed):
    """One arm's accuracy. The report's `spend_usd` is deliberately not read."""

    label: str
    n: int
    n_correct: int
    accuracy: Interval


class E2EPlant(_Parsed):
    """One plant's arms."""

    plant_id: str
    arms: list[E2EArmRow]


class E2EDifference(_Parsed):
    """A paired difference with its interval; the report calls the estimate `mean`."""

    mean: float
    ci_low: float
    ci_high: float


class E2EClaim(_Parsed):
    """A registered end-to-end claim and its boolean verdict."""

    claim: str
    description: str
    rule: str
    difference: E2EDifference
    passed: bool


class E2EReport(_Parsed):
    """The end-to-end report file (the markdown title and the spend are not read)."""

    plants: list[E2EPlant]
    #: The pooled arms (equal-weight mean over the plants).
    arms: list[E2EArmRow]
    claims: list[E2EClaim]


def provenance(path: Path, result_row: str) -> Provenance:
    """Path, hash and date of a report file, for the figure's caption."""
    data = path.read_bytes()
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return Provenance(
        path=path.as_posix(),
        sha256=hashlib.sha256(data).hexdigest(),
        modified=modified,
        result_row=result_row,
    )


def read_report[T: BaseModel](path: Path, model: type[T]) -> T:
    """Parse a JSON file, naming the file and the broken field when it does not fit."""
    if not path.exists():
        raise FileNotFoundError(f"expected the results report at {path}, found no such file")
    try:
        return model.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise ValueError(f"expected field {where!r} in {path}, found: {first['msg']}") from error
