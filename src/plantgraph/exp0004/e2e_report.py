"""Command line of the E2E report (reads files only; no network, no database).

python -m plantgraph.exp0004.e2e_report [--e2e-root DIR] [--r5-root DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.exp0004.e2e_report_load import ArmInput, headline_ids, load_arm
from plantgraph.exp0004.e2e_report_models import R5_ARM, RESOLVER_ARMS, ArmData, v_arm
from plantgraph.exp0004.e2e_report_render import render_markdown
from plantgraph.exp0004.e2e_report_tables import build_e2e_report
from plantgraph.qa.cascade.limits import SETTINGS
from plantgraph.qa.cascade.policy import load_policy

POLICY_PATH = Path("src/plantgraph/qa/cascade/policies_v2t/cascade_v4_iso.json")
R5_CORPUS = "H1000g2"
V_CORPUS = "H1000g2V"
#: Setting A of the V2T-A freeze: cutoff 120 s.
SETTING = "A"


def _r5_input(r5_root: Path) -> ArmInput:
    return ArmInput(
        label=R5_ARM,
        corpus_id=R5_CORPUS,
        cypher_run=r5_root / "runs" / f"S7-CYP-{R5_CORPUS}",
        agent_run=r5_root / "runs" / f"S7-AG-{R5_CORPUS}",
        questions_root=r5_root / "questions",
        corpora_root=r5_root / "corpora",
    )


def _v_input(e2e_root: Path, resolver: str) -> ArmInput:
    arm_root = e2e_root / resolver
    return ArmInput(
        label=v_arm(resolver),
        corpus_id=V_CORPUS,
        cypher_run=arm_root / "live" / "runs" / f"E2E-CYP-{V_CORPUS}-{resolver}",
        agent_run=arm_root / "live" / "runs" / f"E2E-AG-{V_CORPUS}-{resolver}",
        questions_root=arm_root / "questions",
        corpora_root=arm_root / "live" / "corpora",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004.e2e_report", description=__doc__)
    parser.add_argument("--e2e-root", type=Path, default=Path("data/runs/exp0004/e2e"))
    parser.add_argument("--r5-root", type=Path, default=Path("data/runs/exp0007/sealed"))
    parser.add_argument("--out", type=Path, default=None, help="default: <e2e-root>/report")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Load the four arms, build the report and write `report.md` and `report.json`."""
    args = _parser().parse_args(argv)
    out: Path = args.out or args.e2e_root / "report"
    policy = load_policy(POLICY_PATH)
    cutoff_s = SETTINGS[SETTING].cutoff_s
    r5 = _r5_input(args.r5_root)
    questions, ids = headline_ids(r5.questions_root, r5.corpus_id)
    # the variant arms carry no splits.json: R5's headline ids apply to them (same question ids)
    inputs = [r5, *(_v_input(args.e2e_root, r) for r in RESOLVER_ARMS)]
    arms: dict[str, ArmData] = {}
    for arm_input in inputs:
        print(f"loading {arm_input.label} ...", flush=True)  # the corpus graphs load slowly
        arms[arm_input.label] = load_arm(arm_input, policy, cutoff_s, ids)
    report = build_e2e_report(arms, questions, policy.name, cutoff_s)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"wrote {out / 'report.md'} and {out / 'report.json'}")


if __name__ == "__main__":
    main()
