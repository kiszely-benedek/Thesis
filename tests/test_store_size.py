"""`infra/store_size.py`: disk sizes and metrics CSVs, on a temporary directory tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.infra.store_size import build_footprint, directory_bytes, read_last_metric
from plantgraph.store.neo4j_loader import StoreCounts


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_directory_bytes_sums_nested_files(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", 10)
    _write(tmp_path / "sub" / "b.bin", 5)
    assert directory_bytes(tmp_path) == 15


def test_directory_bytes_rejects_a_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="expected a directory"):
        directory_bytes(tmp_path / "nope")


def test_read_last_metric_takes_the_last_row(tmp_path: Path) -> None:
    csv = tmp_path / "m.csv"
    csv.write_text("t,value\n1,100\n2,200.0\n", encoding="utf-8")
    assert read_last_metric(csv) == 200


def test_read_last_metric_is_none_without_file_or_samples(tmp_path: Path) -> None:
    assert read_last_metric(tmp_path / "missing.csv") is None
    header_only = tmp_path / "h.csv"
    header_only.write_text("t,value\n", encoding="utf-8")
    assert read_last_metric(header_only) is None


def test_build_footprint_keeps_store_and_transaction_logs_apart(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "databases" / "neo4j" / "store", 100)
    _write(tmp_path / "data" / "transactions" / "neo4j" / "log", 7)
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "neo4j.database.neo4j.store.size.database.csv").write_text(
        "t,value\n1,90\n", encoding="utf-8"
    )
    counts = StoreCounts(n_nodes=3, n_relationships=2, n_properties=11)

    footprint = build_footprint("neo4j", tmp_path, counts, fresh_database=True)

    assert (footprint.data_bytes, footprint.tx_log_bytes) == (100, 7)
    assert footprint.metrics_store_bytes == 90
    assert footprint.metrics_reserved_bytes is None  # that metric file is absent
    assert (footprint.n_nodes, footprint.n_relationships, footprint.n_properties) == (3, 2, 11)
    assert footprint.fresh_database is True
