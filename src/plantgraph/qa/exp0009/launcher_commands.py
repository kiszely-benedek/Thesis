"""The launcher's commands about plants, questions, money and records (one small function each).

`launcher.py` maps the shell onto these. A command prints what the shell needs on stdout and
signals failure by raising; `launcher.main` turns a raised error into `ERROR: <message>` on stderr
and exit code 1.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plantgraph.ingest.seed_plan import SeedPlan, load_seed_plan
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0007.paths import check_paths
from plantgraph.qa.exp0008.draw_seeds import draw_seed_plan
from plantgraph.qa.exp0008.hygiene import retired_seeds
from plantgraph.qa.exp0008.ledger import audit_spent_usd
from plantgraph.qa.exp0009 import (
    build,
    caps,
    draw,
    gates,
    ledger,
    load,
    question_files,
    questions,
    records,
    stages,
)
from plantgraph.qa.exp0009.plan import Exp0009Plan, PlantSpec22, Role
from plantgraph.qa.exp0009.smoke_plan import smoke_plan, smoke_prior_text
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env


def read_plan(prereg: Path) -> Exp0009Plan:
    """`plan.json` of the pre-registration folder."""
    return Exp0009Plan.model_validate_json((prereg / draw.PLAN_FILE).read_text(encoding="utf-8"))


def cmd_draw(args: argparse.Namespace) -> None:
    """Draw seeds, sizes, tagging and the text prior; write them once; print the PREREG A tables."""
    if args.smoke:
        prior = smoke_prior_text()
        plan = smoke_plan(prior)
        args.prereg.mkdir(parents=True, exist_ok=True)
        (args.prereg / draw.PLAN_FILE).write_text(plan.model_dump_json(indent=2) + "\n", "utf-8")
        (args.prereg / draw.PRIOR_FILE).write_bytes(prior.encode("utf-8"))
        (args.prereg / draw.SEEDS_FILE).write_text('{"smoke": true}\n', encoding="utf-8")
        return
    seeds = draw_seed_plan(args.draw_seed, retired_seeds(args.runs_root), args.runs_root)
    prior = draw.real_prior_text()
    plan = draw.draw_plan(args.draw_seed, seeds, draw.real_sizer, draw.real_document_flags, prior)
    draw.write_draw(args.prereg, seeds, plan, prior)
    print(draw.render_tables(seeds, plan))


def cmd_plan_list(args: argparse.Namespace) -> None:
    """Print `plant_id scale seed` for the plants of one role (`all` = every plant)."""
    plan = read_plan(args.prereg)
    plants = plan.plants if args.kind == "all" else plan.of_role(Role(args.kind))
    for spec in plants:
        print(spec.plant_id, spec.scale, spec.seed)


def _seeds(prereg: Path, smoke: bool) -> SeedPlan | None:
    return None if smoke else load_seed_plan(prereg / draw.SEEDS_FILE)


def cmd_build(args: argparse.Namespace) -> None:
    """Build one plant (A, B relabel, positions) and run its build-time gates; raise on a fail."""
    spec = read_plan(args.prereg).plant(args.plant)
    corpora = args.root / "corpora"
    build.build_plant(spec, corpora, _seeds(args.prereg, args.smoke))
    results = _build_gates(spec, corpora, check_band=not args.smoke)
    out = corpora / spec.plant_id / "gates.json"
    out.write_text(json.dumps([r.model_dump() for r in results], indent=1) + "\n", "utf-8")
    failed = [r for r in results if not r.passed]
    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'} {result.gate}: {result.detail}")
    if failed:
        raise ValueError(f"build gates failed for {spec.plant_id}: {[r.gate for r in failed]}")


def _build_gates(spec: PlantSpec22, corpora: Path, check_band: bool) -> list[gates.GateResult]:
    a_ingest = corpora / spec.plant_id / build.INGEST_FILE
    return [
        gates.g0c_rules(corpora / spec.plant_id / build.RULES_FILE),
        gates.g0c_validation(spec),
        gates.g0g(a_ingest, spec.plant_id),
        gates.g0k(spec, a_ingest, check_band=check_band),
        gates.line_view(spec.plant_id, a_ingest),
        gates.g0b_checks(spec.b_id, corpora / spec.b_id, spec),
    ]


def cmd_load_a(args: argparse.Namespace) -> None:
    """Wipe the database and load plant A with `plant_lines` (smoke: files only)."""
    settings = None if args.smoke else _settings()
    load.load_a(args.root, args.plant, settings)


def cmd_prepare_b_load(args: argparse.Namespace) -> None:
    """Prepare `cypcorp/plant_lines/<id>B/` for `python -m plantgraph.qa.v2tb load`."""
    print(load.prepare_b_load(args.root, args.plant))


def _settings() -> Neo4jSettings:
    settings = from_env()
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found them unset")
    return settings


def cmd_questions_pool(args: argparse.Namespace) -> None:
    """One pool step for a plant: scope R pool and the scope X candidates, from one corpus."""
    recipe = questions.RECIPES[args.recipe]
    pool = questions.run_pool_step(args.root / "corpora", args.root / "qpool", args.plant, recipe)
    print(f"{args.plant}: R pool {len(pool.r_pool)}, X kept {sum(map(len, pool.x_kept.values()))}")


def cmd_questions_files(args: argparse.Namespace) -> None:
    """After every pool of a role: the drop set, G0l, the samples and the A2 and B files."""
    plan = read_plan(args.prereg)
    role_plants = plan.of_role(Role(args.role))
    recipe = questions.SEALED if args.role == "sealed" else questions.DEV
    pools = {s.plant_id: questions.read_pool(args.root / "qpool" / s.plant_id) for s in role_plants}
    verdict = gates.g0l({pid: pool.reports for pid, pool in pools.items()})
    print(f"{verdict.gate}: {verdict.detail}")
    if not verdict.passed:
        raise ValueError(f"gate G0l failed: {verdict.detail} (back to the architect, ADR-0067)")
    drop = question_files.drop_set(pools, recipe.x_families)
    names = sorted(f.value for f in drop.all)
    print(f"drop set of the {args.role} plants: {names}")
    prior_text = (args.prereg / draw.PRIOR_FILE).read_text(encoding="utf-8")
    priors = question_files.load_priors(prior_text)
    for pid, pool in pools.items():
        counts = question_files.write_plant_files(
            pid, pool, drop, recipe, args.root / "questions", priors
        )
        print(f"{pid}: {counts}")
    (args.root / "questions" / f"drop_{args.role}.json").write_text(
        json.dumps(names, indent=1) + "\n", encoding="utf-8"
    )


def cmd_run_cap(args: argparse.Namespace) -> None:
    """Print a run's cap: questions x cost key x 1.5, cut to the step ceiling and the ledger."""
    n = len(args.questions.read_text(encoding="utf-8").splitlines())
    measured = json.loads(args.measured.read_text("utf-8")) if args.measured else None
    cost = caps.cost_per_question_usd(args.tier, args.scale, arm=args.arm, measured=measured)
    own = caps.run_cap_usd(n, cost)
    ceiling = caps.STEP_CEILING_USD[args.step]
    if args.run_dir is None:
        print(ledger.run_cap_usd(own, args.root, args.step_dir, ceiling))
    else:
        print(ledger.resumed_run_cap_usd(own, args.root, args.step_dir, ceiling, args.run_dir))


def cmd_cost_of(args: argparse.Namespace) -> None:
    """Print a tier's cost per question (the harness reserves it for every question in flight)."""
    measured = json.loads(args.measured.read_text("utf-8")) if args.measured else None
    print(caps.cost_per_question_usd(args.tier, args.scale, arm=args.arm, measured=measured))


def cmd_audit_cap(args: argparse.Namespace) -> None:
    """Print the audit's cap ($8.13, or what the runs leave of $35); `--left`: minus its spend."""
    total = ledger.audit_cap_usd(args.root)
    print(round(total - audit_spent_usd(args.root), 6) if args.left else total)


def cmd_spent(args: argparse.Namespace) -> None:
    """Print what the runs and the audit have paid so far."""
    print(ledger.summary(args.root))


def cmd_estimate(args: argparse.Namespace) -> None:
    """Print the cost estimate of a paid stage (question counts x measured cost per question)."""
    balance = "not read" if args.balance_usd is None else f"${args.balance_usd:.2f}"
    print(stages.render_estimate(args.stage, args.root, balance=balance))


def cmd_g0f(args: argparse.Namespace) -> None:
    """G0f: no system-side path changed since the E9 commit; print the list, raise if not empty."""
    commit = args.e9_commit.read_text(encoding="utf-8").strip()
    changed = check_paths(Path("."), commit)
    print(json.dumps(changed))
    if changed:
        raise ValueError(f"gate G0f failed: system-side files changed since E9: {changed[:5]}")


def cmd_records_check(args: argparse.Namespace) -> None:
    """The measurement-record check of one finished run; raise if it is incomplete."""
    records.require_complete_records(args.run_dir)


def cmd_rescore(args: argparse.Namespace) -> None:
    """Re-score a run offline; write precision, recall and F1 per row; raise on a mismatch."""
    artifacts_dir = args.questions_root / args.corpus_id / "questions.jsonl"
    from plantgraph.qa.questions.per_family import read_questions

    questions_list, _lines = read_questions(artifacts_dir)
    inputs = records.inputs_from_corpus(args.corpus_id, args.ingest_json, is_b=args.b)
    report = records.rescore(args.run_dir, {q.question_id: q for q in questions_list}, inputs)
    args.out.write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(
        f"re-scored {len(report.rows)} rows, {len(report.mismatches)} differ from the stored ones"
    )
    if report.mismatches:
        raise ValueError(f"re-score differs from the stored correct on {report.mismatches[:3]}")


def cmd_check_loadable(args: argparse.Namespace) -> None:
    """The corpus loads from its files (used on B ids after the relabel)."""
    load_corpus_artifacts(args.corpus_id, args.ingest_json)


def cmd_r14f(args: argparse.Namespace) -> None:
    """R14f on a B corpus: the item lines the B agent sees are exact; raise if not."""
    spec = read_plan(args.prereg).plant(args.plant)
    result = gates.r14f_exactness(spec.b_id, args.root / "corpora" / spec.b_id)
    print(f"{'PASS' if result.passed else 'FAIL'} {result.gate}: {result.detail}")
    if not result.passed:
        raise ValueError(f"gate R14f failed for {spec.b_id}: {result.detail}")
