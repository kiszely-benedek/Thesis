"""Loading a plant into Neo4j for the Cypher tier, one corpus at a time (design §19.4).

**One corpus in the database at a time** (user rule): every load recreates the database first
(`fresh_database=True`), so nothing of the previous plant is left. The A load goes through
`run_synthetic` with the `plant_lines` store profile. The B load is the frozen B loader
(`python -m plantgraph.qa.v2tb load`, which also checks the positions are in the database); this
module only prepares the B folder it reads. `neo4j=False` writes the same files without touching a
database (the smoke).

The Cypher tier reads a copy of the first load's `ingest.json` kept under `cypcorp/plant_lines/`:
a reload rewrites the file's timings, but a run freezes that file's hash and refuses to resume on
a changed one, so the copy is made once and never replaced.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.load_step import NO_MEASUREMENT, StoreMeasurement
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.exp0009.build import (
    CORPUS_B_FILE,
    INGEST_FILE,
    sha256_of_file,
)
from plantgraph.qa.exp0009.plan import b_id_of
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME
from plantgraph.store.neo4j_settings import Neo4jSettings

PROFILE: Literal["plant_lines"] = "plant_lines"
CYPCORP = Path("cypcorp") / PROFILE


def load_a(root: Path, plant_id: str, settings: Neo4jSettings | None) -> Path:
    """Load plant `plant_id` (A corpus) into Neo4j, or write its files only if `settings` is None.

    Writes `neo4jplant/<id>/ingest.json` and, once, `cypcorp/plant_lines/<id>/ingest.json`.
    Returns the path of the loaded plant's `ingest.json`.

    Raises:
        ValueError: the loaded plant has another sheet count than the built one.
    """
    from plantgraph.ingest.__main__ import _write_result  # the frozen writer, not a copy

    record = json.loads((root / "corpora" / plant_id / INGEST_FILE).read_text(encoding="utf-8"))
    config = GeneratorConfigV22.model_validate(record["config"]["generator"])
    measurement = StoreMeasurement(fresh_database=True) if settings else NO_MEASUREMENT
    result = run_synthetic(
        corpus_id=plant_id,
        generator_config=config,
        split_config=HeadlinePresetV22().split_config(config.seed),
        check=False,
        settings=settings,
        store_profile=PROFILE,
        measurement=measurement,
    )
    out_dir = root / "neo4jplant" / plant_id
    shutil.rmtree(out_dir, ignore_errors=True)
    _write_result(result, out_dir)
    keep_cypher_copy(root, plant_id)
    require_loaded_matches(root, plant_id)
    return out_dir / INGEST_FILE


def keep_cypher_copy(root: Path, plant_id: str) -> None:
    """Copy the loaded plant's `ingest.json` to `cypcorp/plant_lines/<id>/` unless it is there."""
    target = root / CYPCORP / plant_id / INGEST_FILE
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "neo4jplant" / plant_id / INGEST_FILE, target)


def _n_sheets(path: Path) -> int:
    return int(json.loads(path.read_text(encoding="utf-8"))["counts"]["n_sheets"])


def require_loaded_matches(root: Path, plant_id: str) -> None:
    """The loaded plant has the built plant's sheet count.

    Raises:
        ValueError: the two counts differ.
    """
    built = _n_sheets(root / "corpora" / plant_id / INGEST_FILE)
    loaded = _n_sheets(root / "neo4jplant" / plant_id / INGEST_FILE)
    if built != loaded:
        raise ValueError(f"expected the loaded {plant_id} to have {built} sheets, found {loaded}")


def relabel_top_level_id(text: str, from_id: str, to_id: str) -> str:
    """The kept copy's text with only its top-level `corpus_id` changed.

    After a real Neo4j load the kept copy also holds a `load_report` that names A's corpus; that
    report records the A load and stays as it is. The top-level field is the file's first key.

    Raises:
        ValueError: the file does not start with the expected top-level field.
    """
    field = f'"corpus_id": "{from_id}"'
    head = text.find(field)
    if head < 0 or text[:head].strip() != "{":
        raise ValueError(f"expected the ingest file to start with {field}, found it elsewhere")
    return text[:head] + f'"corpus_id": "{to_id}"' + text[head + len(field) :]


def prepare_b_load(root: Path, plant_id: str) -> Path:
    """Make `cypcorp/plant_lines/<id>B/`: the relabel of A's kept copy plus the positions file.

    The positions file's sha256 must equal the one `corpus_b.json` recorded at build.

    Raises:
        ValueError: the positions file differs from the recorded one.
        FileNotFoundError: the plant was not built or loaded first.
    """
    b_id = b_id_of(plant_id)
    a_copy = root / CYPCORP / plant_id / INGEST_FILE
    b_dir = root / CYPCORP / b_id
    b_dir.mkdir(parents=True, exist_ok=True)
    text = a_copy.read_bytes().decode("utf-8")
    (b_dir / INGEST_FILE).write_bytes(relabel_top_level_id(text, plant_id, b_id).encode("utf-8"))
    built = root / "corpora" / b_id
    shutil.copyfile(built / POSITIONS_FILE_NAME, b_dir / POSITIONS_FILE_NAME)
    recorded = json.loads((built / CORPUS_B_FILE).read_text(encoding="utf-8"))["positions_sha256"]
    if sha256_of_file(b_dir / POSITIONS_FILE_NAME) != recorded:
        raise ValueError(f"expected the positions file of {b_id} to hash as corpus_b.json says")
    return b_dir
