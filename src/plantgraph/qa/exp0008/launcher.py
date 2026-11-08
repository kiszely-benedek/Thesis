"""`python -m plantgraph.qa.exp0008.launcher <command>`: the helpers of `run_all.sh`.

The shell scripts only sequence work; every decision that needs arithmetic, hashing or parsing is a
command here, so that it has a test. A command that fails prints `ERROR: <what was expected, found>`
on stderr and exits 1.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from plantgraph.ingest.seed_plan import DEFAULT_SEED_PLAN_PATH
from plantgraph.qa.exp0008 import launcher_commands as c
from plantgraph.qa.exp0008.caps import COST_PER_QUESTION_USD, STEP_CEILING_USD
from plantgraph.qa.exp0008.plan import KINDS
from plantgraph.qa.exp0008.smoke_evidence import cmd_smoke_evidence


def _add(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Callable[..., None],
) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, help=(handler.__doc__ or "").split("\n")[0])
    parser.set_defaults(handler=handler)
    return parser


def _path(parser: argparse.ArgumentParser, *names: str, required: bool = True) -> None:
    for name in names:
        parser.add_argument(name, type=Path, required=required)


def _add_money(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = _add(sub, "plan", c.cmd_plan)
    p.add_argument("kind", choices=KINDS)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_PLAN_PATH)
    p = _add(sub, "run-cap", c.cmd_run_cap)
    _path(p, "--misses", "--root", "--step-dir")
    _path(p, "--run-dir", required=False)
    p.add_argument("--tier", required=True, choices=sorted(COST_PER_QUESTION_USD))
    p.add_argument("--step", required=True, choices=sorted(STEP_CEILING_USD))
    p = _add(sub, "fixed-cap", c.cmd_fixed_cap)
    _path(p, "--root", "--step-dir")
    p.add_argument("--own", type=float, required=True, help="the step's own cap in dollars")
    p.add_argument("--step", required=True, choices=sorted(STEP_CEILING_USD))
    p = _add(sub, "plan-ids", c.cmd_plan_ids)
    _path(p, "--plan", "--out")
    p.add_argument("--corpus", required=True)
    p = _add(sub, "audit-cap", c.cmd_audit_cap)
    _path(p, "--root")
    p = _add(sub, "spent", c.cmd_spent)
    _path(p, "--root")
    p = _add(sub, "cost-of", c.cmd_cost_of)
    p.add_argument("--tier", required=True, choices=sorted(COST_PER_QUESTION_USD))
    p = _add(sub, "balance", c.cmd_balance)
    p.add_argument("--needed", type=float, required=True)
    p.add_argument("--fake-balance", type=float, help="the smoke: no network, this many dollars")


def _add_state_and_gates(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = _add(sub, "state-write", c.cmd_state_write)
    _path(p, "--dir")
    p.add_argument("--stage", required=True)
    p.add_argument("outputs", nargs="+", type=Path)
    p = _add(sub, "state-check", c.cmd_state_check)
    _path(p, "--dir")
    p.add_argument("--stage", required=True)
    p = _add(sub, "stopped", c.cmd_stopped)
    _path(p, "--dir")
    for name in ("--stage", "--reason", "--resume"):
        p.add_argument(name, required=True)
    p = _add(sub, "g1", c.cmd_g1)
    _path(p, "--out")
    p.add_argument(
        "--plant", action="append", required=True, metavar="PLANT|TUNE_REPORT|DEV_REPORT"
    )
    p = _add(sub, "g2", c.cmd_g2)
    _path(p, "--verdicts", "--out")
    p = _add(sub, "memory-probe", c.cmd_memory_probe)
    _path(p, "--out")
    p.add_argument("--limit-gib", type=float)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p = _add(sub, "replay-compare", c.cmd_replay_compare)
    _path(p, "--replay-dir", "--run-dir")
    p.add_argument("--allow-prefix", choices=["yes", "no"], default="no")
    p = _add(sub, "check-run-config", c.cmd_check_run_config)
    _path(p, "--run-dir")
    p.add_argument("--corpora-root", type=Path)


def _add_freeze(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = _add(sub, "freeze-check", c.cmd_freeze_check)
    _path(p, "--porcelain", "--part-a")
    _path(p, "--changed", required=False)
    p.add_argument("--head", required=True)
    p = _add(sub, "freeze-write", c.cmd_freeze_write)
    _path(p, "--prereg", "--files")
    p.add_argument("--head", required=True)
    p = _add(sub, "prereg-b", c.cmd_prereg_b)
    _path(p, "--root", "--prereg", "--taus")
    p.add_argument("--head", required=True)
    p.add_argument(
        "--extra", type=Path, nargs="*", default=[], help="more files PREREG.sha256 covers"
    )
    p = _add(sub, "smoke-evidence", cmd_smoke_evidence)
    p.add_argument("what", choices=["g1", "g2"])
    _path(p, "--out-dir")
    p.add_argument("--fail", action="store_true", help="write evidence that makes the gate fail")


def build_parser() -> argparse.ArgumentParser:
    """The command-line parser (exposed for the tests)."""
    parser = argparse.ArgumentParser(
        prog="python -m plantgraph.qa.exp0008.launcher", description=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_money(sub)
    _add_state_and_gates(sub)
    _add_freeze(sub)
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
