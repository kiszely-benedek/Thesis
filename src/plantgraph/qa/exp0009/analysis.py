"""The EXP-0009 sealed analysis (T17): every pre-registered claim from the saved sealed runs.

    uv run python -m plantgraph.qa.exp0009.analysis --root data/runs/exp0009

END calls it with `--root` alone. It reads result files only (questions, `p1c/runs/`, `state/`,
`corpora/*/rules.json`, END's re-scores); it calls no model and opens no database. The one
heavy step is the same as in `cascade-report`: each plant's graph is rebuilt from its
`ingest.json`, because the cascade routes a question by its "need label", which is read off the
tags the question names. It writes `reports/analysis.json` and `reports/analysis.md` under the
root. If `state/b_sealed` says `no`, every B claim is reported as NOT_RUN, as PREREG A says.

The pass rules and the bootstrap are fixed in `analysis_claims.py`; this module only sequences.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from plantgraph.qa.exp0009 import analysis_claims as claims
from plantgraph.qa.exp0009 import analysis_misc as misc
from plantgraph.qa.exp0009 import analysis_x as x
from plantgraph.qa.exp0009.analysis_effect import data_effect_rows, load_v21
from plantgraph.qa.exp0009.analysis_load import (
    FinderFactory,
    PlantData,
    corpus_finder,
    load_plant,
    read_b_sealed,
)
from plantgraph.qa.exp0009.analysis_models import (
    AnalysisReport,
    ClaimRow,
    ClaimStatus,
    PlantRecord,
    Table,
)
from plantgraph.qa.exp0009.analysis_render import render_markdown
from plantgraph.qa.exp0009.launcher_commands import read_plan

SCOPE_NOTE = (
    "Scope R is EXP-0008's headline set on the v2.2 plants with the five X families left out "
    "(the three headline splits, LOOP_ACTUATED_VALVE out). Scope X is the five extension "
    "families: B answers all of them, A2 only the isolation families. acc@C counts an answer "
    "correct when it arrived within setting A's 120 s cutoff. The plants of a scale are pooled "
    "with equal weight."
)
_B, _DIFF = "V2T-B", "V2T-B minus V2T-A2"
#: (claim, arm, scope, pass rule) of each B claim, for the NOT_RUN rows
B_CLAIMS = (
    ("Q4-B", _B, claims.SCOPE_R_X, claims.RULE_NO_LOSS),
    ("Q4-B sensitivity", _B, claims.SCOPE_R_X_NO_POSITION, claims.RULE_NO_LOSS),
    ("SB1", _DIFF, claims.SCOPE_R, claims.RULE_DESCRIPTIVE),
    ("SB2", _DIFF, claims.SCOPE_X_ISOLATION, claims.RULE_ABOVE_ZERO),
)


def not_run_row(claim: str, arm: str, scope: str, rule: str, reason: str) -> ClaimRow:
    """A claim that could not be computed, with the reason in its detail."""
    return ClaimRow(
        claim=claim, arm=arm, scope=scope, rule=rule, status=ClaimStatus.NOT_RUN, detail=reason
    )


def b_claim_rows(plants: Sequence[PlantData], *, b_sealed: bool) -> list[ClaimRow]:
    """Q4-B, its sensitivity row, SB1 and SB2; NOT_RUN rows when B was not run sealed."""
    if not b_sealed:
        reason = "B was not run sealed: G1-B or G1-B2 failed in P1b (state/b_sealed = no)"
        return [not_run_row(*spec, reason) for spec in B_CLAIMS]
    return [
        claims.b_scale_claim(plants, with_position=True),
        claims.b_scale_claim(plants, with_position=False),
        *claims.sb_claim_rows(plants),
    ]


def plant_record(plant: PlantData) -> PlantRecord:
    """The plant, its run folders and question counts, as the report's run table lists them."""
    return PlantRecord(
        plant_id=plant.spec.plant_id, scale=plant.spec.scale, sheets=plant.spec.predicted_sheets,
        a2_runs=list(plant.a2.run_ids), b_runs=list(plant.b.run_ids) if plant.b else [],
        n_a2_questions=len(plant.a2_questions), n_b_questions=len(plant.b_questions),
    )  # fmt: skip


def effect_rows(
    plants: Sequence[PlantData], exp0008_root: Path, finder_for: FinderFactory
) -> list[ClaimRow]:
    """The data effect against EXP-0008, or a NOT_RUN row when its root is not there."""
    if not exp0008_root.is_dir():
        reason = f"no EXP-0008 root at {exp0008_root}"
        return [
            not_run_row(
                "Data effect", "V2T-A2, v2.2 minus v2.1", "shared families", "descriptive", reason
            )
        ]
    return data_effect_rows(plants, load_v21(exp0008_root, finder_for))


def descriptive_tables(
    root: Path, plants: Sequence[PlantData], *, b_sealed: bool
) -> tuple[list[Table], list[str]]:
    """The descriptive list of PREREG A, and a note for every optional input that was missing."""
    ids = [p.spec.plant_id for p in plants]
    reports = {p.spec.plant_id: x.read_scope_report(root, p) for p in plants}
    baselines = {p.spec.plant_id: x.read_baselines(root, p) for p in plants}
    flags = {p.spec.plant_id: x.read_flags(root, p) for p in plants}
    rules = {p.spec.plant_id: misc.read_rules(root, p) for p in plants}
    rescored = {
        corpus: misc.read_rescore(root, corpus)
        for p in plants
        for corpus in (p.spec.plant_id, p.spec.b_id)
    }
    questions = x.x_questions(plants, flags)
    tables = [
        x.refused_table(reports, plants), x.subscope_table(questions), x.family_table(questions),
        x.position_table(plants, baselines), x.named_by_table(plants, baselines),
        misc.network_table(plants), misc.rules_table(rules, plants),
        misc.prf_table(rescored, plants, b_sealed=b_sealed),
    ]  # fmt: skip
    notes = [
        f"no qpool flags for {i}: its X questions are in no sub-scope"
        for i in ids
        if flags[i] is None
    ]
    notes += [f"no rules.json for {i}" for i in ids if rules[i] is None]
    notes += [
        f"no re-score at {misc.rescore_path(root, c).name}: END's re-score of {c} is missing"
        for c, report in rescored.items()
        if report is None and (b_sealed or not c.endswith("B"))
    ]
    return tables, notes


def build_report(
    root: Path, exp0008_root: Path, finder_for: FinderFactory, v21_finder_for: FinderFactory
) -> AnalysisReport:
    """Load the sealed plants and compute every claim and table.

    Raises:
        ValueError / FileNotFoundError: an input that must exist is missing or inconsistent.
    """
    plan = read_plan(root / "prereg")
    b_sealed = read_b_sealed(root)
    plants = [load_plant(root, plan.plant(i), b_sealed, finder_for) for i in plan.sealed_ids()]
    a2_report = claims.a2_sealed_report(plants)
    rows = [*claims.a2_claim_rows(a2_report, plants), *b_claim_rows(plants, b_sealed=b_sealed)]
    rows += effect_rows(plants, exp0008_root, v21_finder_for)
    tables, notes = descriptive_tables(root, plants, b_sealed=b_sealed)
    return AnalysisReport(
        root=str(root), b_sealed=b_sealed, scope_note=SCOPE_NOTE,
        plants=[plant_record(p) for p in plants], claims=rows,
        exp0008_verdicts=claims.exp0008_verdict_lines(a2_report), tables=tables,
        notes=[*notes, *a2_report.notes],
    )  # fmt: skip


def write_reports(report: AnalysisReport, out_dir: Path) -> tuple[Path, Path]:
    """Write `analysis.json` and `analysis.md`; return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "analysis.json", out_dir / "analysis.md"
    json_path.write_text(report.model_dump_json(indent=1) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the analysis; print a failure as `ERROR: ...` and return 1."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.analysis")
    parser.add_argument("--root", type=Path, default=Path("data/runs/exp0009"))
    parser.add_argument("--exp0008-root", type=Path, default=None)
    args = parser.parse_args(argv)
    exp0008 = args.exp0008_root or args.root.parent / "exp0008"
    try:
        report = build_report(
            args.root,
            exp0008,
            corpus_finder(args.root / "corpora"),
            corpus_finder(exp0008 / "corpora"),
        )
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    json_path, md_path = write_reports(report, args.root / "reports")
    for claim in report.claims:
        print(f"{claim.claim}: {claim.status.value}")
    print(f"wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
