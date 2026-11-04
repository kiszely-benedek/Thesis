"""Where a corpus directory keeps its files, and typed reading and writing of them.

    <dir>/corpus.json  pairs.json  taus.json  tuning_trace.json  score.json  report.md
    <dir>/decisions/<decider>.json   <dir>/links/<decider>.json

Writing refuses to overwrite: a measurement is never silently replaced.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


def corpus_path(directory: Path) -> Path:
    """The corpus spec and description."""
    return directory / "corpus.json"


def pairs_path(directory: Path) -> Path:
    """The labelled candidate pairs."""
    return directory / "pairs.json"


def taus_path(directory: Path) -> Path:
    """The tuned D1 and D2 thresholds."""
    return directory / "taus.json"


def trace_path(directory: Path) -> Path:
    """Every threshold tried while tuning."""
    return directory / "tuning_trace.json"


def decision_path(directory: Path, decider_id: str) -> Path:
    """One decider's run on the corpus."""
    return directory / "decisions" / f"{decider_id}.json"


def links_path(directory: Path, decider_id: str) -> Path:
    """One decider's accepted links, as `ingest --identity-links` reads them."""
    return directory / "links" / f"{decider_id}.json"


def score_path(directory: Path) -> Path:
    """The scores with bootstrap intervals."""
    return directory / "score.json"


def report_path(directory: Path) -> Path:
    """The Markdown report."""
    return directory / "report.md"


def write_model(path: Path, model: BaseModel) -> None:
    """Write `model` as indented JSON; raise if `path` exists."""
    write_text(path, model.model_dump_json(indent=1))


def write_text(path: Path, text: str) -> None:
    """Write `text` to a new file, creating parent folders; raise if `path` exists."""
    if path.exists():
        raise FileExistsError(
            f"expected {path} not to exist (a measurement is never overwritten), found it"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_model[Model: BaseModel](path: Path, model_type: type[Model]) -> Model:
    """Read `path` as a `model_type`; raise with the path if it is missing or malformed."""
    if not path.is_file():
        raise FileNotFoundError(
            f"expected {path} to exist (run the earlier step first), found none"
        )
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"expected {path} to hold a {model_type.__name__} as JSON: {error}"
        ) from error
