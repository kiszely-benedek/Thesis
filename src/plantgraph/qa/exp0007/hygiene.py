"""Sealed-test hygiene checks (EXP-0007 plan section 9): seeds and the Neo4j target.

Two ways a paid or generating script could do damage unnoticed: building a test plant twice or
after its seed leaked into a record, and pointing a load at the user's own Neo4j database.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from plantgraph.ingest.headline_v2 import TEST_SEED_RANGE, TEST_SEEDS_V2

#: The registered test seeds (ADR-0059, written down before any test plant was generated).
REGISTERED_TEST_SEEDS_V2 = {1: 5100, 3: 5001, 10: 5001, 30: 5001, 100: 5002, 1000: 5003}
#: The user's own plant database; a script may only touch it when told so explicitly.
PLANT_DATABASE = "neo4j"
_DATABASE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9.-]*")


def assert_registered_seeds() -> None:
    """Raise unless `TEST_SEEDS_V2` is exactly the registered table.

    Raises:
        ValueError: the code's table differs from the registered one.
    """
    if TEST_SEEDS_V2 != REGISTERED_TEST_SEEDS_V2:
        raise ValueError(
            f"expected TEST_SEEDS_V2 == {REGISTERED_TEST_SEEDS_V2} (ADR-0059), "
            f"found {TEST_SEEDS_V2}"
        )


def generator_seed_of(ingest_json: Path) -> int | None:
    """The generator seed an `ingest.json` records (`None` for a Proteus import)."""
    config = json.loads(ingest_json.read_text(encoding="utf-8")).get("config", {})
    seed = config.get("generator", {}).get("seed")
    return seed if isinstance(seed, int) else None


def find_leaked_test_seeds(ingest_files: Iterable[Path]) -> dict[Path, int]:
    """The ingest records whose seed lies in the reserved test range (5000-5999)."""
    leaked = {}
    for path in ingest_files:
        seed = generator_seed_of(path)
        if seed is not None and seed in TEST_SEED_RANGE:
            leaked[path] = seed
    return leaked


def ingest_files_outside(data_root: Path, excluded: Path) -> list[Path]:
    """Every `ingest.json` under `data_root` except those under `excluded` (the run's own data)."""
    excluded_resolved = excluded.resolve()
    return [
        p
        for p in sorted(data_root.rglob("ingest.json"))
        if excluded_resolved not in p.resolve().parents
    ]


def require_no_leaked_seeds(data_root: Path, excluded: Path) -> None:
    """Raise if a test seed already appears in an earlier record (ADR-0059's revisit trigger).

    Raises:
        ValueError: names the records and seeds found.
    """
    leaked = find_leaked_test_seeds(ingest_files_outside(data_root, excluded))
    if leaked:
        raise ValueError(
            f"expected no seed in {TEST_SEED_RANGE.start}-{TEST_SEED_RANGE.stop - 1} in earlier "
            f"records, found {', '.join(f'{p} (seed {s})' for p, s in leaked.items())}"
        )


def require_database(name: str | None, is_plant_database: bool) -> str:
    """The Neo4j database a script may load into; the plant database only on explicit say-so.

    Raises:
        ValueError: no name, a malformed name, or `neo4j` without `is_plant_database`.
    """
    if not name:
        raise ValueError("expected a Neo4j database name (E7_NEO4J_DATABASE), found none")
    if not _DATABASE_NAME.fullmatch(name):
        raise ValueError(f"expected a plain database name (letters, digits, . -), found {name!r}")
    if name == PLANT_DATABASE and not is_plant_database:
        raise ValueError(
            f"refusing the user's plant database {PLANT_DATABASE!r}: pick a temporary database, "
            "or set E7_TARGET_IS_PLANT_DB=yes when this really is the target"
        )
    return name
