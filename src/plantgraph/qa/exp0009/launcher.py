"""`python -m plantgraph.qa.exp0009.launcher <command>`: the helpers of `run_all.sh`.

The shell scripts only sequence work; every decision that needs arithmetic, hashing or parsing is a
command here, so that it has a test. A command that fails prints `ERROR: <what was expected,
found>` on stderr and exits 1. Commands that EXP-0008 already has (state files, balance, replay
comparison, memory probe) are its own functions, registered here under the same names.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from plantgraph.qa.exp0008 import launcher_commands as old
from plantgraph.qa.exp0009 import launcher_commands as c
from plantgraph.qa.exp0009 import launcher_stages as s

ROOT = Path("data/runs/exp0009")
Handler = Callable[[argparse.Namespace], None]
type Sub = argparse._SubParsersAction[argparse.ArgumentParser]


def _add(sub: Sub, name: str, handler: Handler) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, help=(handler.__doc__ or "").split("\n")[0])
    parser.set_defaults(handler=handler)
    return parser


def _roots(parser: argparse.ArgumentParser, prereg: bool = False) -> None:
    parser.add_argument("--root", type=Path, default=ROOT)
    if prereg:
        parser.add_argument("--prereg", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")


def _plants(sub: Sub) -> None:
    p = _add(sub, "draw", c.cmd_draw)
    p.add_argument("--draw-seed", type=int)
    p.add_argument("--prereg", type=Path, default=ROOT / "prereg")
    p.add_argument("--runs-root", type=Path, default=Path("data/runs"))
    p.add_argument("--smoke", action="store_true")
    p = _add(sub, "plan-list", c.cmd_plan_list)
    p.add_argument("kind", choices=["dev", "probe", "validation", "sealed", "all"])
    p.add_argument("--prereg", type=Path, default=ROOT / "prereg")
    for name, handler in (
        ("build", c.cmd_build),
        ("load-a", c.cmd_load_a),
        ("prepare-b-load", c.cmd_prepare_b_load),
        ("r14f", c.cmd_r14f),
    ):
        p = _add(sub, name, handler)
        _roots(p)
        p.add_argument("--prereg", type=Path, default=ROOT / "prereg")
        p.add_argument("--plant", required=True)
    p = _add(sub, "questions-pool", c.cmd_questions_pool)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--plant", required=True)
    p.add_argument("--recipe", choices=["sealed", "dev"], required=True)
    p = _add(sub, "questions-files", c.cmd_questions_files)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--prereg", type=Path, default=ROOT / "prereg")
    p.add_argument("--role", choices=["dev", "validation", "sealed"], required=True)


def _money(sub: Sub) -> None:
    for name, handler in (("run-cap", c.cmd_run_cap), ("cost-of", c.cmd_cost_of)):
        p = _add(sub, name, handler)
        p.add_argument("--tier", choices=["cyp", "ag"], required=True)
        p.add_argument("--scale", type=int, choices=[100, 1000], required=True)
        p.add_argument("--arm", choices=["A2", "B"], required=True)
        p.add_argument("--measured", type=Path, help="P1b's measured dollars per question (JSON)")
        if name == "run-cap":
            p.add_argument("--questions", type=Path, required=True)
            p.add_argument("--step", choices=["P1a", "P1b", "P1c"], required=True)
            p.add_argument("--root", type=Path, required=True)
            p.add_argument("--step-dir", type=Path, required=True)
            p.add_argument("--run-dir", type=Path)
    for name, handler in (("audit-cap", c.cmd_audit_cap), ("spent", c.cmd_spent)):
        p = _add(sub, name, handler)
        p.add_argument("--root", type=Path, required=True)
        if name == "audit-cap":
            p.add_argument("--left", action="store_true", help="the cap minus what the audit spent")
    p = _add(sub, "estimate", c.cmd_estimate)
    p.add_argument("--stage", required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--balance-usd", type=float)
    p = _add(sub, "balance", old.cmd_balance)
    p.add_argument("--needed", type=float, required=True)
    p.add_argument("--fake-balance", type=float)


def _runs(sub: Sub) -> None:
    p = _add(sub, "records-check", c.cmd_records_check)
    p.add_argument("--run-dir", type=Path, required=True)
    p = _add(sub, "rescore", c.cmd_rescore)
    for name in ("--run-dir", "--questions-root", "--ingest-json", "--out"):
        p.add_argument(name, type=Path, required=True)
    p.add_argument("--corpus-id", required=True)
    p.add_argument("--b", action="store_true", help="a B corpus: score with the B scorer")
    p = _add(sub, "cascade-report", s.cmd_cascade_report)
    for name in ("--cyp-run", "--ag-run", "--questions-root", "--corpora-root", "--out"):
        p.add_argument(name, type=Path, required=True)
    p.add_argument("--corpus-id", required=True)
    p.add_argument("--arm", choices=["A2", "B"], required=True)
    p = _add(sub, "plan-ids", old.cmd_plan_ids)
    for name in ("--plan", "--out"):
        p.add_argument(name, type=Path, required=True)
    p.add_argument("--corpus", required=True)
    p = _add(sub, "replay-compare", old.cmd_replay_compare)
    p.add_argument("--replay-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--allow-prefix", choices=["yes", "no"], default="no")
    p = _add(sub, "check-run-config", old.cmd_check_run_config)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--corpora-root", type=Path)
    p = _add(sub, "memory-probe", old.cmd_memory_probe)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--limit-gib", type=float)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = _add(sub, "measure-costs", s.cmd_measure_costs)
    p.add_argument("--val-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = _add(sub, "g0f", c.cmd_g0f)
    p.add_argument("--e9-commit", type=Path, default=Path("data/runs/exp0008/prereg/E9.commit"))
    p = _add(sub, "b-code-write", s.cmd_b_code_write)
    p.add_argument("--run-dir", type=Path, required=True)
    p = _add(sub, "audit-b-select", s.cmd_audit_b_select)
    p.add_argument("--run", type=Path, action="append", required=True)
    for name in ("--main-plan", "--questions-root", "--corpora-root", "--out", "--sheet"):
        p.add_argument(name, type=Path, required=True)
    p = _add(sub, "b-files-check", s.cmd_b_files_check)
    p.add_argument("--against", type=Path, required=True)
    p = _add(sub, "b-code-check", s.cmd_b_code_check)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--against", type=Path, required=True)


def _state(sub: Sub) -> None:
    p = _add(sub, "state-write", old.cmd_state_write)
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("outputs", nargs="+", type=Path)
    p = _add(sub, "state-check", old.cmd_state_check)
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--stage", required=True)
    p = _add(sub, "stopped", old.cmd_stopped)
    p.add_argument("--dir", type=Path, required=True)
    for name in ("--stage", "--reason", "--resume"):
        p.add_argument(name, required=True)


def _tuning_and_freeze(sub: Sub) -> None:
    p = _add(sub, "tuning-round", s.cmd_tuning_round)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--change", required=True, help="one line: what the main session changed")
    p.add_argument("--b-report", type=Path, required=True)
    p.add_argument("--a2-report", type=Path, required=True)
    p = _add(sub, "tuning-check", s.cmd_tuning_check)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--round", type=int, required=True)
    _add(sub, "finish-tuning", s.cmd_finish_tuning).add_argument("--root", type=Path, required=True)
    _add(sub, "tuning-choose", s.cmd_tuning_choose).add_argument("--root", type=Path, required=True)
    p = _add(sub, "validation-gates", s.cmd_validation_gates)
    p.add_argument("--a2", action="append", required=True, metavar="PLANT=REPORT")
    p.add_argument("--b", action="append", required=True, metavar="PLANT=REPORT")
    p.add_argument("--out", type=Path, required=True)
    p = _add(sub, "smoke-cells", s.cmd_smoke_cells)
    p.add_argument("--plant", action="append", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--fail", choices=["g1", "g1b", "g1b2"])
    p = _add(sub, "freeze-check", s.cmd_freeze_check)
    p.add_argument("--porcelain", type=Path, required=True)
    p.add_argument("--part-a", type=Path, required=True)
    p.add_argument("--changed", type=Path)
    p.add_argument("--chosen-b-code", type=Path, required=True)
    p.add_argument("--head", required=True)
    p = _add(sub, "freeze-write", s.cmd_freeze_write)
    p.add_argument("--prereg", type=Path, required=True)
    p.add_argument("--files", type=Path, required=True)
    p.add_argument("--head", required=True)
    p = _add(sub, "prereg-b", s.cmd_prereg_b)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--prereg", type=Path, required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--extra", type=Path, nargs="*", default=[])
    p = _add(sub, "d10-write", s.cmd_d10_write)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--prereg", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    """The command-line parser (exposed for the tests)."""
    parser = argparse.ArgumentParser(
        prog="python -m plantgraph.qa.exp0009.launcher", description=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for register in (_plants, _money, _runs, _state, _tuning_and_freeze):
        register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command; print a failure as `ERROR: ...` and return 1."""
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except (ValueError, KeyError, FileNotFoundError, FileExistsError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
