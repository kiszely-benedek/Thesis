"""The demo's configuration file: which corpora to serve and which stored runs fix the tiers."""

from __future__ import annotations

from pathlib import Path

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


class DemoConfig(BaseModel):
    """The whole demo: corpora, the cascade policy and where its own cache and log live."""

    model_config = ConfigDict(frozen=True)

    corpora: tuple[DemoCorpus, ...]
    #: A shipped policy name (`cascade_v2`) or the path of a policy JSON.
    policy: str
    #: The cascade's cutoff C: a question gets this many seconds across all its tiers.
    question_deadline_s: float = 120.0
    #: The demo's own answer cache and call log: demo answers never mix into experiment caches.
    cache_path: Path
    calls_log_path: Path

    @model_validator(mode="after")
    def _corpora_are_unique(self) -> DemoConfig:
        ids = [corpus.corpus_id for corpus in self.corpora]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError(f"expected one or more distinct corpus ids, found {ids}")
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
