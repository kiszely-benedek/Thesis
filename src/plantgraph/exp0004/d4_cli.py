"""Command-line side of the D4 commands: shared flags, and running them with readable errors."""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.exp0004 import d4_commands
from plantgraph.exp0004.d4_session import DEFAULT_CACHE_PATH, DEFAULT_PIN_PATH, LlmOptions
from plantgraph.llm.models import CacheMiss
from plantgraph.qa.harness.spend_cap import SpendCapReached


def add_llm_arguments(parser: argparse.ArgumentParser) -> None:
    """The flags every command that calls the model takes."""
    parser.add_argument(
        "--allow-paid-calls",
        action="store_true",
        help="permit real, billed model calls (without it: cache-only, stops at the first miss)",
    )
    parser.add_argument(
        "--max-spend-usd", type=float, help="hard cap; required with the flag above"
    )
    parser.add_argument("--pin-json", type=Path, default=DEFAULT_PIN_PATH)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)


def options_from(args: argparse.Namespace) -> LlmOptions:
    """The model options from parsed arguments (the flag comes only from the command line)."""
    return LlmOptions(
        allow_paid_calls=args.allow_paid_calls,
        max_spend_usd=args.max_spend_usd,
        pin_path=args.pin_json,
        cache_path=args.cache_path,
    )


def is_llm_command(args: argparse.Namespace) -> bool:
    """True for `decide --decider d4`, `pilot` and `open100`."""
    if args.command in ("pilot", "open100"):
        return True
    return bool(args.command == "decide" and args.decider == "d4")


def run_llm_command(args: argparse.Namespace) -> None:
    """Run one model-calling command; a miss, a reached cap or a bad flag ends it with a message."""
    options = options_from(args)
    try:
        _dispatch(args, options)
    except (CacheMiss, SpendCapReached, ValueError) as error:
        raise SystemExit(f"error: {error}") from error


def _dispatch(args: argparse.Namespace, options: LlmOptions) -> None:
    if args.command == "pilot":
        print(d4_commands.pilot(args.directory, args.n, options).model_dump_json(indent=1))
    elif args.command == "open100":
        d4_commands.open100(args.out, options)
        print(args.out)
    else:
        run = d4_commands.decide_d4(args.directory, options)
        print(run.model_dump_json(include={"pair_level", "llm"}, indent=1))
