"""The main audit sample over scope R rows only (ADR-0069, finding F9).

The frozen `qa.audit select` pools every row of the A2 sealed runs. Those include the scope X
isolation families, which A2 answers through the tag-set adapter and gets wrong by construction
wherever the gold names an untagged valve. Their verdicts say nothing about the scorer, and they
would use up audit money that scope R needs. This wrapper drops the scope X rows from the pool and
then calls the frozen `select_audit` unchanged. The B stratum covers scope X's answer types.

    python -m plantgraph.qa.exp0009.audit_select --run ... --questions-root ... --ledger ... \
        --cap-usd N --call-usd N --out plan.json
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from plantgraph.qa.audit.budget import SpendLedger
from plantgraph.qa.audit.cli import DEFAULT_SEED
from plantgraph.qa.audit.models import SourceRow
from plantgraph.qa.audit.select import AuditPlan, select_audit
from plantgraph.qa.audit.sources import load_run, source_rows
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES


def scope_r_rows(rows: Sequence[SourceRow]) -> list[SourceRow]:
    """The rows whose family is not a scope X family."""
    return [row for row in rows if row.family not in SCOPE_X_FAMILIES]


def pool_of(run_dirs: Sequence[Path], questions_root: Path) -> list[SourceRow]:
    """Every row of the runs, as the audit's rows (distinct run ids are checked)."""
    pool: list[SourceRow] = []
    seen: set[str] = set()
    for run_dir in run_dirs:
        run = load_run(run_dir, questions_root)
        if run.run_id in seen:
            raise ValueError(f"expected distinct run ids, found {run.run_id!r} twice")
        seen.add(run.run_id)
        pool += source_rows(run)
    return pool


def select_scope_r(
    pool: Sequence[SourceRow], *, seed: int, call_usd: float, remaining_usd: float
) -> AuditPlan:
    """The frozen selection over the scope R rows of `pool`.

    Raises:
        ValueError: no scope R row is left, or the budget cannot cover the minimum sample.
    """
    rows = scope_r_rows(pool)
    if not rows:
        raise ValueError("expected scope R rows in the A2 sealed runs, found none")
    return select_audit(rows, [], seed=seed, call_usd=call_usd, remaining_usd=remaining_usd)


def main(argv: Sequence[str] | None = None) -> int:
    """Write the plan to `--out` and print its size."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.audit_select")
    parser.add_argument("--run", action="append", type=Path, required=True)
    parser.add_argument("--questions-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--cap-usd", type=float, required=True)
    parser.add_argument("--call-usd", type=float, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    ledger = SpendLedger(args.ledger, args.cap_usd)
    pool = pool_of(args.run, args.questions_root)
    plan = select_scope_r(
        pool, seed=args.seed, call_usd=args.call_usd, remaining_usd=ledger.remaining_usd()
    )
    args.out.write_text(plan.model_dump_json(indent=1), encoding="utf-8")
    dropped = len(pool) - len(scope_r_rows(pool))
    print(f"audit plan: {len(plan.items)} scope R rows ({dropped} scope X rows left out), "
          f"about {plan.estimated_usd:.2f} USD -> {args.out}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
