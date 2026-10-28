"""`python -m plantgraph.qa.exp0007 <command>`: the free helpers the EXP-0007 run scripts call.

No command here makes a model call or touches Neo4j. Exit codes: 0 ok, 1 a check failed (the
message says what was expected and found), 4 the pilot's correction is above the stop limit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plantgraph.qa.exp0001.prompt_size import parse_corpus_args
from plantgraph.qa.exp0007 import cap_plans, hygiene, paths
from plantgraph.qa.exp0007 import caps as caps_module
from plantgraph.qa.exp0007.dev_report import load_dev_report, write_dev_report
from plantgraph.qa.exp0007.freeze_checks import files_equal, ingest_problems, pins_match_policy
from plantgraph.qa.exp0007.health import (
    fetch_listing,
    health_fault,
    outcome_counts,
    write_listing,
)
from plantgraph.qa.exp0007.pilot import (
    MAX_CORRECTION,
    PILOT_FAMILIES,
    V1_BASELINE_RUNS,
    TierCorrection,
    correction_of,
    filter_questions,
    head_questions,
    read_v1_baseline,
)
from plantgraph.qa.exp0007.prompt_inputs import prompt_inputs_of, write_prompt_inputs
from plantgraph.qa.exp0007.run_costs import read_question_costs
from plantgraph.qa.exp0007.tune_cli import add_tune_commands

EXIT_CHECK_FAILED = 1
EXIT_CORRECTION_TOO_HIGH = 4


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return EXIT_CHECK_FAILED


def _cmd_check_paths(args: argparse.Namespace) -> int:
    commit = args.f1_commit_file.read_text(encoding="utf-8").strip()
    bad = paths.check_paths(args.repo, commit)
    if bad:
        return _fail(
            f"expected no system-side change since F1 {commit[:7]} beyond the six named "
            f"files, found {bad}"
        )
    print(f"ok: no system-side path differs from F1 {commit[:7]} except the six named files")
    return 0


def _cmd_check_inputs(args: argparse.Namespace) -> int:
    problems = pins_match_policy(args.sealed_inputs)
    for name in args.same_as_sealed:
        if not files_equal(args.inputs / name, args.sealed_inputs / name):
            problems.append(f"{args.inputs / name} differs from {args.sealed_inputs / name}")
    if problems:
        return _fail("; ".join(problems))
    print("ok: pins match cascade_v3 and the copied inputs equal the sealed ones")
    return 0


def _cmd_check_seeds(args: argparse.Namespace) -> int:
    hygiene.assert_registered_seeds()
    hygiene.require_no_leaked_seeds(args.data_root, args.exclude)
    print("ok: TEST_SEEDS_V2 is the registered table and no earlier record holds a test seed")
    return 0


def _cmd_check_neo4j_target(args: argparse.Namespace) -> int:
    print(hygiene.require_database(args.database, args.is_plant_db))
    return 0


def _cmd_check_listing(args: argparse.Namespace) -> int:
    listing = fetch_listing()
    if args.write_if_absent and not args.expected.exists():
        write_listing(args.expected, listing)
        print(f"wrote {args.expected}")
        return 0
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    if listing != expected:
        return _fail(f"expected Luna's listing to equal {args.expected}, found {listing}")
    print("ok: Luna's listing equals the registered one")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    counts = outcome_counts(args.run_dir)
    print(f"    {sum(counts.values())} rows: {dict(counts)}")
    fault = health_fault(counts)
    return _fail(f"technical fault in {args.run_dir}: {fault}") if fault else 0


def _cmd_filter_families(args: argparse.Namespace) -> int:
    families = list(PILOT_FAMILIES) if args.pilot_families else args.families.split(",")
    print(f"kept {filter_questions(args.source, args.out, families)} questions")
    return 0


def _cmd_head_questions(args: argparse.Namespace) -> int:
    head_questions(args.source, args.out, args.n)
    return 0


def _cmd_pilot_report(args: argparse.Namespace) -> int:
    result = {}
    for tier in V1_BASELINE_RUNS:
        run = args.pilot_runs / f"P7-{tier.upper()}-D100g2"
        v2_costs = read_question_costs(run)
        result[tier] = correction_of(tier, v2_costs, read_v1_baseline(args.cv1_runs, tier))
    args.out.write_text(
        json.dumps({t: c.model_dump() for t, c in result.items()}, indent=2) + "\n",
        encoding="utf-8",
    )
    for tier, c in result.items():
        print(
            f"{tier}: tokens {c.tokens_v2:,.0f} / {c.tokens_v1:,.0f} = {c.r_tokens:.3f}; "
            f"usd {c.usd_v2:.5f} / {c.usd_v1:.5f} = {c.r_usd:.3f}; correction used {c.r:.3f}"
        )
    if any(c.r > MAX_CORRECTION for c in result.values()):
        print(
            f"STOP: a correction is above {MAX_CORRECTION} (plan stop rule 2): ask the user",
            file=sys.stderr,
        )
        return EXIT_CORRECTION_TOO_HIGH
    return 0


def _read_corrections(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {tier: TierCorrection.model_validate(value).r for tier, value in raw.items()}


_STAGE_OPTIONS = {
    "dev": ("dev_questions",),
    "r4": ("ladder_questions",),
    "r5": ("sealed_questions", "c1_questions", "r4_runs"),
}


def _build_cap_file(args: argparse.Namespace) -> caps_module.CapFile:
    if args.stage == "pilot":
        return cap_plans.pilot_caps()
    if args.pilot_result is None:
        raise ValueError(f"expected --pilot-result for stage {args.stage}, found none")
    missing = [name for name in _STAGE_OPTIONS[args.stage] if getattr(args, name) is None]
    if missing:
        raise ValueError(
            f"expected --{', --'.join(m.replace('_', '-') for m in missing)} for stage {args.stage}"
        )
    corrections = _read_corrections(args.pilot_result)
    if args.stage == "dev":
        return cap_plans.dev_caps(args.cv1_runs, args.dev_questions, corrections, V1_BASELINE_RUNS)
    if args.stage == "r4":
        return cap_plans.r4_caps(args.runs_root, args.ladder_questions, corrections)
    return cap_plans.r5_caps(
        args.runs_root, args.sealed_questions, args.c1_questions, corrections, args.r4_runs
    )


def _cmd_make_caps(args: argparse.Namespace) -> int:
    caps = _build_cap_file(args)
    digest = caps_module.write_cap_file(args.out, caps)
    for e in caps.entries:
        print(
            f"{e.run_id:24s} n={e.n_questions:4d}  c={e.cost_per_question_usd:.6f}  "
            f"cap ${e.cap_usd:.2f}  ({e.basis})"
        )
    print(f"stage {caps.stage}: sum of caps ${caps.total_usd:.2f}")
    print(f"cap file {args.out}\nsha256 {digest}")
    return 0


def _cmd_cap_of(args: argparse.Namespace) -> int:
    caps = caps_module.load_verified(args.cap_file, args.cap_sha256)
    entry = caps_module.entry_for(caps, args.run_id)
    print(entry.cap_usd if args.field == "cap" else entry.cost_per_question_usd)
    return 0


def _cmd_check_ingest(args: argparse.Namespace) -> int:
    problems = ingest_problems(args.ingest_json, args.corpus_id)
    return _fail(f"{args.ingest_json}: {'; '.join(problems)}") if problems else 0


def _cmd_test_seed(args: argparse.Namespace) -> int:
    hygiene.assert_registered_seeds()
    print(hygiene.REGISTERED_TEST_SEEDS_V2[args.sheets])
    return 0


def _cmd_corpus_prompt_hashes(args: argparse.Namespace) -> int:
    items = [prompt_inputs_of(i, path) for i, path in parse_corpus_args(args.corpora)]
    write_prompt_inputs(args.out, items)
    print(f"wrote {args.out}")
    return 0


def _cmd_dev_report(args: argparse.Namespace) -> int:
    report = load_dev_report(
        args.corpus_id, args.cyp_run, args.ag_run, args.questions_root, args.cutoff_s
    )
    for path in write_dev_report(report, args.out):
        print(f"wrote {path}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0007", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: object) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.set_defaults(handler=handler)
        return command

    p = add("check-paths", _cmd_check_paths)
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--f1-commit-file", type=Path, required=True)
    p = add("check-inputs", _cmd_check_inputs)
    p.add_argument("--sealed-inputs", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--same-as-sealed", nargs="+", default=[])
    p = add("check-seeds", _cmd_check_seeds)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--exclude", type=Path, required=True)
    p = add("check-neo4j-target", _cmd_check_neo4j_target)
    p.add_argument("--database")
    p.add_argument("--is-plant-db", action="store_true")
    p = add("check-listing", _cmd_check_listing)
    p.add_argument("--expected", type=Path, required=True)
    p.add_argument("--write-if-absent", action="store_true")
    p = add("health", _cmd_health)
    p.add_argument("--run-dir", type=Path, required=True)
    p = add("filter-families", _cmd_filter_families)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--families")
    p.add_argument("--pilot-families", action="store_true")
    p = add("head-questions", _cmd_head_questions)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n", type=int, default=cap_plans.SMOKE_QUESTIONS)
    p = add("pilot-report", _cmd_pilot_report)
    p.add_argument("--pilot-runs", type=Path, required=True)
    p.add_argument("--cv1-runs", type=Path, default=Path("data/runs/cv1/runs"))
    p.add_argument("--out", type=Path, required=True)
    _add_make_caps(add("make-caps", _cmd_make_caps))
    p = add("cap-of", _cmd_cap_of)
    p.add_argument("--cap-file", type=Path, required=True)
    p.add_argument("--cap-sha256", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--field", choices=["cap", "cost"], default="cap")
    p = add("check-ingest", _cmd_check_ingest)
    p.add_argument("--ingest-json", type=Path, required=True)
    p.add_argument("--corpus-id", required=True)
    p = add("test-seed", _cmd_test_seed)
    p.add_argument("--sheets", type=int, required=True)
    p = add("corpus-prompt-hashes", _cmd_corpus_prompt_hashes)
    p.add_argument("corpora", nargs="+", metavar="ID=INGEST_JSON")
    p.add_argument("--out", type=Path, required=True)
    p = add("dev-report", _cmd_dev_report)
    p.add_argument("--corpus-id", required=True)
    p.add_argument("--cyp-run", type=Path, required=True)
    p.add_argument("--ag-run", type=Path, required=True)
    p.add_argument("--questions-root", type=Path, required=True)
    p.add_argument("--cutoff-s", type=float, default=120.0)
    p.add_argument("--out", type=Path, required=True)
    add_tune_commands(sub)
    return parser


def _add_make_caps(p: argparse.ArgumentParser) -> None:
    p.add_argument("--stage", choices=["pilot", "dev", "r4", "r5"], required=True)
    p.add_argument("--pilot-result", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cv1-runs", type=Path, default=Path("data/runs/cv1/runs"))
    p.add_argument("--dev-questions", type=Path)
    p.add_argument("--runs-root", type=Path, default=Path("data/runs"))
    p.add_argument("--ladder-questions", type=Path)
    p.add_argument("--sealed-questions", type=Path)
    p.add_argument("--c1-questions", type=Path)
    p.add_argument("--r4-runs", type=Path)


def main(argv: list[str] | None = None) -> None:
    """Parse argv and run the chosen command; exit with its code."""
    args = _parser().parse_args(argv)
    try:
        code = args.handler(args)
    except (ValueError, KeyError, FileNotFoundError, FileExistsError, RuntimeError) as error:
        code = _fail(str(error))
    raise SystemExit(code)
