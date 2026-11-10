"""The EXP-0008 spend ledger: a $40 program cap, of which the runs may use $30 (review-fixes §6).

Money is read back from the records the runs already write, never from a running counter that
could drift. A run's `calls.jsonl` (D4's `*llm_calls.jsonl`) lists every model call; a call is
paid when its reply did not come from the cache. The scorer audit keeps its own ledger file
(`qa/audit/budget.py`), because its judge calls are not part of the runs. Each paid run asks for
`run_cap_usd` before it starts.
"""

from __future__ import annotations

import json
from pathlib import Path

from plantgraph.qa.harness.jsonl_tail import parse_jsonl

PROGRAM_CAP_USD = 40.0
AUDIT_CAP_USD = 10.0
RUNS_CAP_USD = PROGRAM_CAP_USD - AUDIT_CAP_USD

#: folder (under the EXP-0008 root) whose `calls.jsonl` and `ledger.jsonl` belong to the audit
AUDIT_FOLDER = "audit"
#: a run writes `calls.jsonl`; the identity-link decider D4 writes `*_llm_calls.jsonl` likewise
_CALLS_GLOB = "*calls.jsonl"
_AUDIT_LEDGER = "ledger.jsonl"


class LedgerExhausted(RuntimeError):
    """A paid step has no money left under the ledger."""


def paid_usd_of_calls(calls_file: Path) -> float:
    """Dollars paid in one `calls.jsonl`: the cost of every call whose reply was not cached.

    A last line cut off by a crash is skipped with a warning.

    Raises:
        ValueError: a line other than the last is not JSON, so the spend cannot be trusted.
    """
    total = 0.0
    for record in parse_jsonl(calls_file, json.loads):
        response = record.get("response")
        if response and not response.get("from_cache") and response.get("cost_usd"):
            total += float(response["cost_usd"])
    return total


def runs_spent_usd(root: Path) -> float:
    """Everything the runs under `root` paid so far (the audit's folder is left out)."""
    audit = (root / AUDIT_FOLDER).resolve()
    files = sorted(p for p in root.rglob(_CALLS_GLOB) if audit not in p.resolve().parents)
    return sum(paid_usd_of_calls(p) for p in files)


def audit_spent_usd(root: Path) -> float:
    """What the scorer audit (pilot included) paid, from its own ledger file."""
    ledger = root / AUDIT_FOLDER / _AUDIT_LEDGER
    if not ledger.is_file():
        return 0.0
    lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    return sum(float(line["paid_usd"]) for line in lines)


def run_cap_usd(dry_cap_usd: float, root: Path, step_dir: Path, step_ceiling_usd: float) -> float:
    """The cap one run may use: its dry-run cap, bounded by its step's ceiling and by the ledger.

    Three limits apply and the smallest wins: the dry run's cap, what is left of the step's ceiling
    (the step's own spend so far is read from `step_dir`), and what is left of the $30 runs ledger.

    Raises:
        LedgerExhausted: the step's ceiling or the runs ledger has nothing left.
    """
    step_left = step_ceiling_usd - runs_spent_usd(step_dir)
    ledger_left = RUNS_CAP_USD - runs_spent_usd(root)
    if step_left <= 0:
        raise LedgerExhausted(
            f"expected money left under the step ceiling ${step_ceiling_usd:.2f}, "
            f"found ${step_left:.4f}"
        )
    if ledger_left <= 0:
        raise LedgerExhausted(
            f"expected money left under the ${RUNS_CAP_USD:.0f} runs ledger, "
            f"found ${ledger_left:.4f}"
        )
    return round(min(dry_cap_usd, step_left, ledger_left), 6)


def resumed_run_cap_usd(
    dry_cap_usd: float, root: Path, step_dir: Path, step_ceiling_usd: float, run_dir: Path
) -> float:
    """`run_cap_usd` for a run that may already have spent money in an earlier attempt.

    The harness counts everything a run spent against its cap, so a resumed run needs
    "spent so far + the new allowance"; the allowance is bounded as in `run_cap_usd`, which
    already subtracts that earlier spend from the step ceiling and the ledger.
    """
    allowance = run_cap_usd(dry_cap_usd, root, step_dir, step_ceiling_usd)
    calls = run_dir / "calls.jsonl"
    spent = paid_usd_of_calls(calls) if calls.is_file() else 0.0
    return round(spent + allowance, 6)


def audit_cap_usd(root: Path) -> float:
    """The audit's total cap (pilot included): $10, or what the runs leave of the $40 program cap.

    This is the figure the audit's own ledger takes as its cap: it subtracts what the audit has
    already spent, so the money still available is `audit_cap_usd - audit_spent_usd`.

    Raises:
        LedgerExhausted: nothing is left for the audit.
    """
    total = round(min(AUDIT_CAP_USD, PROGRAM_CAP_USD - runs_spent_usd(root)), 6)
    left = total - audit_spent_usd(root)
    if left <= 0:
        raise LedgerExhausted(
            f"expected money left for the audit under ${total:.2f} (the $40 program cap less "
            f"the runs), found ${left:.4f}"
        )
    return total
