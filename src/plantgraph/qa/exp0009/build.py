"""Building one EXP-0009 plant: the A corpus, its B twin, and the valve-positions file (§19.4).

The ingest CLI is left alone (ADR-0068 decision 2): this module composes the config from `plan.json`
and calls `run_synthetic` directly, with the CLI's own writer. The B corpus is **not** generated a
second time. Its `ingest.json` is A's with the corpus id replaced, because the node uids are built
from the id when the corpus is rebuilt and nothing else in the file depends on it (decision 3).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.ingest.seed_plan import SeedPlan, require_drawn_test_seed
from plantgraph.qa.exp0009.plan import PlantSpec22, a_id_of
from plantgraph.qa.v2tb.store_b import ingest_positions

INGEST_FILE = "ingest.json"
RULES_FILE = "rules.json"
CORPUS_B_FILE = "corpus_b.json"


class CorpusBRecord(BaseModel):
    """`corpus_b.json`: what ties a B corpus to its A corpus and to its positions file."""

    model_config = ConfigDict(frozen=True)

    a_id: str
    b_id: str
    a_ingest_sha256: str
    b_ingest_sha256: str
    positions_sha256: str
    positions_per_code: dict[str, int]
    #: wall-clock seconds of the A build, the relabel and the positions step
    seconds: dict[str, float]


def sha256_of_file(path: Path) -> str:
    """Hex sha256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_exact(path: Path) -> str:
    """The file's text, line endings untouched (Windows' text mode would turn CRLF into LF)."""
    return path.read_bytes().decode("utf-8")


def relabel_ingest_text(text: str, from_id: str, to_id: str) -> str:
    """`ingest.json` text with its one `corpus_id` field changed.

    Raises:
        ValueError: the file does not hold the field exactly once.
    """
    field = f'"corpus_id": "{from_id}"'
    if text.count(field) != 1:
        raise ValueError(
            f"expected exactly one {field} in the ingest file, found {text.count(field)}"
        )
    return text.replace(field, f'"corpus_id": "{to_id}"')


def build_a(spec: PlantSpec22, corpora_root: Path, seeds: SeedPlan | None) -> IngestResult:
    """Generate, split and check the A corpus, and write `ingest.json` and `rules.json`.

    Raises:
        ValueError: a retired or undrawn test seed, or the round trip (gate G1) failed.
    """
    from plantgraph.ingest.__main__ import _write_result  # the frozen writer, not a copy

    require_drawn_test_seed(spec.seed, seeds)  # EXP-0009's seeds, never EXP-0008's default path
    result = run_synthetic(
        corpus_id=spec.plant_id,
        generator_config=spec.generator_config(),
        split_config=HeadlinePresetV22().split_config(spec.seed),
        check=True,
        settings=None,
        store_profile="both",  # the ingest CLI's default, which EXP-0008's build used
    )
    if result.gate_equal is False:
        raise ValueError(f"expected the round trip to reproduce {spec.plant_id}, it did not")
    _write_result(result, corpora_root / spec.plant_id)
    return result


def write_b_files(a_id: str, a_dir: Path, b_dir: Path) -> None:
    """Relabel A's `ingest.json` into the B folder and copy `rules.json`."""
    b_dir.mkdir(parents=True, exist_ok=True)
    text = _read_exact(a_dir / INGEST_FILE)
    relabelled = relabel_ingest_text(text, a_id, a_id + "B")
    (b_dir / INGEST_FILE).write_bytes(relabelled.encode("utf-8"))
    if (a_dir / RULES_FILE).is_file():
        (b_dir / RULES_FILE).write_bytes((a_dir / RULES_FILE).read_bytes())


def require_relabel_equal(a_ingest: Path, b_ingest: Path) -> None:
    """The byte test: B's file with the id put back equals A's file.

    Raises:
        ValueError: the two files differ by more than the corpus id.
    """
    text = _read_exact(b_ingest)
    b_id = json.loads(text)["corpus_id"]
    restored = relabel_ingest_text(text, b_id, a_id_of(b_id))
    if restored.encode("utf-8") != a_ingest.read_bytes():
        raise ValueError(f"expected {b_ingest} to equal {a_ingest} but its id, found a difference")


def build_plant(spec: PlantSpec22, corpora_root: Path, seeds: SeedPlan | None) -> CorpusBRecord:
    """The whole free build of one plant: A corpus, B relabel, positions, `corpus_b.json`.

    Gate G0-B check 1 (the file equals the generator plan's positions) runs inside the positions
    step. Never overwrites: a plant is built once.

    Raises:
        FileExistsError: the plant's folder already exists.
    """
    a_dir, b_dir = corpora_root / spec.plant_id, corpora_root / spec.b_id
    if a_dir.exists() or b_dir.exists():
        raise FileExistsError(
            f"expected no folder for {spec.plant_id}, found one under {corpora_root}"
        )
    started = time.perf_counter()
    build_a(spec, corpora_root, seeds)
    built = time.perf_counter()
    write_b_files(spec.plant_id, a_dir, b_dir)
    relabelled = time.perf_counter()
    require_relabel_equal(a_dir / INGEST_FILE, b_dir / INGEST_FILE)
    positions = ingest_positions(spec.generator_config(), b_dir)
    record = CorpusBRecord(
        a_id=spec.plant_id,
        b_id=spec.b_id,
        a_ingest_sha256=sha256_of_file(a_dir / INGEST_FILE),
        b_ingest_sha256=sha256_of_file(b_dir / INGEST_FILE),
        positions_sha256=positions.sha256,
        positions_per_code=dict(sorted(Counter(positions.positions.values()).items())),
        seconds={
            "a_build": round(built - started, 1),
            "relabel": round(relabelled - built, 1),
            "positions": round(time.perf_counter() - relabelled, 1),
        },
    )
    (b_dir / CORPUS_B_FILE).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return record
