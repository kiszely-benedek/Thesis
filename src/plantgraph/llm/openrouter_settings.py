"""Where to find OpenRouter and how to authenticate (design `qa-system.md` §6).

**OpenRouter** is a hosted gateway that exposes many providers' language
models through one OpenAI-compatible HTTP API; this project talks to it
instead of calling any single model vendor directly. Follows the exact
env-then-`.env` rule as `store/neo4j_settings.py`: real environment
variables win, and a git-ignored `.env` file at the repository root fills in
whatever is still missing. The API key is a Pydantic `SecretStr` and its
value is read only once, inside `client.py`, to authenticate a call — it
never appears in `repr`, `str`, a log line or the cache (§6).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr

#: `openrouter_settings.py` -> `llm` -> `plantgraph` -> `src` -> repository root.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

_API_KEY_VAR = "OPENROUTER_API_KEY"
_BASE_URL_VAR = "OPENROUTER_BASE_URL"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

_REQUIRED_VARS = (_API_KEY_VAR,)


class OpenRouterSettings(BaseModel):
    """Connection settings for the OpenRouter chat and embeddings API."""

    model_config = ConfigDict(frozen=True)

    api_key: SecretStr
    base_url: str = _DEFAULT_BASE_URL


def missing_required_vars() -> list[str]:
    """Which of the required OpenRouter variables are still unset.

    Loads `.env` first (without overriding real environment variables), so
    the answer reflects both sources — this is what lets a skipped live test
    name the exact variable the user still needs to set.
    """
    load_dotenv(_ENV_FILE, override=False)
    return [name for name in _REQUIRED_VARS if not os.environ.get(name)]


def from_env() -> OpenRouterSettings | None:
    """Build settings from the environment, falling back to `.env` for what is missing.

    Returns:
        `None` if `OPENROUTER_API_KEY` is still unset after `.env` is
        loaded. `OPENROUTER_BASE_URL` defaults to OpenRouter's own
        OpenAI-compatible endpoint.
    """
    if missing_required_vars():
        return None
    return OpenRouterSettings(
        api_key=SecretStr(os.environ[_API_KEY_VAR]),
        base_url=os.environ.get(_BASE_URL_VAR, _DEFAULT_BASE_URL),
    )
