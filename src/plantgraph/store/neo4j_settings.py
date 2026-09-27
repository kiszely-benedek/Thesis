"""Where to find the Neo4j database and how to authenticate (design `kg-construction.md` §7.4).

Real environment variables always win. A `.env` file at the repository root
(git-ignored, read with `python-dotenv`) fills in whatever is still missing,
so a developer does not have to export four variables in every shell before
running the opt-in integration test. Nothing here ever prints or logs the
password: it is a Pydantic `SecretStr`, masked in `repr` and `str`, and its
raw value is only ever read once, by `neo4j_loader.py`, to authenticate.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr

#: `neo4j_settings.py` -> `store` -> `plantgraph` -> `src` -> repository root.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

_URI_VAR = "NEO4J_URI"
_USERNAME_VAR = "NEO4J_USERNAME"
_PASSWORD_VAR = "NEO4J_PASSWORD"
_DATABASE_VAR = "NEO4J_DATABASE"
_DEFAULT_DATABASE = "neo4j"

#: order matters only for the skip/error message, which lists them as found here.
_REQUIRED_VARS = (_URI_VAR, _USERNAME_VAR, _PASSWORD_VAR)


class Neo4jSettings(BaseModel):
    """Connection settings for one Neo4j database."""

    model_config = ConfigDict(frozen=True)

    uri: str
    username: str
    password: SecretStr
    database: str = _DEFAULT_DATABASE


def missing_required_vars() -> list[str]:
    """Which of `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD` are still unset.

    Loads `.env` first (without overriding real environment variables), so the
    answer reflects both sources — this is what lets a skipped integration
    test name the exact variable the user still needs to set.
    """
    load_dotenv(_ENV_FILE, override=False)
    return [name for name in _REQUIRED_VARS if not os.environ.get(name)]


def from_env() -> Neo4jSettings | None:
    """Build settings from the environment, falling back to `.env` for what is missing.

    Returns:
        `None` if `NEO4J_URI`, `NEO4J_USERNAME` or `NEO4J_PASSWORD` is still
        unset after `.env` is loaded. `NEO4J_DATABASE` defaults to `"neo4j"`.
    """
    if missing_required_vars():
        return None
    return Neo4jSettings(
        uri=os.environ[_URI_VAR],
        username=os.environ[_USERNAME_VAR],
        password=SecretStr(os.environ[_PASSWORD_VAR]),
        database=os.environ.get(_DATABASE_VAR, _DEFAULT_DATABASE),
    )
