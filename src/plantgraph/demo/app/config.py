"""The demo's configuration file: which corpora to serve and which stored runs fix the tiers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policy

#: Name of the sidecar the drawing export writes next to the PDF.
PDF_NAME = "drawings.pdf"
INDEX_NAME = "drawings.index.json"


class DemoCorpus(BaseModel):
    """One plant the demo shows: its ingest file, its drawing PDF and its recorded runs."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    ingest_json: Path
    #: Holds `drawings.pdf` and `drawings.index.json` (the drawing export's output).
    drawings_dir: Path
    #: The corpus's benchmark questions; without it the picker is empty.
    questions_jsonl: Path | None = None
    #: Finished runs whose answers are shown next to a benchmark question.
    recorded_runs: tuple[Path, ...] = ()
    #: Tier name -> the run that fixes the tier's pin, parameters and primer. Exactly one run per
    #: tier, so the cost estimate does not count a question twice.
    tier_runs: dict[str, Path]

    @property
    def pdf_path(self) -> Path:
        """Where the exported drawing PDF is."""
        return self.drawings_dir / PDF_NAME

    @property
    def index_path(self) -> Path:
        """Where the sheet-to-page index is."""
        return self.drawings_dir / INDEX_NAME


class ResultsSources(BaseModel):
    """The two experiment reports the Results tab reads, and the results rows that cite them."""

    model_config = ConfigDict(frozen=True)

    ladder_report: Path
    ladder_result_row: str = "EXP-0001-LADDER"
    sealed_report: Path
    sealed_result_row: str = "EXP-0002-H100, EXP-0002-H1000"


class PresentationStep(BaseModel):
    """One step of a presentation: an example question asked live, or the Results tab."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["example", "results"] = "example"
    #: The example's id in the plant's examples file; an `example` step needs it.
    question_id: str | None = None

    @model_validator(mode="after")
    def _example_needs_an_id(self) -> PresentationStep:
        if self.kind == "example" and not self.question_id:
            raise ValueError("expected an `example` step to name a question_id, found none")
        return self


class PresentationSequence(BaseModel):
    """A short talk on one plant: its steps run in order, every example asked live."""

    model_config = ConfigDict(frozen=True)

    #: The one plant of the sequence; it is never switched mid-sequence.
    corpus_id: str
    title: str
    steps: tuple[PresentationStep, ...]

    @model_validator(mode="after")
    def _has_steps(self) -> PresentationSequence:
        if not self.steps:
            raise ValueError(f"expected sequence {self.title!r} to have steps, found none")
        return self


class DemoConfig(BaseModel):
    """The whole demo: corpora, the cascade policy and where its own call log lives."""

    model_config = ConfigDict(frozen=True)

    corpora: tuple[DemoCorpus, ...]
    #: A shipped policy name (`cascade_v2`) or the path of a policy JSON.
    policy: str
    #: The cascade's cutoff C: a question gets this many seconds across all its tiers.
    question_deadline_s: float = 120.0
    #: Hard cap on one server session's paid calls (USD); `--session-cap-usd` overrides it.
    session_cap_usd: float = 2.0
    #: The demo's own call log: demo calls never mix into experiment logs. (No answer cache:
    #: the demo answers live only.)
    calls_log_path: Path
    #: Report files behind the Results tab; without it `/api/results` answers 404.
    results: ResultsSources | None = None
    #: Talks for presentation mode; the question ids name this machine's example files, so the
    #: list lives in the local config and is empty in the shipped example.
    presentation: tuple[PresentationSequence, ...] = ()

    @model_validator(mode="after")
    def _corpora_are_unique(self) -> DemoConfig:
        ids = [corpus.corpus_id for corpus in self.corpora]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError(f"expected one or more distinct corpus ids, found {ids}")
        return self

    @model_validator(mode="after")
    def _sequences_name_configured_plants(self) -> DemoConfig:
        known = {corpus.corpus_id for corpus in self.corpora}
        unknown = [s.title for s in self.presentation if s.corpus_id not in known]
        if unknown:
            raise ValueError(
                f"expected every presentation sequence to name a configured plant "
                f"{sorted(known)}, found sequences {unknown} naming others"
            )
        return self

    def corpus(self, corpus_id: str) -> DemoCorpus | None:
        """The configured corpus with this id, or `None`."""
        return next((c for c in self.corpora if c.corpus_id == corpus_id), None)


def load_demo_config(path: Path) -> DemoConfig:
    """Read and validate the config file.

    Raises:
        FileNotFoundError: `path` does not exist.
        ValueError: the JSON does not match `DemoConfig`.
    """
    if not path.exists():
        raise FileNotFoundError(f"expected the demo config at {path}, found no such file")
    return DemoConfig.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_policy(value: str) -> CascadePolicy:
    """Load a policy by shipped name or by file path.

    Raises:
        FileNotFoundError: neither a file nor a shipped policy of that name exists.
    """
    given = Path(value)
    path = given if given.exists() else POLICIES_DIR / f"{value}.json"
    if not path.exists():
        raise FileNotFoundError(f"expected a policy file or a shipped policy name, found {value!r}")
    return load_policy(path)
