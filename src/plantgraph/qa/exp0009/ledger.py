"""The EXP-0009 spend ledger: a $35 hard program cap, runs and audit together (design §19.9).

Reuses EXP-0008's readers (`paid_usd_of_calls`, `audit_spent_usd`). One thing differs: EXP-0008's
`runs_spent_usd` globs `*calls.jsonl` under the root and skips only the `audit/` folder, so a
call file copied under `reports/` (the report tools copy whole run folders there) was counted
twice. Here every path with a `reports` or `audit` component is skipped. EXP-0008's own ledger
stays as it is, so its record remains reproducible.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.exp0008.ledger import LedgerExhausted, audit_spent_usd, paid_usd_of_calls

PROGRAM_CAP_USD = 35.0
AUDIT_CAP_USD = 8.13
RUNS_CAP_USD = round(PROGRAM_CAP_USD - AUDIT_CAP_USD, 2)  # 26.87
_SKIPPED_FOLDERS = frozenset({"reports", "audit"})


def runs_spent_usd(root: Path) -> float:
    """What the runs under `root` paid; copies under `reports/` and the audit folder are skipped."""
    files = sorted(
        p
        for p in root.rglob("*calls.jsonl")
        if not _SKIPPED_FOLDERS & set(p.relative_to(root).parts)
    )
    return sum(paid_usd_of_calls(p) for p in files)


def run_cap_usd(own_cap_usd: float, root: Path, step_dir: Path, step_ceiling_usd: float) -> float:
    """The run's cap cut to what the step ceiling and the runs ledger still allow.

    Raises:
        LedgerExhausted: the step or the runs ledger has nothing left.
    """
    step_left = step_ceiling_usd - runs_spent_usd(step_dir)
    ledger_left = RUNS_CAP_USD - runs_spent_usd(root)
    if step_left <= 0:
        raise LedgerExhausted(
            f"expected money under the step ceiling ${step_ceiling_usd:.2f}, found ${step_left:.4f}"
        )
    if ledger_left <= 0:
        raise LedgerExhausted(
            f"expected money under the ${RUNS_CAP_USD} runs ledger, found ${ledger_left:.4f}"
        )
    return round(min(own_cap_usd, step_left, ledger_left), 6)


def resumed_run_cap_usd(
    own_cap_usd: float, root: Path, step_dir: Path, step_ceiling_usd: float, run_dir: Path
) -> float:
    """`run_cap_usd` for a resumed run: what it already spent plus the new allowance."""
    allowance = run_cap_usd(own_cap_usd, root, step_dir, step_ceiling_usd)
    calls = run_dir / "calls.jsonl"
    spent = paid_usd_of_calls(calls) if calls.is_file() else 0.0
    return round(spent + allowance, 6)


def audit_cap_usd(root: Path) -> float:
    """min($8.13, $35 less the runs): unused run money stays usable by the audit.

    Raises:
        LedgerExhausted: nothing is left for the audit.
    """
    total = round(min(AUDIT_CAP_USD, PROGRAM_CAP_USD - runs_spent_usd(root)), 6)
    if total - audit_spent_usd(root) <= 0:
        raise LedgerExhausted(f"expected money for the audit under ${total:.2f}, found none")
    return total


def summary(root: Path) -> str:
    """One line: what the runs and the audit have spent, and what is left of each ledger."""
    runs, audit = runs_spent_usd(root), audit_spent_usd(root)
    return (
        f"runs ${runs:.4f} of ${RUNS_CAP_USD} (left ${RUNS_CAP_USD - runs:.4f}); "
        f"audit ${audit:.4f} of ${AUDIT_CAP_USD}"
    )
