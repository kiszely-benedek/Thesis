"""Spend caps of an E2E arm, computed from the free dry run's miss counts (design section 10).

python -m plantgraph.exp0004.e2e_caps make --arm d0 --cyp-misses F --ag-misses F --out caps.json
python -m plantgraph.exp0004.e2e_caps split --caps caps.json --max-spend-usd X     # prints two caps

cap of a tier = questions with a cache miss x R5's cost per question x 1.5. The user's cap for the
arm must not exceed the sum; it is divided between the tiers in proportion to their computed caps.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from pydantic import BaseModel

from plantgraph.exp0004.e2e_dry_run import DryRunReport

#: R5's cost per question at H1000g2, in USD (`docs/private/30-experiments/EXP-0007-R5-sealed.md`,
#: table rows always_c_v2t (Cypher tier) and always_g_v2t (agent tier), the 1,000-sheet figure).
COST_PER_QUESTION_USD = {"cyp": 0.00075, "ag": 0.00189}
SAFETY_FACTOR = 1.5


class E2ECaps(BaseModel):
    """The caps of one arm and what they were computed from."""

    arm: str
    n_misses: dict[str, int]
    cost_per_question_usd: dict[str, float]
    cap_usd: dict[str, float]
    total_cap_usd: float
    basis: str


def tier_cap(n_misses: int, tier: str) -> float:
    """Misses x R5's cost per question x the safety factor, rounded up to 0.0001 USD."""
    return math.ceil(n_misses * COST_PER_QUESTION_USD[tier] * SAFETY_FACTOR * 1e4) / 1e4


def compute_caps(arm: str, cyp: DryRunReport, ag: DryRunReport) -> E2ECaps:
    """The two tier caps of one arm from its two dry-run reports."""
    n_misses = {"cyp": cyp.n_questions_with_miss, "ag": ag.n_questions_with_miss}
    caps = {tier: tier_cap(n, tier) for tier, n in n_misses.items()}
    return E2ECaps(
        arm=arm,
        n_misses=n_misses,
        cost_per_question_usd=dict(COST_PER_QUESTION_USD),
        cap_usd=caps,
        total_cap_usd=round(sum(caps.values()), 4),
        basis=f"questions with a miss x R5 cost per question at H1000g2 x {SAFETY_FACTOR}",
    )


def split_cap(caps: E2ECaps, max_spend_usd: float) -> dict[str, float]:
    """Divide the user's cap between the tiers in proportion to their computed caps.

    Raises:
        ValueError: the cap is not positive, there is nothing to pay for, or the cap exceeds the
            dry run's total (a larger cap needs a new dry run).
    """
    if max_spend_usd <= 0:
        raise ValueError(f"expected a cap above 0, found {max_spend_usd}")
    if caps.total_cap_usd <= 0:
        raise ValueError(
            "expected at least one cache miss in the dry run, found none: nothing to pay"
        )
    if max_spend_usd > caps.total_cap_usd:
        raise ValueError(
            f"expected a cap of at most {caps.total_cap_usd} (the dry run's total), "
            f"found {max_spend_usd}"
        )
    return {
        tier: round(max_spend_usd * cap / caps.total_cap_usd, 6)
        for tier, cap in caps.cap_usd.items()
    }


def _read_report(path: Path) -> DryRunReport:
    return DryRunReport.model_validate_json(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    """`make` writes the caps file (never over an existing one); `split` prints `CYP_CAP AG_CAP`."""
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004.e2e_caps", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("make")
    make.add_argument("--arm", required=True)
    make.add_argument("--cyp-misses", type=Path, required=True)
    make.add_argument("--ag-misses", type=Path, required=True)
    make.add_argument("--out", type=Path, required=True)
    split = commands.add_parser("split")
    split.add_argument("--caps", type=Path, required=True)
    split.add_argument("--max-spend-usd", type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == "make":
        caps = compute_caps(args.arm, _read_report(args.cyp_misses), _read_report(args.ag_misses))
        with args.out.open("x", encoding="utf-8") as handle:  # "x": fails if the file exists
            handle.write(caps.model_dump_json(indent=1) + "\n")
        print(f"{args.arm}: caps {caps.cap_usd}, total ${caps.total_cap_usd} ({caps.basis})")
    else:
        caps = E2ECaps.model_validate_json(args.caps.read_text(encoding="utf-8"))
        try:
            parts = split_cap(caps, args.max_spend_usd)
        except ValueError as error:
            raise SystemExit(f"error: {error}") from error
        print(parts["cyp"], parts["ag"])


if __name__ == "__main__":
    main()
