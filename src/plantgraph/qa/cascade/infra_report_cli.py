"""The `infra-report` sub-command: read the measurement files, write the Markdown report."""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.infra.report import build_infra_report
from plantgraph.infra.report_inputs import ReportRequest, load_report_inputs
from plantgraph.infra.report_render import write_infra_report


def add_report_arguments(command: argparse.ArgumentParser) -> None:
    """The options of `infra-report`: where the files are, which corpora and runs, the output."""
    command.add_argument("--ingest-root", required=True, type=Path, help="<root>/<corpus>/rep<k>/")
    command.add_argument(
        "--probe-root", required=True, type=Path, help="<root>/<corpus>/rep<k>.json"
    )
    command.add_argument("--runs-root", required=True, type=Path, help="holds the replay runs")
    command.add_argument(
        "--corpus", action="append", required=True, help="corpus-level data; repeat, smallest first"
    )
    command.add_argument(
        "--compute-corpus", action="append", required=True, help="corpora that were replayed"
    )
    command.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="ROLE=NAME_TEMPLATE",
        help="a replay run, with {c} for the corpus (e.g. cypher=INF-CYPL-{c})",
    )
    command.add_argument(
        "--old-run",
        action="append",
        default=[],
        metavar="ROLE=NAME_TEMPLATE",
        help="the original run, shown instead when the role's replay is missing or differs",
    )
    command.add_argument(
        "--db-replay",
        action="append",
        default=[],
        metavar="ROLE=NAME_TEMPLATE",
        help="a database-only replay (infra-cypher-replay) used for the role instead of --run",
    )
    command.add_argument("--old-runs-root", type=Path, default=Path("data/runs/cv1/runs"))
    command.add_argument(
        "--price-json", type=Path, help="hand-filled reference price; absent file: no money table"
    )
    command.add_argument("--out", required=True, type=Path, help="the Markdown file to write")


def _role_templates(values: list[str]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for value in values:
        role, separator, template = value.partition("=")
        if not separator or not role or "{c}" not in template:
            raise SystemExit(f"error: expected ROLE=NAME_WITH_{{c}}, found {value!r}")
        templates[role] = template
    return templates


def report_command(args: argparse.Namespace) -> None:
    """Load the files, build the report, write it and print it."""
    request = ReportRequest(
        ingest_root=args.ingest_root,
        probe_root=args.probe_root,
        runs_root=args.runs_root,
        corpora=args.corpus,
        compute_corpora=args.compute_corpus,
        replay_templates=_role_templates(args.run),
        old_run_templates=_role_templates(args.old_run),
        old_runs_root=args.old_runs_root,
        db_replay_templates=_role_templates(args.db_replay),
        price_json=args.price_json,
    )
    report = build_infra_report(load_report_inputs(request))
    out = write_infra_report(report, args.out)
    print(out.read_text(encoding="utf-8"))
    print(f"wrote {out} and {out.with_suffix('.json')}")
