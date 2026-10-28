"""The `tune-report` sub-command: score cascade_v4 and cascade_v4_iso on stored V2T runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.cascade.join import TierSource
from plantgraph.qa.cascade.limits import SETTINGS
from plantgraph.qa.cascade.tune_compare import (
    family_changes,
    regressed_families,
    round_change,
    round_verdict,
)
from plantgraph.qa.cascade.tune_models import TuneReport
from plantgraph.qa.cascade.tune_render import render_tune_report, write_tune_report
from plantgraph.qa.cascade.tune_report import build_tune_report
from plantgraph.qa.cascade.tune_select import V4


def add_tune_arguments(command: argparse.ArgumentParser) -> None:
    """Declare the arguments of `tune-report`."""
    command.add_argument("--corpus", required=True)
    command.add_argument("--setting", required=True, choices=sorted(SETTINGS))
    command.add_argument("--questions-root", required=True, type=Path)
    command.add_argument("--corpora-root", required=True, type=Path, help="<corpus>/ingest.json")
    command.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="TIER=RUN_DIR",
        help="tier cypher-v2t and tier agent-v2t, one stored run each",
    )
    command.add_argument("--previous", type=Path, help="the last round's tune_report.json")
    command.add_argument("--out", required=True, type=Path, help="directory for the report files")


def tune_command(args: argparse.Namespace) -> None:
    """Build, write and print the report; with `--previous`, list families that dropped."""
    sources = dict(_parse_run(value) for value in args.run)
    report = build_tune_report(
        args.corpus, SETTINGS[args.setting], sources, args.questions_root, args.corpora_root
    )
    changes = None
    if args.previous is not None:
        previous = TuneReport.model_validate_json(args.previous.read_text(encoding="utf-8"))
        changes = family_changes(report, previous, V4)
        dropped = regressed_families(changes)
        print(f"families that lost 2 or more questions (stop rule 3): {dropped or 'none'}")
        verdict = round_verdict(round_change(report, previous, V4))
        print(f"setting {args.setting}, cascade_v4 against the previous round: {verdict}")
    markdown, json_path = write_tune_report(report, args.out, changes)
    print(render_tune_report(report, changes))
    print(f"wrote {markdown} and {json_path}")


def _parse_run(value: str) -> tuple[str, TierSource]:
    name, separator, location = value.partition("=")
    if not separator or not name:
        raise SystemExit(f"error: expected --run TIER=RUN_DIR, found {value!r}")
    return name, TierSource(Path(location))
