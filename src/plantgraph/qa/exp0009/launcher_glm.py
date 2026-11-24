"""The launcher's commands for stage P1g, the GLM comparison arm (design §20).

Same contract as `launcher_commands.py`: print what the shell needs, raise on failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plantgraph.qa.exp0009 import glm_arm, glm_report
from plantgraph.qa.exp0009.cascade_report import ArmReport
from plantgraph.qa.exp0009.glm_report import SystemRuns
from plantgraph.qa.exp0009.launcher_commands import read_plan
from plantgraph.qa.exp0009.plan import PlantSpec22
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.questions.per_family import read_questions

QUESTIONS_FILE = "questions.jsonl"


def cmd_glm_questions(args: argparse.Namespace) -> None:
    """Write the arm's question files: each plant's A2 file without its scope X questions."""
    for spec in glm_arm.glm_plants(read_plan(args.prereg)):
        a2_dir = args.root / "questions" / spec.plant_id
        out_dir = args.root / glm_arm.FOLDER / "questions" / spec.plant_id
        count = glm_arm.write_glm_questions(a2_dir, out_dir)
        print(f"{spec.plant_id}: {count} scope R questions")


def cmd_glm_estimate(args: argparse.Namespace) -> None:
    """Print the estimate NOTE of P1g, from the question files the arm will run."""
    loads = []
    for spec in glm_arm.glm_plants(read_plan(args.prereg)):
        path = args.root / glm_arm.FOLDER / "questions" / spec.plant_id / QUESTIONS_FILE
        count = len(path.read_text(encoding="utf-8").splitlines())
        loads.append(glm_arm.PlantLoad(spec.plant_id, spec.scale, count))
    balance = "not read" if args.balance_usd is None else f"${args.balance_usd:.2f}"
    print(glm_arm.render_estimate(args.root, loads, balance))


def cmd_glm_room(args: argparse.Namespace) -> None:
    """Print the dollars P1g may still spend; raise if the runs ledger cannot cover them."""
    print(glm_arm.money_needed_usd(args.root, args.root / glm_arm.FOLDER))


def _system(name: str, report_path: Path, run_dirs: dict[str, Path]) -> SystemRuns:
    report = ArmReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    rows = {tier: RunDir(path).read_rows() for tier, path in run_dirs.items()}
    return SystemRuns(name=name, correct_ids=frozenset(report.correct_ids), rows_by_tier=rows)


def _compare_plant(root: Path, spec: PlantSpec22) -> glm_report.PlantComparison:
    plant, runs = spec.plant_id, glm_arm.FOLDER
    questions, _lines = read_questions(root / runs / "questions" / plant / QUESTIONS_FILE)
    luna_runs = {t: root / "p1c" / "runs" / f"S9-{t.upper()}-{plant}" for t in glm_report.TIERS}
    glm_runs = {t: root / runs / "runs" / glm_arm.run_id(t, plant) for t in glm_report.TIERS}
    luna = _system("Luna", root / "reports" / f"{plant}_a2.json", luna_runs)
    glm = _system("GLM", root / "reports" / "glm" / f"{plant}_glm.json", glm_runs)
    ids = [q.question_id for q in questions]
    return glm_report.compare_plant(plant, spec.scale, ids, luna, glm)


def cmd_glm_report(args: argparse.Namespace) -> None:
    """Write `reports/glm_comparison.md` and `.json`: GLM against Luna on the arm's questions."""
    plants = glm_arm.glm_plants(read_plan(args.prereg))
    comparisons = [_compare_plant(args.root, spec) for spec in plants]
    out = args.root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    text = glm_report.render_markdown(comparisons)
    (out / "glm_comparison.md").write_text(text, encoding="utf-8")
    document = json.dumps([c.model_dump(mode="json") for c in comparisons], indent=1)
    (out / "glm_comparison.json").write_text(document + "\n", encoding="utf-8")
    print(text)
