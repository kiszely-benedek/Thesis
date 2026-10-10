"""Cross-check the abandoned-call cost estimate against the late charges a run logged.

A call abandoned at its timeout may still be billed. The cascade charges each one a fixed
upper bound (`ABANDONED_CALL_COST_USD`); this reads `calls.jsonl` to show what the late
answers that did arrive really cost, so the bound can be judged.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.llm.models import CallRecord
from plantgraph.qa.cascade.report_models import LateChargeCheck
from plantgraph.qa.cascade.signals import ABANDONED_CALL_COST_USD
from plantgraph.qa.harness.run_dir import RunDir


def late_charge_check(run_dir: Path, strategy: str) -> LateChargeCheck | None:
    """The check for one strategy of one run; `None` when it abandoned no call."""
    run = RunDir(run_dir)
    rows = [r for r in run.read_rows() if r.strategy == strategy]
    n_abandoned = sum(r.retrieval_usage.n_abandoned for r in rows if r.retrieval_usage)
    if n_abandoned == 0 or not run.calls_path.exists():
        return None
    records = [
        CallRecord.model_validate_json(line)
        for line in run.calls_path.read_text(encoding="utf-8").splitlines()
    ]
    own = [c for c in records if c.strategy == strategy]
    late = [c for c in own if c.error_kind == "late_after_timeout"]
    return LateChargeCheck(
        run_id=run_dir.name,
        strategy=strategy,
        n_abandoned_in_rows=n_abandoned,
        n_timeouts_logged=sum(c.error_kind == "timeout" for c in own),
        n_late_logged=len(late),
        late_cost_logged_usd=sum(c.response.cost_usd or 0.0 for c in late if c.response),
        estimate_usd=n_abandoned * ABANDONED_CALL_COST_USD,
    )
