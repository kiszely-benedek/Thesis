"""`seed-cache`: merge response caches into one file for the demo, never touching the sources.

The experiment runs stored every model reply in a sqlite `responses` table, keyed by a hash of the
request. Replaying a question in the demo is free only if its key is in the demo's cache, so this
command unions the experiment cache with the older demo cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from pydantic import BaseModel

_CREATE_TABLE = "CREATE TABLE responses (key TEXT PRIMARY KEY, response_json TEXT NOT NULL)"


class SourceProvenance(BaseModel):
    """One merged-in cache file: where it is, its content hash and how many rows it held."""

    path: str
    sha256: str
    rows: int
    rows_written: int


class SeedProvenance(BaseModel):
    """What `seed-cache` wrote; saved next to the output as `<out>.provenance.json`."""

    out: str
    date: str
    sources: list[SourceProvenance]
    rows_written: int
    rows_skipped_duplicate: int


def build_seed_parser(prog: str = "seed-cache") -> argparse.ArgumentParser:
    """The `seed-cache` command line: one or more `--from` sources and one `--out`."""
    parser = argparse.ArgumentParser(
        prog=prog, description="Union response caches into a new file."
    )
    parser.add_argument(
        "--from",
        dest="sources",
        type=Path,
        action="append",
        required=True,
        help="a source cache; repeat it. On a duplicate key the earlier --from wins",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="the new cache file (must not exist)"
    )
    return parser


def seed_cache(sources: Sequence[Path], out: Path) -> SeedProvenance:
    """Copy every source's `responses` into a new `out`; the first source wins on a key clash."""
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}: pass a --out path that does not exist")
    missing = [path for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"source cache(s) not found: {[str(p) for p in missing]}")

    out.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(out)
    try:
        target.execute(_CREATE_TABLE)
        source_records = [_merge_source(target, path) for path in sources]
        target.commit()
    finally:
        target.close()

    written = sum(record.rows_written for record in source_records)
    total = sum(record.rows for record in source_records)
    provenance = SeedProvenance(
        out=str(out),
        date=date.today().isoformat(),
        sources=source_records,
        rows_written=written,
        rows_skipped_duplicate=total - written,
    )
    provenance_path = out.with_name(out.name + ".provenance.json")
    provenance_path.write_text(provenance.model_dump_json(indent=2), encoding="utf-8")
    return provenance


def _merge_source(target: sqlite3.Connection, path: Path) -> SourceProvenance:
    """Insert one source's rows into `target`, skipping keys already there."""
    before = _count(target)
    # Read-only URI: the old demo cache may be open in the running server.
    source = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = source.execute("SELECT key, response_json FROM responses").fetchall()
    finally:
        source.close()
    # INSERT OR IGNORE: the same key is the same request, so the earlier source's reply stays.
    target.executemany("INSERT OR IGNORE INTO responses (key, response_json) VALUES (?, ?)", rows)
    return SourceProvenance(
        path=str(path),
        sha256=_sha256(path),
        rows=len(rows),
        rows_written=_count(target) - before,
    )


def _count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM responses").fetchone()
    return int(row[0])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_seed_cache(argv: Sequence[str]) -> None:
    """Entry point for `python -m plantgraph.demo.app seed-cache ...`; prints the provenance."""
    args = build_seed_parser().parse_args(argv)
    provenance = seed_cache(args.sources, args.out)
    print(json.dumps(provenance.model_dump(), indent=2))
