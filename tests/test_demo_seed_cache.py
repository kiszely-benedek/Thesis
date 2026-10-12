"""Tests for the demo's `seed-cache` command, on toy sqlite files."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from plantgraph.demo.app.seed_cache import SeedProvenance, seed_cache


def _make_cache(path: Path, rows: dict[str, str]) -> Path:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE responses (key TEXT PRIMARY KEY, response_json TEXT NOT NULL)")
    connection.executemany("INSERT INTO responses VALUES (?, ?)", rows.items())
    connection.commit()
    connection.close()
    return path


def _read_all(path: Path) -> dict[str, str]:
    connection = sqlite3.connect(path)
    try:
        return dict(connection.execute("SELECT key, response_json FROM responses").fetchall())
    finally:
        connection.close()


def test_union_of_sources(tmp_path: Path) -> None:
    first = _make_cache(tmp_path / "a.sqlite", {"k1": "a1", "k2": "a2"})
    second = _make_cache(tmp_path / "b.sqlite", {"k3": "b3"})
    out = tmp_path / "out.sqlite"
    seed_cache([first, second], out)
    assert _read_all(out) == {"k1": "a1", "k2": "a2", "k3": "b3"}


def test_first_source_wins_on_duplicate_key(tmp_path: Path) -> None:
    first = _make_cache(tmp_path / "a.sqlite", {"k1": "from-first"})
    second = _make_cache(tmp_path / "b.sqlite", {"k1": "from-second", "k2": "b2"})
    out = tmp_path / "out.sqlite"
    seed_cache([first, second], out)
    assert _read_all(out) == {"k1": "from-first", "k2": "b2"}


def test_refuses_existing_output(tmp_path: Path) -> None:
    source = _make_cache(tmp_path / "a.sqlite", {"k1": "a1"})
    out = _make_cache(tmp_path / "out.sqlite", {"keep": "me"})
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        seed_cache([source], out)
    assert _read_all(out) == {"keep": "me"}


def test_missing_source_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        seed_cache([tmp_path / "nope.sqlite"], tmp_path / "out.sqlite")


def test_sources_are_opened_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _make_cache(tmp_path / "a.sqlite", {"k1": "a1"})
    before = source.read_bytes()
    opened: list[str] = []
    real_connect: Any = sqlite3.connect

    def spy(database: str, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        opened.append(str(database))
        connection: sqlite3.Connection = real_connect(database, *args, **kwargs)
        return connection

    monkeypatch.setattr(sqlite3, "connect", spy)
    seed_cache([source], tmp_path / "out.sqlite")
    source_uris = [name for name in opened if "a.sqlite" in name]
    assert source_uris and all("mode=ro" in name for name in source_uris)
    assert source.read_bytes() == before


def test_provenance_counts_and_file(tmp_path: Path) -> None:
    first = _make_cache(tmp_path / "a.sqlite", {"k1": "a1", "k2": "a2"})
    second = _make_cache(tmp_path / "b.sqlite", {"k2": "b2", "k3": "b3", "k4": "b4"})
    out = tmp_path / "out.sqlite"
    provenance = seed_cache([first, second], out)

    assert provenance.rows_written == 4
    assert provenance.rows_skipped_duplicate == 1
    assert [(s.rows, s.rows_written) for s in provenance.sources] == [(2, 2), (3, 2)]
    assert provenance.sources[0].sha256 == hashlib.sha256(first.read_bytes()).hexdigest()

    saved = tmp_path / "out.sqlite.provenance.json"
    assert (
        SeedProvenance.model_validate(json.loads(saved.read_text(encoding="utf-8"))) == provenance
    )
