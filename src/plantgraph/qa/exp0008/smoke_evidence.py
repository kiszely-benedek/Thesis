"""Evidence files for the smoke's gates G1 and G2, since a smoke has no real model answers.

In `run_all.sh --smoke` every model reply is a canned `{}`, so the reports that G1 and G2 read would
show nothing but zeros. The smoke therefore writes small evidence files in the exact formats the
real tools write (`tune_report.json`, `dev_report.json`, the judge's `verdicts.jsonl` and its
ledger), and the gate code that judges them is the real code. `--fail` writes evidence that makes
the gate fail, which is how the smoke proves that a failed gate stops the launcher.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plantgraph.qa.audit.budget import LedgerLine, SpendLedger
from plantgraph.qa.audit.models import (
    AuditItem,
    AuditRecord,
    JudgeReply,
    JudgeVerdict,
    SourceRow,
    Stratum,
)
from plantgraph.qa.exp0008.gates import V2T_POLICY

_FAMILIES = ("CONNECTED", "FLOW_PATH", "LOOKUP_TYPE")
_PER_FAMILY = 10
_PILOT_CALL_USD = 0.012


def _write_g1_plant(out_dir: Path, plant: str, v2t_correct: int, f1_correct: int) -> None:
    """One plant's two reports, with `v2t_correct` of 30 for V2T and `f1_correct` of 30 for F1."""
    by_family = {
        family: {"correct": v2t_correct // len(_FAMILIES), "total": _PER_FAMILY}
        for family in _FAMILIES
    }
    tune = {
        "n_questions": _PER_FAMILY * len(_FAMILIES),
        "results": {
            V2T_POLICY: {"n_correct_in_limit": v2t_correct, "by_family": by_family},
        },
    }
    rows = [{"family": f, "n": _PER_FAMILY, "cascade_correct": f1_correct // 3} for f in _FAMILIES]
    plant_dir = out_dir / plant
    plant_dir.mkdir(parents=True, exist_ok=True)
    (plant_dir / "tune_report.json").write_text(json.dumps(tune), encoding="utf-8")
    (plant_dir / "dev_report.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")


def write_g1_evidence(out_dir: Path, fail: bool) -> None:
    """Two plants; V2T beats F1 on both, or (`fail`) falls below it on one."""
    _write_g1_plant(out_dir, "VAL100g21", v2t_correct=27, f1_correct=24)
    _write_g1_plant(out_dir, "VAL1000g21", v2t_correct=21 if fail else 27, f1_correct=24)


def _record(index: int, stratum: Stratum, verdict: JudgeVerdict) -> AuditRecord:
    row = SourceRow(
        run_id="smoke",
        strategy="smoke",
        question_id=f"smoke:q{index}",
        corpus_id="smoke",
        family="CONNECTED",
        scale="100",
        outcome="ANSWERED",
        scorer_correct=False,
        answer_key=str(index),
    )
    reply = JudgeReply(verdict=verdict, reference_ok=True, reason="smoke evidence")
    return AuditRecord(
        item=AuditItem(stratum=stratum, row=row),
        reply=reply,
        prompt_chars=100,
        prompt_tokens=40,
        completion_tokens=10,
        paid_usd=_PILOT_CALL_USD,
    )


def write_g2_evidence(out_dir: Path, fail: bool) -> None:
    """A pilot of 10 defect rows and 10 controls; the judge finds them all, or (`fail`) none."""
    out_dir.mkdir(parents=True, exist_ok=True)
    defect = JudgeVerdict.INCORRECT if fail else JudgeVerdict.CORRECT
    records = [_record(i, "pilot_defect_valves", defect) for i in range(10)]
    records += [_record(10 + i, "pilot_control", JudgeVerdict.CORRECT) for i in range(10)]
    text = "".join(r.model_dump_json() + "\n" for r in records)
    (out_dir / "verdicts.jsonl").write_text(text, encoding="utf-8")
    ledger = SpendLedger(out_dir.parent / "ledger.jsonl")
    for r in records:
        ledger.record(
            LedgerLine(stage="pilot", item_key=r.item.row.question_id, paid_usd=r.paid_usd)
        )


def cmd_smoke_evidence(args: argparse.Namespace) -> None:
    """Write the smoke's evidence for gate G1 or G2 (`--fail` makes the gate fail)."""
    if args.what == "g1":
        write_g1_evidence(args.out_dir, args.fail)
    else:
        write_g2_evidence(args.out_dir, args.fail)
