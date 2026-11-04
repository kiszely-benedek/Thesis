"""Read an identity-link file (EXP-0004) and pin it by hash, so a rebuild cannot use another one.

An `IdentityLinkSet` is the output of a pair decider: which differently written tags are the same
item. A corpus loaded with links is only reproducible if the links are the same, so `ingest.json`
records the file's path and sha256 (`IdentityFileRecord`), and a rebuild checks the hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.resolution.identity_links import IdentityLinkSet


class IdentityFileRecord(BaseModel):
    """The `config.identity` entry of `ingest.json`: where the links came from, and their hash."""

    model_config = ConfigDict(frozen=True)

    path: str
    sha256: str


def read_identity_links(path: Path) -> tuple[IdentityLinkSet, IdentityFileRecord]:
    """Parse the link file at `path`; return the links and the record to store in `ingest.json`.

    Raises:
        ValueError: the file is missing or is not an `IdentityLinkSet` as JSON.
    """
    if not path.is_file():
        raise ValueError(f"expected an identity-link file at {path}, found none")
    raw = path.read_bytes()
    try:
        links = IdentityLinkSet.model_validate_json(raw)
    except ValueError as error:
        raise ValueError(f"expected {path} to hold an IdentityLinkSet as JSON: {error}") from error
    return links, IdentityFileRecord(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def read_recorded_identity_links(record: IdentityFileRecord) -> IdentityLinkSet:
    """Re-read the file a past run recorded; refuse it if its hash is no longer the recorded one.

    Raises:
        ValueError: the file changed since the run (or is gone).
    """
    links, current = read_identity_links(Path(record.path))
    if current.sha256 != record.sha256:
        raise ValueError(
            f"expected identity-link file {record.path} to have sha256 {record.sha256}, "
            f"found {current.sha256}: the links changed since this corpus was ingested"
        )
    return links
