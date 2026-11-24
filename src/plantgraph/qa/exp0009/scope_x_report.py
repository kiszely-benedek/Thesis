"""The scope X report of one v2.2 plant: candidates, refusals, their causes, discriminating share.

Per family it counts the candidates, the refused ones split by reason, the kept ones, and the kept
ones whose gold holds an untagged valve. For OPEN_VALVES it also gives the **discriminating share**:
the kept questions whose gold differs from the topological one, which is what separates them from
their registered twin. Refusals are traced to the **role** of the valves behind them (a role says
why a valve is on the drawing: "pump discharge block", "tank inlet block"), each valve counted once
per refused candidate (design `v2t-b-system-revision.md` §10 R3).

ADR-0067's stop rule is checked here: a family that refuses more than a quarter of its candidates
on a dev plant returns to the architect. This is a measurement: it builds the held-out families on
a dev plant to count them, and writes no question file.

    uv run python -m plantgraph.qa.exp0009.scope_x_report --seed 1 --sheets 100 \
        --tagging untagged --out report.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.qa.exp0009.dev_plants import forced_config
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x import FamilyOutcome, RefusalReason, scope_x_candidates

#: ADR-0067: more refused than this share of a family's candidates stops the work
QUARTER = 0.25
#: the candidate-pool seed of EXP-0008's sealed recipe, as `availability_table.POOL_SEED`
POOL_SEED = 31
_TAGGING = {"untagged": True, "tagged": False, "drawn": None}


class FamilyReport(BaseModel):
    """One family on one plant, in the numbers the design asks for."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    candidates: int
    refused_no_descriptor: int
    refused_empty_gold: int
    kept: int
    kept_with_untagged_gold: int
    #: OPEN_VALVES only: kept questions whose gold differs from the topological gold
    kept_discriminating: int | None
    #: role -> number of valves of that role behind a refused candidate
    refusing_roles: dict[str, int]

    @property
    def refused(self) -> int:
        """Refused candidates, whatever the reason."""
        return self.refused_no_descriptor + self.refused_empty_gold

    @property
    def refused_share(self) -> float:
        """Refused over candidates; 0.0 when there were none."""
        return self.refused / self.candidates if self.candidates else 0.0

    @property
    def discriminating_share(self) -> float | None:
        """Discriminating over kept; `None` for a family that has no such question."""
        if self.kept_discriminating is None or not self.kept:
            return None
        return self.kept_discriminating / self.kept


class PlantReport(BaseModel):
    """The scope X report of one plant, with the quarter rule checked."""

    model_config = ConfigDict(frozen=True)

    plant_id: str
    seed: int
    sheets_target: int
    sheets: int
    tagging: str
    seconds: dict[str, float]
    families: list[FamilyReport]

    @property
    def over_quarter(self) -> list[QuestionFamily]:
        """The families that refuse more than `QUARTER` of their candidates (the stop rule)."""
        return [r.family for r in self.families if r.refused_share > QUARTER]


def family_report(outcome: FamilyOutcome, roles: Mapping[str, str]) -> FamilyReport:
    """Count one family's outcome; `roles` maps a valve's node id to its generator role."""
    reasons = Counter(refusal.reason for refusal in outcome.refusals)
    role_counts = Counter(
        roles.get(valve_id, "<no role>")
        for refusal in outcome.refusals
        for valve_id in refusal.valve_ids
    )
    flags = outcome.flags.values()
    discriminating = [
        f.differs_from_topological for f in flags if f.differs_from_topological is not None
    ]
    return FamilyReport(
        family=outcome.family,
        candidates=outcome.candidates,
        refused_no_descriptor=reasons[RefusalReason.NO_UNIQUE_DESCRIPTOR],
        refused_empty_gold=reasons[RefusalReason.EMPTY_GOLD],
        kept=len(outcome.kept),
        kept_with_untagged_gold=sum(f.holds_untagged for f in flags),
        kept_discriminating=sum(discriminating) if discriminating else None,
        refusing_roles=dict(sorted(role_counts.items(), key=lambda pair: (-pair[1], pair[0]))),
    )


def _roles_of(plans: tuple[TrimPlan, ...]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for plan in plans:
        roles.update(plan.roles)
    return roles


def report_as_json(report: PlantReport) -> str:
    """The report as JSON, with the derived shares written next to the stored counts."""
    rows = [
        {
            **row.model_dump(mode="json"),
            "refused": row.refused,
            "refused_share": round(row.refused_share, 4),
            "discriminating_share": row.discriminating_share,
        }
        for row in report.families
    ]
    document = {
        **report.model_dump(mode="json"),
        "families": rows,
        "over_quarter": [family.value for family in report.over_quarter],
    }
    return json.dumps(document, indent=1) + "\n"


def plant_report(
    *, seed: int, sheets_target: int, tagging: str
) -> tuple[PlantReport, dict[QuestionFamily, FamilyOutcome]]:
    """Generate one forced-tagging plant and build every scope X family on it, timing each step."""
    seconds: dict[str, float] = {}
    started = time.perf_counter()
    generated = generate_plant_v2(forced_config(sheets_target, seed, untagged=_TAGGING[tagging]))
    plant, _conversion = generated.graph()
    seconds["generate"] = time.perf_counter() - started

    started = time.perf_counter()
    sheets, manifest = split(plant, HeadlinePresetV22().split_config(seed))
    seconds["split"] = time.perf_counter() - started

    plant_id = f"D{sheets_target}g22s{seed}"
    started = time.perf_counter()
    positions = positions_of(generated.plan.unit_plans)
    outcomes = scope_x_candidates(
        plant, manifest, sheets, positions, corpus_id=plant_id, seed=POOL_SEED
    )
    seconds["scope_x"] = time.perf_counter() - started

    roles = _roles_of(generated.plan.unit_plans)
    report = PlantReport(
        plant_id=plant_id,
        seed=seed,
        sheets_target=sheets_target,
        sheets=len(sheets),
        tagging=tagging,
        seconds={name: round(value, 1) for name, value in seconds.items()},
        families=[family_report(outcome, roles) for outcome in outcomes.values()],
    )
    return report, outcomes


def main(argv: list[str] | None = None) -> None:
    """Build one plant, write its scope X report as JSON and print the stop-rule verdict."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.scope_x_report")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--sheets", required=True, type=int)
    parser.add_argument("--tagging", required=True, choices=sorted(_TAGGING))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report, _outcomes = plant_report(
        seed=args.seed, sheets_target=args.sheets, tagging=args.tagging
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_as_json(report), encoding="utf-8")
    over = [family.value for family in report.over_quarter]
    print(f"{report.plant_id} ({args.tagging}): families over a quarter refused: {over}")


if __name__ == "__main__":
    main()
