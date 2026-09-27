"""`Neo4jSettings.from_env` — no Neo4j driver, no live database (design §7.7).

Every test points `_ENV_FILE` at a throwaway path with `monkeypatch`, never at
the repository's real `.env`: that file holds this machine's actual Neo4j
credentials, and a unit test must not read them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from plantgraph.store import neo4j_settings
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env, missing_required_vars

_ALL_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")


@pytest.fixture(autouse=True)
def _isolated_neo4j_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Start every test with a clean environment and a `.env` file that does not exist.

    `load_dotenv` writes straight into `os.environ`, which `monkeypatch` only
    reverts for keys it changed itself — so a test that lets `.env` populate a
    variable must also be cleaned up manually afterwards, not just relied on
    `monkeypatch` to undo.
    """
    for name in _ALL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(neo4j_settings, "_ENV_FILE", tmp_path / ".env")
    yield
    for name in _ALL_VARS:
        os.environ.pop(name, None)


def _write_dotenv(path: Path, **values: str) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))


def test_from_env_is_none_when_every_required_variable_is_absent() -> None:
    assert from_env() is None


def test_missing_required_vars_names_exactly_the_absent_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")

    assert missing_required_vars() == ["NEO4J_PASSWORD"]


def test_dotenv_file_fills_in_what_the_environment_is_missing() -> None:
    _write_dotenv(
        neo4j_settings._ENV_FILE,
        NEO4J_URI="neo4j://dotenv-host:7687",
        NEO4J_USERNAME="dotenv-user",
        NEO4J_PASSWORD="dotenv-password",
    )

    settings = from_env()

    assert settings is not None
    assert settings.uri == "neo4j://dotenv-host:7687"
    assert settings.username == "dotenv-user"
    assert settings.password.get_secret_value() == "dotenv-password"
    assert settings.database == "neo4j", "NEO4J_DATABASE absent -> default"


def test_a_real_environment_variable_overrides_the_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_dotenv(
        neo4j_settings._ENV_FILE,
        NEO4J_URI="neo4j://dotenv-host:7687",
        NEO4J_USERNAME="dotenv-user",
        NEO4J_PASSWORD="dotenv-password",
    )
    monkeypatch.setenv("NEO4J_URI", "neo4j://real-env-host:7687")

    settings = from_env()

    assert settings is not None
    assert settings.uri == "neo4j://real-env-host:7687"
    assert settings.username == "dotenv-user", "still filled in from .env"


def test_neo4j_database_var_overrides_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "hunter2")
    monkeypatch.setenv("NEO4J_DATABASE", "plantgraph-test")

    settings = from_env()

    assert settings is not None
    assert settings.database == "plantgraph-test"


def test_password_never_appears_in_repr_or_str() -> None:
    settings = Neo4jSettings(uri="neo4j://127.0.0.1:7687", username="neo4j", password="hunter2")

    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings)
