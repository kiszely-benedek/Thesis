"""The launcher's commands about tuning, validation gates, the E10 freeze and the sealed draw hash.

Same contract as `launcher_commands.py`: print what the shell needs, raise on failure.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path

from plantgraph.qa.audit.models import AuditItem, SourceRow
from plantgraph.qa.cascade.join import TierSource
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0008.ledger import paid_usd_of_calls
from plantgraph.qa.exp0009 import audit_b, cascade_report, freeze, gates, prereg_b, stages
from plantgraph.qa.exp0009.audit_b import StratumRow
from plantgraph.qa.exp0009.cascade_report import ArmReport
from plantgraph.qa.exp0009.gates import FamilyCells
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import Question, QuestionResult, RunConfig
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES
from plantgraph.qa.v2tb.descriptor import PlantIndex


def cmd_cascade_report(args: argparse.Namespace) -> None:
    """The offline cascade of one arm on one plant over its two tier runs; write the report."""
    sources = {"cypher-v2t": TierSource(args.cyp_run), "agent-v2t": TierSource(args.ag_run)}
    report = cascade_report.build_arm_report(
        args.corpus_id, args.arm, sources, args.questions_root, args.corpora_root
    )
    args.out.write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"{report.corpus_id} {report.arm}: {report.n_correct}/{report.n_questions}")


_RUN_NAME = re.compile(r"V9-(CYP|AG)-\w*?(100|1000)g22(B?)")


def cmd_measure_costs(args: argparse.Namespace) -> None:
    """P1b's measured dollars per question, per arm, tier and scale, for P1c's caps."""
    costs: dict[str, float] = {}
    for run_dir in sorted((args.val_dir / "runs").glob("V9-*")):
        match = _RUN_NAME.fullmatch(run_dir.name)
        if match is None:
            continue
        tier, scale, is_b = match.group(1).lower(), match.group(2), match.group(3)
        n_rows = len(RunDir(run_dir).read_rows())
        paid = paid_usd_of_calls(run_dir / "calls.jsonl")
        if n_rows and paid > 0:  # a run that paid nothing (every reply cached) measures no cost
            costs[f"{'B' if is_b else 'A2'}-{tier}-{scale}"] = round(paid / n_rows, 6)
    args.out.write_text(json.dumps(costs, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(costs)


def _read_report(path: Path) -> ArmReport:
    return ArmReport.model_validate_json(path.read_text(encoding="utf-8"))


# ---- P1a: tuning rounds -----------------------------------------------------------------------


def _round_dirs(root: Path) -> list[Path]:
    return sorted((root / "tune").glob("round*"), key=lambda p: int(p.name.removeprefix("round")))


def cmd_tuning_round(args: argparse.Namespace) -> None:
    """Close round K: write `b_code.sha256` and `round.json`; print whether another round may run.

    Raises:
        ValueError: a fourth round, or B files equal to an earlier round's.
    """
    if args.round > stages.MAX_ROUNDS:
        raise ValueError(
            f"expected at most {stages.MAX_ROUNDS} tuning rounds, found round {args.round}"
        )
    folder = args.root / "tune" / f"round{args.round}"
    folder.mkdir(parents=True, exist_ok=True)
    earlier = {
        int(d.name.removeprefix("round")): freeze.sha256_of(d / "b_code.sha256")
        for d in _round_dirs(args.root)
        if (d / "b_code.sha256").is_file() and d != folder
    }
    code_hash = freeze.write_b_code_sha256(folder / "b_code.sha256")
    stages.require_new_b_code(earlier, code_hash)
    b_report, a2_report = _read_report(args.b_report), _read_report(args.a2_report)
    r_names = {f for f in {*b_report.by_family, *a2_report.by_family}} - {
        f.value for f in SCOPE_X_FAMILIES
    }
    row = prereg_b.TuningRound(
        number=args.round,
        change=args.change,
        b_dev_accuracy=round(b_report.accuracy(), 6),
        b_minus_a2_on_r=round(
            b_report.accuracy(frozenset(r_names)) - a2_report.accuracy(frozenset(r_names)), 6
        ),
    )
    (folder / "round.json").write_text(row.model_dump_json(indent=1) + "\n", encoding="utf-8")
    accuracies = [_round(d).b_dev_accuracy for d in _round_dirs(args.root)]
    allowed, why = stages.next_round_allowed(accuracies)
    print(
        f"round {row.number}: B dev {row.b_dev_accuracy:.4f}, B-A2 on R {row.b_minus_a2_on_r:+.4f}"
    )
    print(f"next_round={'yes' if allowed else 'no'} ({why})")


def _round(folder: Path) -> prereg_b.TuningRound:
    text = (folder / "round.json").read_text(encoding="utf-8")
    return prereg_b.TuningRound.model_validate_json(text)


def cmd_tuning_check(args: argparse.Namespace) -> None:
    """Before paying for round K: refuse a fourth round, a stopped tuning, or unchanged B files.

    Raises:
        ValueError: the round is not allowed, naming why.
    """
    done = [_round(d) for d in _round_dirs(args.root) if (d / "round.json").is_file()]
    if (args.root / "tune" / "FINISHED").exists():
        raise ValueError("expected tuning to be open, found it finished (finish-tuning)")
    if args.round != len(done) + 1:
        raise ValueError(f"expected round {len(done) + 1} to be next, found {args.round}")
    if done:
        allowed, why = stages.next_round_allowed([r.b_dev_accuracy for r in done])
        if not allowed:
            raise ValueError(f"expected another round to be allowed, found: {why}")
    current = freeze.digest_of_hashes(freeze.b_code_hashes())
    earlier = {
        int(d.name.removeprefix("round")): freeze.sha256_of(d / "b_code.sha256")
        for d in _round_dirs(args.root)
        if (d / "b_code.sha256").is_file()
    }
    stages.require_new_b_code(earlier, current)


def cmd_finish_tuning(args: argparse.Namespace) -> None:
    """End tuning: write `tune/FINISHED` and `tune/chosen_round.txt` (the E10 candidate)."""
    folder = args.root / "tune"
    rounds = [_round(d) for d in _round_dirs(args.root) if (d / "round.json").is_file()]
    chosen = prereg_b.choose_round(rounds).number
    (folder / "chosen_round.txt").write_text(f"{chosen}" + "\n", encoding="utf-8")
    with (folder / "FINISHED").open("x", encoding="utf-8") as handle:
        handle.write("tuning finished\n")
    print(f"tuning finished; the E10 candidate is round {chosen}")


def cmd_tuning_choose(args: argparse.Namespace) -> None:
    """Print the E10 candidate round: the highest B dev accuracy, a tie to the earlier round."""
    rounds = [_round(d) for d in _round_dirs(args.root) if (d / "round.json").is_file()]
    print(prereg_b.choose_round(rounds).number)


# ---- P1b: G1, G1-B, G1-B2 ---------------------------------------------------------------------


def _cells(specs: list[str]) -> FamilyCells:
    """`PLANT=report.json` pairs to family cells."""
    pairs = (spec.split("=", 1) for spec in specs)
    return {plant: _read_report(Path(path)).by_family for plant, path in pairs}


def cmd_validation_gates(args: argparse.Namespace) -> None:
    """G1 (A2), G1-B and G1-B2 from the validation cascade reports; write the verdicts.

    Raises:
        ValueError: G1 failed (a stop for the user). G1-B or G1-B2 failing only sets `b_sealed=no`.
    """
    a2, b = _cells(args.a2), _cells(args.b)
    results = [gates.g1(a2), gates.g1_b(b), gates.g1_b2(a2, b)]
    b_sealed = all(r.passed for r in results[1:])
    document = {"gates": [r.model_dump() for r in results], "b_sealed": b_sealed, "a2": a2, "b": b}
    args.out.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'} {result.gate}: {result.detail}")
    print(f"b_sealed={'yes' if b_sealed else 'no'}")
    if not results[0].passed:
        raise ValueError(f"gate G1 failed: {results[0].detail}")


def cmd_smoke_cells(args: argparse.Namespace) -> None:
    """Smoke only: canned cascade reports whose accuracies make a chosen gate pass or fail."""
    weak = {"g1": ("A2",), "g1b": ("B",), "g1b2": ()}.get(args.fail or "", ())
    good, bad = (9, 10), (2, 10)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for plant in args.plant:
        for arm, name in (("A2", "a2"), ("B", "b")):
            cells = {"FLOW_PATH": bad if arm in weak else good}
            if args.fail == "g1b2" and arm == "B":
                cells = {"FLOW_PATH": (6, 10)}
            if arm == "B":
                cells["OPEN_VALVES_TO_ISOLATE"] = good
            total = sum(t for _c, t in cells.values())
            report = ArmReport(
                corpus_id=plant,
                arm=arm,
                policy="smoke",
                n_questions=total,
                n_correct=sum(c for c, _t in cells.values()),
                by_family=cells,
                correct_ids=(),
            )
            (args.out_dir / f"{plant}_{name}.json").write_text(
                report.model_dump_json(indent=1) + "\n", encoding="utf-8"
            )


# ---- F10 and B10 ------------------------------------------------------------------------------


def cmd_freeze_check(args: argparse.Namespace) -> None:
    """F10's preconditions: clean frozen paths, HEAD as part A names it, B files as chosen."""
    freeze.check_clean(args.porcelain.read_text(encoding="utf-8"))
    named = freeze.named_head(args.part_a.read_text(encoding="utf-8"))
    changed = args.changed.read_text(encoding="utf-8").split() if args.changed else []
    freeze.check_head(args.head, named, changed)
    chosen = freeze.read_hash_file(args.chosen_b_code)
    freeze.check_b_files(chosen, freeze.b_code_hashes(), "the chosen tuning round")
    print(f"freeze preconditions hold at {args.head[:10]} (part A names {named[:10]})")


def cmd_freeze_write(args: argparse.Namespace) -> None:
    """Write E10.commit, E10.sha256 over `--files`, and B_FILES.sha256; print the file count."""
    names = args.files.read_text(encoding="utf-8").splitlines()
    print(freeze.write_e10(args.prereg, args.head, [Path(n) for n in names if n.strip()]))
    freeze.write_b_files_hash(args.prereg)


def cmd_prereg_b(args: argparse.Namespace) -> None:
    """Write PREREG_B.md from the stage outputs, then PREREG.sha256 over everything registered."""
    p1b = json.loads((args.root / "state" / "p1b.json").read_text(encoding="utf-8"))
    rounds = [_round(d) for d in _round_dirs(args.root) if (d / "round.json").is_file()]
    verdicts = _lines(args.root / "val" / "replay_verdicts.txt")
    probe = args.root / "val" / "pool_probe.json"
    peak = (
        json.loads(probe.read_text("utf-8"))["peak_rss_bytes"] / 2**30 if probe.is_file() else None
    )
    costs_file = args.root / "state" / "measured_costs.json"
    costs = json.loads(costs_file.read_text("utf-8")) if costs_file.is_file() else {}
    projection_file = args.root / "state" / "p1c_projection.json"  # P1b's end writes it (F1)
    sealed_caps = (
        json.loads(projection_file.read_text("utf-8"))["run_caps_usd"]
        if projection_file.is_file()
        else {}
    )
    part = prereg_b.PartB(
        code_commit=args.head,
        gates=[gates.GateResult.model_validate(g) for g in p1b["gates"]],
        b_sealed=p1b["b_sealed"],
        a2_cells={p: {f: tuple(c) for f, c in cells.items()} for p, cells in p1b["a2"].items()},
        b_cells={p: {f: tuple(c) for f, c in cells.items()} for p, cells in p1b["b"].items()},
        rounds=rounds,
        chosen_round=prereg_b.choose_round(rounds).number,
        replay_verdicts=verdicts,
        cost_per_question_usd=costs,
        sealed_caps_usd=sealed_caps,
        val1000_pool_peak_gib=peak,
        e10_files=len((args.prereg / "E10.sha256").read_text("utf-8").splitlines()),
        e10_sha256_file_sha256=freeze.sha256_of(args.prereg / "E10.sha256"),
    )
    with (args.prereg / "PREREG_B.md").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(prereg_b.render_part_b(part))
    count = freeze.write_prereg_sha(args.prereg, args.extra)
    print(f"wrote PREREG_B.md; PREREG.sha256 lists {count} files")


def _lines(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    rows = (line.split(" ", 1) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {name: verdict for name, verdict in rows}


_D10_FILES = (
    "corpora/*/ingest.json", "corpora/*/rules.json", "corpora/*/operating_positions.json",
    "corpora/*/corpus_b.json", "questions/*/questions.jsonl", "questions/*/splits.json",
    "questions/*/scope_report.json", "questions/*/position_baselines.jsonl",
)  # fmt: skip


def cmd_d10_write(args: argparse.Namespace) -> None:
    """Write D10.sha256 once: E10.commit and every drawn plant and question file."""
    files = [args.prereg / "E10.commit"]
    for pattern in _D10_FILES:
        files += sorted(args.root.glob(pattern))
    print(freeze.write_hash_file(args.root / "D10.sha256", files))


def cmd_b_code_write(args: argparse.Namespace) -> None:
    """Write `b_code.sha256` into a B run's folder (R15)."""
    freeze.write_b_code_sha256(args.run_dir / "b_code.sha256")


def cmd_b_code_check(args: argparse.Namespace) -> None:
    """The B files a run recorded equal the frozen `B_FILES.sha256`.

    Raises:
        FreezeRefused: they differ.
    """
    recorded = freeze.read_hash_file(args.run_dir / "b_code.sha256")
    freeze.check_b_files(freeze.read_hash_file(args.against), recorded, f"run {args.run_dir.name}")


def cmd_b_files_check(args: argparse.Namespace) -> None:
    """The B files now equal a tuning round's or a run's recorded hashes.

    Raises:
        FreezeRefused: they differ.
    """
    chosen = freeze.read_hash_file(args.against)
    freeze.check_b_files(chosen, freeze.b_code_hashes(), args.against.parent.name)


def _scale_of(corpus_id: str) -> str:
    return "1000" if "1000g" in corpus_id else "100"


def cmd_audit_b_select(args: argparse.Namespace) -> None:
    """Pick the B stratum (half the main sample, VALVE_SET and POSITION rows) and its sheet."""
    main_rows = len(json.loads(args.main_plan.read_text(encoding="utf-8"))["items"])
    rows: dict[tuple[str, str], QuestionResult] = {}
    questions: dict[str, Question] = {}
    plants: dict[str, str] = {}
    for run_dir in args.run:
        run = RunDir(run_dir)
        corpus = RunConfig.model_validate_json(run.config_path.read_text("utf-8")).corpora[0]
        plants[corpus] = corpus
        loaded, _lines = read_questions(args.questions_root / corpus / "questions.jsonl")
        questions.update({q.question_id: q for q in loaded})
        rows.update({(r.run_id, r.question_id): r for r in run.read_rows()})
    picked = audit_b.select_stratum(audit_b.candidate_rows(rows.values(), questions), main_rows)
    items = [_audit_item(rows[(p.run_id, p.question_id)], questions, p) for p in picked]
    args.out.write_text(
        json.dumps({"items": [i.model_dump(mode="json") for i in items]}, indent=1) + "\n", "utf-8"
    )
    sheet = []
    for corpus in sorted(plants):
        plant = load_corpus_artifacts(corpus, args.corpora_root / corpus / "ingest.json").gold.plant
        mine = [p for p in picked if questions[p.question_id].corpus_id == corpus]
        if plant is not None and mine:
            by_id = {q: r for (_run, q), r in rows.items()}
            sheet.append(audit_b.resolution_sheet(PlantIndex(plant), mine, by_id, questions))
    args.sheet.write_text("\n\n".join(sheet) + "\n", encoding="utf-8")
    print(f"B stratum: {len(items)} rows (main sample {main_rows})")


def _audit_item(
    row: QuestionResult, questions: Mapping[str, Question], pick: StratumRow
) -> AuditItem:
    question = questions[row.question_id]
    source = SourceRow(
        run_id=row.run_id, strategy=row.strategy, question_id=row.question_id,
        corpus_id=question.corpus_id, family=question.family, scale=_scale_of(question.corpus_id),
        outcome=row.outcome, scorer_correct=row.correct, answer_key=pick.answer_key,
    )  # fmt: skip
    return AuditItem(stratum="right_extra" if row.correct else "wrong", row=source)
