"""The A build equals the frozen CLI's; the B corpus is a byte-exact relabel (design §19.12 3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from exp0009_small import SEED, built_small

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009 import build
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME


def _without_timings(path: Path) -> dict[str, object]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record.pop("stage_seconds", None)
    # the plan fixes each document's flag explicitly; the CLI leaves it to the plant's own draw
    record["config"]["generator"]["handbook"].pop("document_untagged", None)
    return record  # type: ignore[no-any-return]


def test_a_build_equals_the_frozen_cli(tmp_path: Path) -> None:
    spec, root, _record = built_small()
    command = [
        sys.executable, "-m", "plantgraph.ingest", "synthetic", "--headline-v2",
        "--generator", "v2.2", "--n-units", str(spec.n_units), "--seed", str(SEED),
        "--corpus-id", spec.plant_id, "--check", "--no-neo4j", "--out", str(tmp_path),
    ]  # fmt: skip
    subprocess.run(command, check=True, capture_output=True)
    assert _without_timings(tmp_path / "ingest.json") == _without_timings(
        root / spec.plant_id / "ingest.json"
    )
    assert (tmp_path / "rules.json").read_bytes() == (
        root / spec.plant_id / "rules.json"
    ).read_bytes()


def test_b_file_is_a_byte_exact_relabel_with_a_positions_hash() -> None:
    spec, root, record = built_small()
    build.require_relabel_equal(
        root / spec.plant_id / "ingest.json", root / spec.b_id / "ingest.json"
    )
    assert record.positions_sha256 == build.sha256_of_file(root / spec.b_id / POSITIONS_FILE_NAME)
    assert sum(record.positions_per_code.values()) > 0
    stored = json.loads((root / spec.b_id / build.CORPUS_B_FILE).read_text(encoding="utf-8"))
    assert stored["positions_sha256"] == record.positions_sha256


def test_the_b_corpus_loads_with_the_a_counts() -> None:
    spec, root, _record = built_small()
    a = load_corpus_artifacts(spec.plant_id, root / spec.plant_id / "ingest.json")
    b = load_corpus_artifacts(spec.b_id, root / spec.b_id / "ingest.json")
    assert (len(a.localized_sheets), len(a.load_plan.node_statements)) == (
        len(b.localized_sheets),
        len(b.load_plan.node_statements),
    )


def test_a_tampered_b_file_fails_the_byte_test() -> None:
    spec, root, _record = built_small()
    b_file = root / spec.b_id / "ingest.json"
    original = b_file.read_bytes()
    try:
        b_file.write_bytes(original.replace(b'"n_sheets"', b'"n_sheets_"', 1))
        with pytest.raises(ValueError, match="difference"):
            build.require_relabel_equal(root / spec.plant_id / "ingest.json", b_file)
    finally:
        b_file.write_bytes(original)


def test_a_build_refuses_an_existing_folder_and_an_undrawn_test_seed(tmp_path: Path) -> None:
    spec, root, _record = built_small()
    with pytest.raises(FileExistsError):
        build.build_plant(spec, root, None)
    undrawn = spec.model_copy(update={"seed": 5001})
    with pytest.raises(ValueError, match="drawn seed plan|retired"):
        build.build_a(undrawn, tmp_path, None)
