"""`OpenRouterSettings.from_env` — no network, no real key (design `qa-system.md` §6).

Every test points `_ENV_FILE` at a throwaway path with `monkeypatch`, never at
the repository's real `.env`: that file holds this machine's actual
OpenRouter key, and a unit test must not read it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from plantgraph.llm import openrouter_settings
from plantgraph.llm.openrouter_settings import OpenRouterSettings, from_env, missing_required_vars

_ALL_VARS = ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL")


@pytest.fixture(autouse=True)
def _isolated_openrouter_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Start every test with a clean environment and a `.env` file that does not exist.

    `load_dotenv` writes straight into `os.environ`, which `monkeypatch` only
    reverts for keys it changed itself — so a test that lets `.env` populate a
    variable must also be cleaned up manually afterwards, not just relied on
    `monkeypatch` to undo (mirrors `tests/test_neo4j_settings.py`).
    """
    for name in _ALL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(openrouter_settings, "_ENV_FILE", tmp_path / ".env")
    yield
    for name in _ALL_VARS:
        os.environ.pop(name, None)


def _write_dotenv(path: Path, **values: str) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))


def test_from_env_is_none_when_the_key_is_absent() -> None:
    assert from_env() is None


def test_missing_required_vars_names_the_key() -> None:
    assert missing_required_vars() == ["OPENROUTER_API_KEY"]


def test_dotenv_file_fills_in_the_key() -> None:
    _write_dotenv(openrouter_settings._ENV_FILE, OPENROUTER_API_KEY="sk-or-DOTENV-KEY")

    settings = from_env()

    assert settings is not None
    assert settings.api_key.get_secret_value() == "sk-or-DOTENV-KEY"
    # OPENROUTER_BASE_URL is absent here, so this must be the default.
    assert settings.base_url == "https://openrouter.ai/api/v1"


def test_a_real_environment_variable_overrides_the_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_dotenv(openrouter_settings._ENV_FILE, OPENROUTER_API_KEY="sk-or-DOTENV-KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-REAL-ENV-KEY")

    settings = from_env()

    assert settings is not None
    assert settings.api_key.get_secret_value() == "sk-or-REAL-ENV-KEY"


def test_base_url_var_overrides_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-REAL-ENV-KEY")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.invalid/v1")

    settings = from_env()

    assert settings is not None
    assert settings.base_url == "https://example.invalid/v1"


def test_api_key_never_appears_in_repr_or_str() -> None:
    settings = OpenRouterSettings(api_key="sk-or-TEST-SECRET")

    assert "sk-or-TEST-SECRET" not in repr(settings)
    assert "sk-or-TEST-SECRET" not in str(settings)
