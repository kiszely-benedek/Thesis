"""Spend caps of an E2E arm, computed from the free dry run's miss counts (design section 10).

python -m plantgraph.exp0004.e2e_caps make --arm d0 --cyp-misses F --ag-misses F --out caps.json
python -m plantgraph.exp0004.e2e_caps split --caps caps.json --max-spend-usd X     # prints two caps

cap of a tier = questions with a cache miss x R5's cost per question x 1.5. The user's cap for the
arm must not exceed the sum unless the user approved more (`--above-dry-cap`, never above the P4
bound of $4.44); it is divided between the tiers in proportion to their computed caps.
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
#: PREREG.md section 7: the upper bound for all three P4 arms together
P4_UPPER_BOUND_USD = 4.44


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


def split_cap(caps: E2ECaps, max_spend_usd: float, above_dry_cap: bool = False) -> dict[str, float]:
    """Divide the user's cap between the tiers in proportion to their computed caps.

    `above_dry_cap` is the user's explicit approval of a cap above the dry run's total (2026-11-06:
    the agent tier cost 1.42x R5's per-question figure on H1000g2V, so 1.5x did not cover it). It
    never lifts the pre-registered upper bound for the whole of P4.

    Raises:
        ValueError: the cap is not positive, there is nothing to pay for, the cap exceeds the
            dry run's total without `above_dry_cap`, or it exceeds the P4 upper bound.
    """
    if max_spend_usd <= 0:
        raise ValueError(f"expected a cap above 0, found {max_spend_usd}")
    if caps.total_cap_usd <= 0:
        raise ValueError(
            "expected at least one cache miss in the dry run, found none: nothing to pay"
        )
    if max_spend_usd > P4_UPPER_BOUND_USD:
        raise ValueError(
            f"expected a cap of at most {P4_UPPER_BOUND_USD} (the pre-registered P4 bound), "
            f"found {max_spend_usd}"
        )
    if max_spend_usd > caps.total_cap_usd and not above_dry_cap:
        raise ValueError(
            f"expected a cap of at most {caps.total_cap_usd} (the dry run's total), "
            f"found {max_spend_usd}"
        )
    return {
        tier: round(max_spend_usd * cap / caps.total_cap_usd, 6)
        for tier, cap in caps.cap_usd.items()
    }


def explicit_tier_caps(
    cyp_usd: float, ag_usd: float, max_spend_usd: float, above_dry_cap: bool
) -> dict[str, float]:
    """The user's own cap per tier, instead of the proportional split.

    Why (2026-11-06): on a resume the harness's spend guard counts the recorded cost of the rows on
    disk, cache hits included, so a resumed tier needs a nominal cap far above what it really
    spent. A proportional split would then lift the other tier's cap with it.

    Raises:
        ValueError: the user has not approved caps above the dry run's, a tier cap is not
            positive, the two do not add up to the arm cap, or they exceed the P4 upper bound.
    """
    if not above_dry_cap:
        raise ValueError("expected --above-dry-cap with explicit tier caps (the user's approval)")
    if min(cyp_usd, ag_usd) <= 0:
        raise ValueError(f"expected both tier caps above 0, found {cyp_usd} and {ag_usd}")
    if abs(cyp_usd + ag_usd - max_spend_usd) > 1e-6:
        raise ValueError(
            f"expected the tier caps to add up to the arm cap {max_spend_usd}, "
            f"found {cyp_usd} + {ag_usd}"
        )
    if max_spend_usd > P4_UPPER_BOUND_USD:
        raise ValueError(
            f"expected a cap of at most {P4_UPPER_BOUND_USD} (the pre-registered P4 bound), "
            f"found {max_spend_usd}"
        )
    return {"cyp": cyp_usd, "ag": ag_usd}


def _split_or_explicit(caps: E2ECaps, args: argparse.Namespace) -> dict[str, float]:
    """The explicit tier caps when the user gave them, else the proportional split."""
    if args.tier_caps_usd is None:
        return split_cap(caps, args.max_spend_usd, args.above_dry_cap)
    cyp_usd, ag_usd = args.tier_caps_usd
    return explicit_tier_caps(cyp_usd, ag_usd, args.max_spend_usd, args.above_dry_cap)


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
    split.add_argument(
        "--above-dry-cap",
        action="store_true",
        help="the user approved a cap above the dry run's total (never above the P4 bound)",
    )
    split.add_argument(
        "--tier-caps-usd",
        type=float,
        nargs=2,
        metavar=("CYP", "AG"),
        help="the user's own cap per tier, not the proportional split (needs --above-dry-cap)",
    )
    args = parser.parse_args(argv)
    if args.command == "make":
        caps = compute_caps(args.arm, _read_report(args.cyp_misses), _read_report(args.ag_misses))
        with args.out.open("x", encoding="utf-8") as handle:  # "x": fails if the file exists
            handle.write(caps.model_dump_json(indent=1) + "\n")
        print(f"{args.arm}: caps {caps.cap_usd}, total ${caps.total_cap_usd} ({caps.basis})")
    else:
        caps = E2ECaps.model_validate_json(args.caps.read_text(encoding="utf-8"))
        try:
            parts = _split_or_explicit(caps, args)
        except ValueError as error:
            raise SystemExit(f"error: {error}") from error
        print(parts["cyp"], parts["ag"])


if __name__ == "__main__":
    main()
