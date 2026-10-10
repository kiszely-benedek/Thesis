"""Memory readings: size parsing, the page cache estimate, and the process peak."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.infra.process_memory import (
    PAGE_CACHE_RATIO_FILE,
    PAGE_CACHE_SIZE_SETTING,
    neo4j_rss_bytes,
    page_cache_used_bytes,
    parse_size_bytes,
    process_peak_bytes,
)
from plantgraph.infra.store_size import read_last_value


@pytest.mark.parametrize(
    ("text", "expected"),
    [("512", 512), ("512m", 512 * 1024**2), ("4g", 4 * 1024**3), ("4.00GiB", 4 * 1024**3)],
)
def test_parse_size_bytes_reads_neo4j_units(text: str, expected: int) -> None:
    assert parse_size_bytes(text) == expected


def test_parse_size_bytes_refuses_text_that_is_not_a_size() -> None:
    with pytest.raises(ValueError, match="expected a size"):
        parse_size_bytes("lots")


def test_last_value_keeps_the_fraction(tmp_path: Path) -> None:
    csv = tmp_path / "ratio.csv"
    csv.write_text("t,value\n1,0.1\n2,0.25\n", encoding="utf-8")
    assert read_last_value(csv) == 0.25


def test_page_cache_used_is_ratio_times_configured_size(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / PAGE_CACHE_RATIO_FILE).write_text("t,value\n1,0.5\n", encoding="utf-8")
    settings = {PAGE_CACHE_SIZE_SETTING: "2g"}
    assert page_cache_used_bytes(tmp_path, settings) == 1024**3


def test_page_cache_used_is_none_without_metrics_or_setting(tmp_path: Path) -> None:
    assert page_cache_used_bytes(tmp_path, {PAGE_CACHE_SIZE_SETTING: "2g"}) is None
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / PAGE_CACHE_RATIO_FILE).write_text("t,value\n1,0.5\n", encoding="utf-8")
    assert page_cache_used_bytes(tmp_path, {}) is None


def test_process_peak_is_a_positive_number_of_bytes() -> None:
    assert process_peak_bytes() > 1_000_000  # an interpreter with pytest loaded is megabytes


def test_neo4j_rss_is_none_or_positive() -> None:
    rss = neo4j_rss_bytes()
    assert rss is None or rss > 0
