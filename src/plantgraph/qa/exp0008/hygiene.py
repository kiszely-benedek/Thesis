"""Which seeds the first measurement used, so that none is a test seed again (ADR-0065).

`RETIRED_TEST_SEEDS` is the registered core. This module adds every test-range seed that any record
under `data/runs` carries, because a plant built from such a seed has been looked at already.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from plantgraph.ingest.seed_plan import RETIRED_TEST_SEEDS, TEST_SEED_RANGE

#: `"seed": 5003`, `"sample_seed":5002` ... but not `"seed_chars": 5270`
_SEED_FIELD = re.compile(r'"(?:[A-Za-z0-9]+_)*seed"\s*:\s*(\d+)')
_RECORD_SUFFIXES = (".json", ".jsonl")


def recorded_test_seeds(runs_root: Path) -> dict[int, Path]:
    """Every test-range seed in a JSON/JSONL record under `runs_root`, with one file naming it."""
    found: dict[int, Path] = {}
    for path in sorted(p for p in runs_root.rglob("*") if p.suffix in _RECORD_SUFFIXES):
        for seed in _test_seeds_in(path):
            found.setdefault(seed, path)
    return found


def _test_seeds_in(path: Path) -> set[int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {int(m) for m in _SEED_FIELD.findall(text) if int(m) in TEST_SEED_RANGE}


def retired_seeds(runs_root: Path) -> frozenset[int]:
    """The registered retired seeds plus every test-range seed recorded under `runs_root`."""
    return RETIRED_TEST_SEEDS | frozenset(recorded_test_seeds(runs_root))


def require_fresh_test_seed(seed: int, retired: Iterable[int]) -> None:
    """Refuse a retired seed for a test role.

    Raises:
        ValueError: the seed was used (or recorded) by the first measurement.
    """
    if seed in set(retired):
        raise ValueError(
            f"expected a fresh test seed, found {seed} (used by the first measurement)"
        )
