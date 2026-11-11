"""The launcher's helper commands, one small function each (`launcher.py` maps the shell onto them).

Every command prints what the shell needs on stdout and signals failure by raising; `launcher.main`
turns a raised error into `ERROR: <message>` on stderr and exit code 1.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plantgraph.exp0004.e2e_dry_run import DryRunReport
from plantgraph.ingest.seed_plan import load_seed_plan
from plantgraph.qa.audit.budget import SpendLedger
from plantgraph.qa.audit.judge import judge_pin, template_sha256
from plantgraph.qa.audit.models import ItemsFile
from plantgraph.qa.audit.report import g2_verdict
from plantgraph.qa.audit.runner import read_records
from plantgraph.qa.exp0008 import balance, caps, freeze, gates, ledger, memory_probe, replay, state
from plantgraph.qa.exp0008.plan import Plan, SeedTable
from plantgraph.qa.exp0008.prereg_b import PartB, render_part_b
from plantgraph.qa.harness.freeze import corpus_ingest_hashes
from plantgraph.qa.models import RunConfig


def cmd_plan(args: argparse.Namespace) -> None:
    """Print `corpus_id sheets seed duplication_rate variant(0|1)` for one kind of plant."""
    if args.smoke:
        seeds = SeedTable.smoke()
    else:
        drawn = load_seed_plan(args.seed_file)
        if drawn is None:
            raise ValueError(f"expected the drawn seeds at {args.seed_file}, found no file")
        seeds = SeedTable.from_plan(drawn)
    for plant in Plan(seeds, smoke=args.smoke).by_kind(args.kind):
        print(plant.corpus_id, plant.sheets, plant.seed, plant.duplication_rate, int(plant.variant))


def cmd_run_cap(args: argparse.Namespace) -> None:
    """Print a run's cap from its dry run, bounded by the step ceiling and the $30 runs ledger.

    A run that already spent money (a resume after a stop) keeps that spend under the new cap,
    because the harness counts a run's whole spend against its cap.
    """
    misses = DryRunReport.model_validate_json(args.misses.read_text(encoding="utf-8"))
    dry_cap = caps.run_cap_usd(misses.n_questions_with_miss, args.tier)
    ceiling = caps.STEP_CEILING_USD[args.step]
    if args.run_dir is None:
        print(ledger.run_cap_usd(dry_cap, args.root, args.step_dir, ceiling))
    else:
        print(ledger.resumed_run_cap_usd(dry_cap, args.root, args.step_dir, ceiling, args.run_dir))


def cmd_fixed_cap(args: argparse.Namespace) -> None:
    """Print a cap for a step with no dry run (D4, EX01), bounded as `run-cap` is."""
    ceiling = caps.STEP_CEILING_USD[args.step]
    print(ledger.run_cap_usd(args.own, args.root, args.step_dir, ceiling))


def cmd_plan_ids(args: argparse.Namespace) -> None:
    """Write the question ids a selected audit plan holds for one corpus, one per line."""
    items = json.loads(args.plan.read_text(encoding="utf-8"))["items"]
    ids = sorted({i["row"]["question_id"] for i in items if i["row"]["corpus_id"] == args.corpus})
    args.out.write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")


def cmd_audit_cap(args: argparse.Namespace) -> None:
    """Print the audit's cap: $10, or what is left of the $40 program cap."""
    print(ledger.audit_cap_usd(args.root))


def cmd_spent(args: argparse.Namespace) -> None:
    """Print what the runs and the audit have paid so far."""
    runs, audit = ledger.runs_spent_usd(args.root), ledger.audit_spent_usd(args.root)
    print(
        f"runs ${runs:.4f} of ${ledger.RUNS_CAP_USD:.0f}; "
        f"audit ${audit:.4f} of ${ledger.AUDIT_CAP_USD:.0f}"
    )


def _fake_credits(balance_usd: float) -> balance.CreditsFetcher:
    reply = json.dumps({"data": {"total_credits": balance_usd, "total_usage": 0}})
    return lambda: reply


def cmd_balance(args: argparse.Namespace) -> None:
    """Read the OpenRouter balance and require `--needed` dollars of it (never prints the key)."""
    if args.fake_balance is not None:  # the smoke: no network
        fetch = _fake_credits(args.fake_balance)
    else:
        fetch = balance.fetch_credits_json
    print(f"balance ${balance.require_balance(args.needed, fetch):.2f} (needed ${args.needed:.2f})")


def cmd_state_write(args: argparse.Namespace) -> None:
    """Write `<stage>.done` with the hashes of the stage's output files."""
    state.write_done(args.dir, args.stage, args.outputs)


def cmd_state_check(args: argparse.Namespace) -> None:
    """Succeed if the stage is done and its outputs are unchanged; else raise with the reason."""
    problem = state.done_problem(args.dir, args.stage)
    if problem is not None:
        raise ValueError(problem)


def cmd_stopped(args: argparse.Namespace) -> None:
    """Write `STOPPED` with the stage, the reason and the resume command."""
    state.write_stopped(args.dir, args.stage, args.reason, args.resume)


def cmd_g1(args: argparse.Namespace) -> None:
    """Gate G1 over `PLANT|TUNE_REPORT|DEV_REPORT` triples; writes the verdict, raises on a fail."""
    evidence = []
    for spec in args.plant:
        plant, tune, dev = spec.split("|", 2)  # not ":", which a Windows path contains
        evidence.append(gates.read_evidence(plant, Path(tune), Path(dev)))
    verdict = gates.g1_verdict(evidence)
    args.out.write_text(verdict.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(gates.describe(verdict))
    if not verdict.passed:
        raise ValueError("gate G1 failed")


def cmd_g2(args: argparse.Namespace) -> None:
    """Gate G2 over every row of the pilot set; writes the verdict, raises on a fail."""
    plan = ItemsFile.model_validate_json(args.plan.read_text(encoding="utf-8"))
    verdict = g2_verdict(plan.items, read_records(args.verdicts))
    args.out.write_text(verdict.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(
        f"defects found {verdict.n_defect_found}/{verdict.n_defect}; "
        f"controls correct {verdict.n_control_correct}/{verdict.n_control}"
    )
    if not verdict.passed:
        raise ValueError("gate G2 failed")


def cmd_memory_probe(args: argparse.Namespace) -> None:
    """Run the command after `--` and record its peak memory; raise over the limit."""
    limit = int(args.limit_gib * 2**30) if args.limit_gib else None
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = memory_probe.probe(command, limit)
    args.out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(
        f"peak {result.peak_rss_bytes / 2**30:.2f} GiB of {result.limit_bytes / 2**30:.2f}; "
        f"{result.seconds}s; rc {result.return_code}"
    )
    if not result.passed:
        raise ValueError("the pool memory probe failed")


def cmd_check_run_config(args: argparse.Namespace) -> None:
    """Fail unless the run froze its code and corpus hashes (F7: hand-built configs leave none)."""
    path = args.run_dir / "run_config.json"
    config = RunConfig.model_validate_json(path.read_text(encoding="utf-8"))
    if not config.code_hashes or not config.corpus_ingest_sha256:
        raise ValueError(f"expected code_hashes and corpus_ingest_sha256 in {path}, found empty")
    if args.corpora_root:
        now = corpus_ingest_hashes(sorted(config.corpus_ingest_sha256), args.corpora_root)
        if now != config.corpus_ingest_sha256:
            raise ValueError(f"expected {path} to hash the ingest.json in {args.corpora_root}")


def cmd_freeze_check(args: argparse.Namespace) -> None:
    """M3's preconditions: clean frozen paths, HEAD as part A names it."""
    freeze.check_clean(args.porcelain.read_text(encoding="utf-8"))
    named = freeze.named_head(args.part_a.read_text(encoding="utf-8"))
    changed = args.changed.read_text(encoding="utf-8").split() if args.changed else []
    freeze.check_head(args.head, named, changed)
    print(f"freeze preconditions hold at {args.head[:10]} (part A names {named[:10]})")


def cmd_freeze_write(args: argparse.Namespace) -> None:
    """Write E9.commit and E9.sha256 over the files listed in `--files`; print the file count."""
    names = args.files.read_text(encoding="utf-8").splitlines()
    commit_file = args.prereg / "E9.commit"
    commit_file.write_text(args.head + "\n", encoding="utf-8", newline="\n")
    print(freeze.write_hash_file(args.prereg / "E9.sha256", [Path(n) for n in names if n.strip()]))


def _part_b(args: argparse.Namespace) -> PartB:
    root, prereg = args.root, args.prereg
    taus = json.loads(args.taus.read_text(encoding="utf-8"))
    audit_ledger = SpendLedger(root / "audit" / "ledger.jsonl")
    g2 = json.loads((root / "state" / "g2.json").read_text(encoding="utf-8"))
    g1_text = (root / "state" / "g1.json").read_text(encoding="utf-8")
    e9_lines = (prereg / "E9.sha256").read_text(encoding="utf-8").splitlines()
    return PartB(
        code_commit=args.head,
        g1=gates.G1Verdict.model_validate_json(g1_text),
        tau1=taus["tau1"],
        tau2=taus["tau2"],
        pilot_rows=len(read_records(root / "audit" / "pilot" / "verdicts.jsonl")),
        pilot_mean_call_usd=audit_ledger.measured_cost_per_call("pilot"),
        pilot_spent_usd=audit_ledger.spent_usd("pilot"),
        g2_defects_found=f"{g2['n_defect_found']}/{g2['n_defect']}",
        g2_controls_correct=f"{g2['n_control_correct']}/{g2['n_control']}",
        judge_template_sha256=template_sha256(),
        judge_pin_sha256=judge_pin().pin_hash(),
        step_caps_usd=dict(caps.STEP_CEILING_USD),
        e9_sha256_file_sha256=freeze.sha256_of(prereg / "E9.sha256"),
        e9_files=len(e9_lines),
    )


def cmd_prereg_b(args: argparse.Namespace) -> None:
    """Write PREREG_B.md from the stage outputs, then PREREG.sha256 over everything registered."""
    prereg = args.prereg
    out = prereg / "PREREG_B.md"
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(render_part_b(_part_b(args)))
    names = ("PREREG_A.md", "PREREG_B.md", "seeds.json", "E9.commit", "E9.sha256")
    count = freeze.write_hash_file(
        prereg / "PREREG.sha256", [prereg / n for n in names] + args.extra
    )
    print(f"wrote {out}; PREREG.sha256 lists {count} files")


def cmd_cost_of(args: argparse.Namespace) -> None:
    """Print a tier's cost per question (the harness reserves it for each question in flight)."""
    print(caps.COST_PER_QUESTION_USD[args.tier])


def cmd_replay_compare(args: argparse.Namespace) -> None:
    """Compare a cache-only replay with its run; print the verdict, raise if they differ."""
    verdict = replay.compare(
        args.replay_dir / "answers.jsonl",
        args.run_dir / "answers.jsonl",
        args.allow_prefix == "yes",
    )
    print(verdict)
