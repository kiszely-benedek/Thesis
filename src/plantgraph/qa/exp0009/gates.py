"""The free gates and the validation gates of EXP-0009 P1 (design §19.5, §19.7).

A **gate** is a check that must pass before the next step may start. Each function here takes
plain data and returns a `GateResult`, so a test can feed it a good input and a spoiled one.
The functions that need a built plant (`g0c_validation`, `g0b_checks`) are thin: they rebuild
what the gate reads, then hand it to the pure rule.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.rules import owed
from plantgraph.benchmark.v2.rules.registry import RuleReport
from plantgraph.benchmark.v2.validation_v22 import validate_plant_graph_v22
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.ingest.size_search_networked import sheet_band_of
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0007.freeze_checks import ingest_problems
from plantgraph.qa.exp0009.line_view_gate import run_line_view_gate
from plantgraph.qa.exp0009.plan import PlantSpec22
from plantgraph.qa.exp0009.scope_x_report import QUARTER, FamilyReport
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME, read_positions_file
from plantgraph.qa.v2tb.shown_b import item_line_misses
from plantgraph.qa.v2tb.store_b import (
    check_g0b,
    positions_by_local_key,
    valve_ids_of,
    with_positions,
)
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB

MIN_KEPT = 10  # G0e: a family needs this many kept candidates on every sealed plant
WEAK_SHARE = 0.5  # G1: a family below this accuracy is weak
B2_MARGIN = -0.05  # G1-B2: B may fall at most 5 points behind A2 on scope R

#: family -> (correct, total), one dict per plant id
FamilyCells = Mapping[str, Mapping[str, tuple[int, int]]]


class GateResult(BaseModel):
    """The outcome of one gate: its name, whether it passed, and the numbers behind it."""

    model_config = ConfigDict(frozen=True)

    gate: str
    passed: bool
    detail: str


def _result(gate: str, problems: list[str]) -> GateResult:
    return GateResult(gate=gate, passed=not problems, detail="; ".join(problems) or "ok")


# ---- at build ---------------------------------------------------------------------------------


def g0c_rules(rules_json: Path) -> GateResult:
    """`OWED_FIXES` is empty and `rules.json` holds no violation of any wired rule."""
    problems = [f"owed fix {rule}: {task}" for rule, task in owed.OWED_FIXES.items()]
    report = RuleReport.model_validate_json(rules_json.read_text(encoding="utf-8"))
    problems += [
        f"rule {row.rule_id}: {row.violations} violation(s)"
        for row in report.rows
        if row.violations
    ]
    digest = hashlib.sha256(rules_json.read_bytes()).hexdigest()
    return GateResult(gate="G0c-rules", passed=not problems, detail="; ".join(problems) or digest)


def g0c_validation(spec: PlantSpec22) -> GateResult:
    """The frozen schema validator, less the tags untagged documents leave off, finds nothing."""
    generated = generate_plant_v2(spec.generator_config())
    plant, _conversion = generated.graph()
    violations = validate_plant_graph_v22(plant, generated.record)  # type: ignore[arg-type]
    problems = [f"{len(violations)} schema violation(s)"] if violations else []
    return _result("G0c-validation", problems)


def g0k(spec: PlantSpec22, ingest_json: Path, *, check_band: bool = True) -> GateResult:
    """The built plant's document flags equal the plan's, and its sheet total equals the prediction.

    Both are read back from the built corpus's own `ingest.json`: the flags from the generator
    config it recorded (replanned, so a flag the generator ignored would show), the total from its
    sheet count. The total must also lie in the scale's band.
    """
    record = json.loads(ingest_json.read_text(encoding="utf-8"))
    recorded = GeneratorConfigV22.model_validate(record["config"]["generator"])
    built_flags = tuple(d.manual_valves_untagged for d in plan_plant(recorded).documents)
    built_sheets = int(record["counts"]["n_sheets"])
    problems: list[str] = []
    if built_flags != spec.document_untagged:
        problems.append(
            f"built document flags {built_flags} differ from the plan's {spec.document_untagged}"
        )
    if built_sheets != spec.predicted_sheets:
        problems.append(f"built {built_sheets} sheets, plan predicted {spec.predicted_sheets}")
    band = sheet_band_of(spec.scale)
    if check_band and (band is None or not band[0] <= built_sheets <= band[1]):
        problems.append(f"{built_sheets} sheets lie outside the band {band}")
    return _result("G0k", problems)


def g0g(ingest_json: Path, corpus_id: str) -> GateResult:
    """Round trip and identity pair precision = recall = 1.0 (`exp0007 check-ingest`)."""
    return _result("G0g", ingest_problems(ingest_json, corpus_id))


def line_view(corpus_id: str, ingest_json: Path) -> GateResult:
    """LINE-01 for v2.2: the line view equals the gold's own walk, with no key collision."""
    result = run_line_view_gate(load_corpus_artifacts(corpus_id, ingest_json))
    detail = [] if result.passed else [f"collisions {result.key_collisions}, not P = R = 1"]
    return _result("line-view", detail)


def g0b_checks(b_id: str, b_dir: Path, spec: PlantSpec22) -> GateResult:
    """G0-B checks 2 and 3: the patched plan carries every position, and only valves are keyed."""
    artifacts = load_corpus_artifacts(b_id, b_dir / "ingest.json")
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(f"expected a ground-truth plant for {b_id}, found none")
    positions, _sha = read_positions_file(b_dir / POSITIONS_FILE_NAME)
    patched = with_positions(
        artifacts.load_plan, positions_by_local_key(positions, artifacts.gold.occurrence_map)
    )
    planned = dict(positions_of(plan_plant(spec.generator_config()).unit_plans))
    problems = check_g0b(
        file_positions=positions, planned_positions=planned,
        valve_ids=valve_ids_of(plant), patched_plan=patched,
    )  # fmt: skip
    return _result("G0-B", problems)


def r14f_exactness(b_id: str, b_dir: Path) -> GateResult:
    """R14f: every item line the B agent is shown is exact (the gold plant's own brackets)."""
    artifacts = load_corpus_artifacts(b_id, b_dir / "ingest.json")
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(f"expected a ground-truth plant for {b_id}, found none")
    positions, _sha = read_positions_file(b_dir / POSITIONS_FILE_NAME)
    by_key = positions_by_local_key(positions, artifacts.gold.occurrence_map)
    view = NetworkxGraphViewB(b_id, artifacts.localized_sheets, artifacts.resolution, by_key)
    graph = build_item_graph_b(view, line_view=True)
    misses = item_line_misses(graph, by_key, PlantIndex(plant), artifacts.gold.occurrence_map)
    return _result(
        "R14f", [f"{len(misses)} item line(s) differ, e.g. {misses[0]}"] if misses else []
    )


# ---- after the pool step ----------------------------------------------------------------------


def families_below_minimum(kept: Mapping[str, Counter[str]]) -> set[str]:
    """G0e: families with fewer than `MIN_KEPT` kept candidates on any sealed plant.

    `kept` maps a sealed plant id to its kept-candidate count per family value. A family that is
    absent on a plant has zero there.
    """
    families = {family for counts in kept.values() for family in counts}
    return {f for f in families if any(counts[f] < MIN_KEPT for counts in kept.values())}


def g0l(reports: Mapping[str, Iterable[FamilyReport]]) -> GateResult:
    """Per X family and plant, no more than a quarter of the candidates refused as non-unique."""
    problems = [
        f"{plant}: {report.family.value} refused {report.refused_share:.0%}"
        for plant, rows in reports.items()
        for report in rows
        if report.family in SCOPE_X_FAMILIES and report.refused_share > QUARTER
    ]
    return _result("G0l", problems)


# ---- validation: G1, G1-B, G1-B2 --------------------------------------------------------------


def _weak(cells: Mapping[str, tuple[int, int]], families: set[str]) -> set[str]:
    return {f for f in families if cells.get(f, (0, 0))[1] and _share(cells[f]) < WEAK_SHARE}


def _share(cell: tuple[int, int]) -> float:
    return cell[0] / cell[1] if cell[1] else 0.0


def _weak_everywhere(cells: FamilyCells, families: set[str]) -> list[str]:
    per_plant = [_weak(plant_cells, families) for plant_cells in cells.values()]
    return sorted(set.intersection(*per_plant)) if per_plant else []


def _x_names() -> set[str]:
    return {f.value for f in SCOPE_X_FAMILIES}


def g1(a2: FamilyCells) -> GateResult:
    """G1 (A2): no scope R family below 50 % on both validation plants."""
    r_families = {f for cells in a2.values() for f in cells} - _x_names()
    return _result(
        "G1", [f"{f} below 50% on every plant" for f in _weak_everywhere(a2, r_families)]
    )


def g1_b(b: FamilyCells) -> GateResult:
    """G1-B: no family of R or X below 50 % on both validation plants."""
    families = {f for cells in b.values() for f in cells}
    return _result("G1-B", [f"{f} below 50% on every plant" for f in _weak_everywhere(b, families)])


def r_accuracy(cells: Mapping[str, tuple[int, int]]) -> float:
    """Accuracy over the scope R families of one plant's cells (X families left out)."""
    r = [cell for family, cell in cells.items() if family not in _x_names()]
    total = sum(t for _c, t in r)
    return sum(c for c, _t in r) / total if total else 0.0


def g1_b2(a2: FamilyCells, b: FamilyCells) -> GateResult:
    """G1-B2: the mean over plants of B minus A2 on scope R is at least -0.05."""
    plants = sorted(set(a2) & set(b))
    if not plants:
        return _result("G1-B2", ["no plant has both arms"])
    mean = round(sum(r_accuracy(b[p]) - r_accuracy(a2[p]) for p in plants) / len(plants), 6)
    detail = [] if mean >= B2_MARGIN else [f"mean B - A2 on R is {mean:+.4f}, below {B2_MARGIN}"]
    return GateResult(
        gate="G1-B2", passed=not detail, detail="; ".join(detail) or f"mean {mean:+.4f}"
    )
