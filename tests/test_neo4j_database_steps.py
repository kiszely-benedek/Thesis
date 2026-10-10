"""`recreate_database`, `checkpoint`, `count_store`, `read_memory_settings` against a fake driver.

The real server is not touched: the fakes record the commands and answer canned rows.
"""

from __future__ import annotations

from typing import Any

import pytest
from neo4j.exceptions import ClientError
from pydantic import SecretStr

from plantgraph.store import neo4j_loader
from plantgraph.store.neo4j_loader import (
    DatabaseRecreationRefused,
    checkpoint,
    count_store,
    read_memory_settings,
    recreate_database,
)
from plantgraph.store.neo4j_settings import Neo4jSettings


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def consume(self) -> None:
        return None

    def data(self) -> list[dict[str, Any]]:
        return self._rows

    def single(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, driver: _FakeDriver, database: str) -> None:
        self._driver = driver
        self.database = database

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def run(self, query: str) -> _FakeResult:
        self._driver.calls.append((self.database, query))
        if self._driver.error is not None:
            raise self._driver.error
        return _FakeResult(self._driver.rows_for(query))

    def execute_read(self, work: Any, *args: Any) -> Any:
        return work(self, *args)


class _FakeDriver:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error = error
        self.closed = False

    def rows_for(self, query: str) -> list[dict[str, Any]]:
        if "server.memory" in query:
            return [{"name": "server.memory.heap.max_size", "value": "1G"}]
        if "()-[e]->()" in query:
            return [{"n": 2, "p": 5}]
        return [{"n": 3, "p": 7}]

    def session(self, database: str) -> _FakeSession:
        return _FakeSession(self, database)

    def close(self) -> None:
        self.closed = True


def _settings(database: str = "neo4j") -> Neo4jSettings:
    return Neo4jSettings(uri="bolt://x", username="u", password=SecretStr("p"), database=database)


def _install(monkeypatch: pytest.MonkeyPatch, driver: _FakeDriver) -> None:
    monkeypatch.setattr(neo4j_loader, "_open_driver", lambda settings: driver)


def test_recreate_runs_create_or_replace_on_the_system_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _FakeDriver()
    _install(monkeypatch, driver)
    recreate_database(_settings("neo4j"))
    assert driver.calls == [("system", "CREATE OR REPLACE DATABASE `neo4j` WAIT")]
    assert driver.closed


def test_recreate_refusal_names_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = _FakeDriver(error=ClientError("not allowed"))
    _install(monkeypatch, driver)
    with pytest.raises(DatabaseRecreationRefused, match="wipe_all_neo4j.py"):
        recreate_database(_settings())
    assert driver.closed


def test_recreate_rejects_a_database_name_that_could_inject_cypher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _FakeDriver()
    _install(monkeypatch, driver)
    with pytest.raises(ValueError, match="plain Neo4j database name"):
        recreate_database(_settings("neo4j` DROP"))
    assert driver.calls == []


def test_checkpoint_runs_on_the_target_database(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = _FakeDriver()
    _install(monkeypatch, driver)
    checkpoint(_settings("plant"))
    assert driver.calls == [("plant", "CALL db.checkpoint()")]


def test_count_store_adds_node_and_relationship_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _FakeDriver())
    counts = count_store(_settings())
    assert (counts.n_nodes, counts.n_relationships, counts.n_properties) == (3, 2, 12)


def test_read_memory_settings_maps_name_to_value(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _FakeDriver())
    assert read_memory_settings(_settings()) == {"server.memory.heap.max_size": "1G"}
