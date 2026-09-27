"""Where a local OpenAI-compatible LLM server would be reached (design `qa-system.md` §6).

Kept alongside `openrouter_settings.py` because `ModelPin.backend` keeps a
`"local"` option: a self-hosted model server for development, reached at
this base URL instead of OpenRouter's. **No coder task depends on it** — a
read-only check of this machine (2026-09-26) found no local LLM runtime
installed (no `ollama`, no LM Studio, nothing answering on the usual local
ports), so this module exists only so a future contributor can plug one in
without touching `client.py`. Same env-then-`.env` rule as
`store/neo4j_settings.py`, but with nothing required: a local backend is
optional, not a missing credential.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

#: `local_settings.py` -> `llm` -> `plantgraph` -> `src` -> repository root.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

_BASE_URL_VAR = "LOCAL_LLM_BASE_URL"


class LocalLLMSettings(BaseModel):
    """Connection settings for a local, OpenAI-compatible model server."""

    model_config = ConfigDict(frozen=True)

    base_url: str


def from_env() -> LocalLLMSettings | None:
    """Build settings from the environment, falling back to `.env` for what is missing.

    Returns:
        `None` if `LOCAL_LLM_BASE_URL` is unset in both the environment and
        `.env` — this backend is optional, unlike OpenRouter's key.
    """
    load_dotenv(_ENV_FILE, override=False)
    base_url = os.environ.get(_BASE_URL_VAR)
    if base_url is None:
        return None
    return LocalLLMSettings(base_url=base_url)
