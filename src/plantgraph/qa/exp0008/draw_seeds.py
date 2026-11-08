"""Draw the fresh EXP-0008 test seeds, once, reproducibly, into the pre-registration (part A).

Drawing a seed is not generating a plant: nothing here builds one. The draw is a seeded sample of
the test range minus every retired seed, so the same `--draw-seed` and the same `data/runs` give
the same plan. The tool refuses to overwrite an existing seeds file (the seeds are fixed before
any plant exists) and records how the draw was made inside the file.

    python -m plantgraph.qa.exp0008.draw_seeds --draw-seed N [--runs-root data/runs] [--out PATH]
"""

from __future__ import annotations

import argparse
import platform
import random
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from plantgraph.ingest.seed_plan import (
    DEFAULT_SEED_PLAN_PATH,
    PLANTS_PER_SIZE,
    SEALED_SIZES,
    SINGLE_SHEET_CANDIDATES,
    TEST_SEED_RANGE,
    DrawRecord,
    SeedPlan,
)
from plantgraph.qa.exp0008.hygiene import retired_seeds

METHOD = (
    "random.Random(draw_seed).sample(sorted(pool), n); in order: validation 100, validation 1000, "
    "the ladder seed, the 1-sheet candidates, 5 sealed seeds at 100, 5 sealed seeds at 1000"
)
_N_SEEDS = 2 + 1 + SINGLE_SHEET_CANDIDATES + PLANTS_PER_SIZE * len(SEALED_SIZES)
_SEALED_START = 3 + SINGLE_SHEET_CANDIDATES


def draw_seed_plan(
    draw_seed: int, retired: frozenset[int], runs_root: Path, drawn_at: datetime | None = None
) -> SeedPlan:
    """The plan for `draw_seed`: pool = test range minus `retired`, sampled by `draw_seed`.

    Raises:
        ValueError: the pool is too small for all roles.
    """
    pool = sorted(set(TEST_SEED_RANGE) - retired)
    if len(pool) < _N_SEEDS:
        raise ValueError(f"expected at least {_N_SEEDS} unretired test seeds, found {len(pool)}")
    drawn = random.Random(draw_seed).sample(pool, _N_SEEDS)
    return SeedPlan(
        validation={100: drawn[0], 1000: drawn[1]},
        ladder_seed=drawn[2],
        single_sheet_candidates=tuple(drawn[3:_SEALED_START]),
        sealed=_sealed_seeds(drawn[_SEALED_START:]),
        draw=DrawRecord(
            draw_seed=draw_seed,
            method=METHOD,
            pool=f"{TEST_SEED_RANGE.start}-{TEST_SEED_RANGE.stop - 1} minus retired: {len(pool)}",
            retired=tuple(sorted(retired & set(TEST_SEED_RANGE))),
            retired_sources=f"registered table + seed fields of *.json/*.jsonl under {runs_root}",
            drawn_at_utc=(drawn_at or datetime.now(UTC)).isoformat(timespec="seconds"),
            python_version=platform.python_version(),
        ),
    )


def _sealed_seeds(flat: list[int]) -> dict[int, tuple[int, ...]]:
    """Split the sealed seeds into consecutive blocks of five, one per size."""
    return {
        size: tuple(flat[i * PLANTS_PER_SIZE : (i + 1) * PLANTS_PER_SIZE])
        for i, size in enumerate(SEALED_SIZES)
    }


def write_seed_plan(plan: SeedPlan, path: Path) -> None:
    """Write the plan as JSON; never overwrites.

    Raises:
        FileExistsError: the seeds are already drawn at `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise FileExistsError(
            f"expected no seeds file at {path}, found one (never redrawn)"
        ) from error
    with handle:
        handle.write(plan.model_dump_json(indent=2) + "\n")


def render_markdown(plan: SeedPlan) -> str:
    """The seed table for `PREREG_A.md`."""
    candidates = ", ".join(map(str, plan.single_sheet_candidates))
    rows = [f"| validation, {n} sheets | {s} |" for n, s in sorted(plan.validation.items())]
    rows.append(f"| ladder, 3/10/30 sheets | {plan.ladder_seed} |")
    rows.append(f"| ladder, 1-sheet candidates in order | {candidates} |")
    for size, seeds in plan.sealed.items():
        rows += [f"| sealed {size} sheets, plant p{k} | {s} |" for k, s in enumerate(seeds, 1)]
    return "\n".join(["| role | seed |", "|---|---|", *rows])


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0008.draw_seeds")
    parser.add_argument("--draw-seed", type=int, required=True, help="seeds the sample; recorded")
    parser.add_argument("--runs-root", type=Path, default=Path("data/runs"))
    parser.add_argument("--out", type=Path, default=DEFAULT_SEED_PLAN_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Draw and write the plan, print the markdown table."""
    args = _parse_args(argv)
    plan = draw_seed_plan(args.draw_seed, retired_seeds(args.runs_root), args.runs_root)
    write_seed_plan(plan, args.out)
    print(render_markdown(plan))
    print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
