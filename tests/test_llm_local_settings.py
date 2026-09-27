"""`LocalLLMSettings.from_env` — optional backend, no runtime installed (design `qa-system.md` §6).

Every test points `_ENV_FILE` at a throwaway path with `monkeypatch`, never
at the repository's real `.env`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from plantgraph.llm import local_settings
from plantgraph.llm.local_settings import from_env

_VAR = "LOCAL_LLM_BASE_URL"


@pytest.fixture(autouse=True)
def _isolated_local_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.delenv(_VAR, raising=False)
    monkeypatch.setattr(local_settings, "_ENV_FILE", tmp_path / ".env")
    yield
    os.environ.pop(_VAR, None)


def _write_dotenv(path: Path, **values: str) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))


def test_from_env_is_none_when_unset() -> None:
    # Unlike OpenRouter's key, an absent local backend is not an error: no
    # coder task depends on it (§6, no local runtime is installed here).
    assert from_env() is None


def test_dotenv_file_fills_in_the_base_url() -> None:
    _write_dotenv(local_settings._ENV_FILE, LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1")

    settings = from_env()

    assert settings is not None
    assert settings.base_url == "http://127.0.0.1:11434/v1"


def test_a_real_environment_variable_overrides_the_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_dotenv(local_settings._ENV_FILE, LOCAL_LLM_BASE_URL="http://dotenv:1234/v1")
    monkeypatch.setenv(_VAR, "http://real-env:1234/v1")

    settings = from_env()

    assert settings is not None
    assert settings.base_url == "http://real-env:1234/v1"
