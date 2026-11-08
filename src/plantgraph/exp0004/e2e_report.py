"""Command line of the E2E report (reads files only; no network, no database).

python -m plantgraph.exp0004.e2e_report [--e2e-root DIR] [--r5-root DIR] [--out DIR]
    [--plant R5_CORPUS:V_CORPUS ...] [--headline-n N]

Each `--plant` is one plant: its R5 corpus and its tag-variant (V) corpus. With several plants the
claims use the two-stage cluster bootstrap. The default is the first measurement's single plant.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.exp0004.e2e_report_load import (
    PREREGISTERED_HEADLINE_N,
    ArmInput,
    headline_ids,
    load_arm,
)
from plantgraph.exp0004.e2e_report_models import R5_ARM, RESOLVER_ARMS, ArmData, v_arm
from plantgraph.exp0004.e2e_report_render import render_markdown
from plantgraph.exp0004.e2e_report_tables import PlantArms, build_pooled_e2e_report
from plantgraph.qa.cascade.limits import SETTINGS
from plantgraph.qa.cascade.policy import load_policy

POLICY_PATH = Path("src/plantgraph/qa/cascade/policies_v2t/cascade_v4_iso.json")
#: The first measurement's plant; EXP-0008 passes its own ids with `--plant`.
R5_CORPUS = "H1000g2"
V_CORPUS = "H1000g2V"
#: Setting A of the V2T-A freeze: cutoff 120 s.
SETTING = "A"


def _r5_input(r5_root: Path, r5_corpus: str) -> ArmInput:
    return ArmInput(
        label=R5_ARM,
        corpus_id=r5_corpus,
        cypher_run=r5_root / "runs" / f"S7-CYP-{r5_corpus}",
        agent_run=r5_root / "runs" / f"S7-AG-{r5_corpus}",
        questions_root=r5_root / "questions",
        corpora_root=r5_root / "corpora",
    )


def _v_input(e2e_root: Path, v_corpus: str, resolver: str) -> ArmInput:
    arm_root = e2e_root / resolver
    return ArmInput(
        label=v_arm(resolver),
        corpus_id=v_corpus,
        cypher_run=arm_root / "live" / "runs" / f"E2E-CYP-{v_corpus}-{resolver}",
        agent_run=arm_root / "live" / "runs" / f"E2E-AG-{v_corpus}-{resolver}",
        questions_root=arm_root / "questions",
        corpora_root=arm_root / "live" / "corpora",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004.e2e_report", description=__doc__)
    parser.add_argument("--e2e-root", type=Path, default=Path("data/runs/exp0004/e2e"))
    parser.add_argument("--r5-root", type=Path, default=Path("data/runs/exp0007/sealed"))
    parser.add_argument("--out", type=Path, default=None, help="default: <e2e-root>/report")
    parser.add_argument(
        "--plant",
        action="append",
        default=[],
        metavar="R5_CORPUS:V_CORPUS",
        help=f"one plant, repeat for several (default {R5_CORPUS}:{V_CORPUS})",
    )
    parser.add_argument(
        "--headline-n",
        type=int,
        default=PREREGISTERED_HEADLINE_N,
        help="headline questions per plant that every arm must hold",
    )
    return parser


def _parse_plants(values: list[str]) -> list[tuple[str, str]]:
    """`H1000g21p1:H1000g21p1V` pairs as (R5 corpus, V corpus); the default is one plant."""
    if not values:
        return [(R5_CORPUS, V_CORPUS)]
    plants = []
    for value in values:
        r5_corpus, separator, v_corpus = value.partition(":")
        if not (separator and r5_corpus and v_corpus):
            raise SystemExit(f"error: expected --plant R5_CORPUS:V_CORPUS, found {value!r}")
        plants.append((r5_corpus, v_corpus))
    return plants


def _load_plant(
    args: argparse.Namespace, r5_corpus: str, v_corpus: str, cutoff_s: float
) -> PlantArms:
    """Load the four arms of one plant; the V arms use R5's headline ids (they carry no splits)."""
    policy = load_policy(POLICY_PATH)
    r5 = _r5_input(args.r5_root, r5_corpus)
    questions, ids = headline_ids(r5.questions_root, r5.corpus_id, args.headline_n)
    inputs = [r5, *(_v_input(args.e2e_root, v_corpus, r) for r in RESOLVER_ARMS)]
    arms: dict[str, ArmData] = {}
    for arm_input in inputs:
        print(f"loading {arm_input.corpus_id} {arm_input.label} ...", flush=True)  # slow graphs
        arms[arm_input.label] = load_arm(arm_input, policy, cutoff_s, ids, args.headline_n)
    return PlantArms(r5_corpus, arms, questions)


def main(argv: list[str] | None = None) -> None:
    """Load the arms of every plant, build the report and write `report.md` and `report.json`."""
    args = _parser().parse_args(argv)
    out: Path = args.out or args.e2e_root / "report"
    cutoff_s = SETTINGS[SETTING].cutoff_s
    plants = [_load_plant(args, r5, v, cutoff_s) for r5, v in _parse_plants(args.plant)]
    report = build_pooled_e2e_report(plants, load_policy(POLICY_PATH).name, cutoff_s)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"wrote {out / 'report.md'} and {out / 'report.json'}")


if __name__ == "__main__":
    main()
