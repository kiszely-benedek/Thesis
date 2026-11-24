"""The pool step: one process per plant draws the scope R pool and the scope X candidates (§19.6).

**Scope R** is EXP-0008's question recipe re-run on v2.2 plants. **Scope X** (extension) adds the
five families that only a system able to read valve positions and to name untagged valves can
answer (`qa/questions/scope_x.py`). Both come from one rebuilt corpus, so the plant is generated
once. This module only *pools* candidates; choosing which families survive and sampling ten per
family is `question_files.py`, because that choice needs the pools of every plant of a role.

Layout written under `qpool/<plant id>/`: `questions.jsonl` and `availability.json` (the R pool,
EXP-0008's writer), and `scope_x/` with the kept X questions per family, their flags, T15b's
family reports and the text-prior key of every POSITION question.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.exp0009.position_baselines import position_rows
from plantgraph.qa.exp0009.scope_x_report import FamilyReport, family_report
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.availability import BinTargets
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.questions.scope_x import (
    SCOPE_X_DEV_FAMILIES,
    SCOPE_X_FAMILIES,
    scope_x_candidates,
)
from plantgraph.qa.questions.scope_x_models import FamilyOutcome, NamedBy, QuestionFlags
from plantgraph.qa.questions.sealed_set import build_pool

X_FOLDER = "scope_x"
FLAGS_FILE, REPORT_FILE, KEYS_FILE = "flags.json", "report.json", "position_keys.json"
_F = QuestionFamily
#: Scope R families pre-registered unavailable at both scales (S5, §17.17, v2 exclusion).
R_UNAVAILABLE: frozenset[QuestionFamily] = frozenset(
    {
        _F.UPSTREAM_ISOLATION,
        _F.DOWNSTREAM_ISOLATION,
        _F.DOWNSTREAM_IN_UNIT,
        _F.UPSTREAM_SOURCES,
        _F.FIRST_MEETING_POINT,
    }
)


@dataclass(frozen=True)
class Recipe:
    """How a plant's questions are drawn: pool size, seeds, per-family count, X families."""

    name: str
    pool_seed: int
    n_per_bin: int
    n_unanswerable: int
    sample_seed: int
    n_per_family: int
    n_per_wording: int
    x_families: tuple[QuestionFamily, ...]


#: EXP-0008's sealed recipe (`lib_plants.sh sealed_questions`); all five X families
SEALED = Recipe("sealed", 31, 500, 100, 20261031, 10, 5, SCOPE_X_FAMILIES)
#: EXP-0008's dev recipe (`dev_questions`); held-out X families are never built on these plants
DEV = Recipe("dev", 1, 97, 97, 20261101, 10, 0, SCOPE_X_DEV_FAMILIES)
RECIPES = {SEALED.name: SEALED, DEV.name: DEV}


@dataclass(frozen=True)
class PlantPool:
    """Everything the pool step finds on one plant."""

    r_pool: list[Question]
    #: the kept X questions per family
    x_kept: dict[QuestionFamily, list[Question]]
    flags: dict[str, QuestionFlags]
    reports: list[FamilyReport]
    #: POSITION question id -> its text-prior key (so later steps need no plant)
    position_keys: dict[str, tuple[str, ...]]


def pool_step(artifacts: CorpusArtifacts, recipe: Recipe) -> PlantPool:
    """Pool scope R and scope X candidates on one rebuilt corpus.

    Raises:
        ValueError: the corpus has no ground truth.
    """
    gold = artifacts.gold
    if gold.plant is None or gold.manifest is None:
        raise ValueError(f"expected a ground-truth plant for {artifacts.corpus_id}, found none")
    targets = BinTargets(per_bin=recipe.n_per_bin, unanswerable=recipe.n_unanswerable)
    r_pool, _availability = build_pool(artifacts, targets, recipe.pool_seed)
    plan = plan_plant(artifacts.generator_config)  # type: ignore[arg-type]
    positions = positions_of(plan.unit_plans)  # same as the generator's own (tested), no pyDEXPI
    outcomes = scope_x_candidates(
        gold.plant, gold.manifest, gold.sheets, positions,
        corpus_id=artifacts.corpus_id, seed=recipe.pool_seed, families=recipe.x_families,
    )  # fmt: skip
    roles = {k: v for trim in plan.unit_plans for k, v in trim.roles.items()}
    return PlantPool(
        r_pool=r_pool,
        x_kept={family: outcome.kept for family, outcome in outcomes.items()},
        flags={qid: f for outcome in outcomes.values() for qid, f in outcome.flags.items()},
        reports=[family_report(outcome, roles) for outcome in outcomes.values()],
        position_keys=_position_keys(artifacts, outcomes, positions),
    )


def _position_keys(
    artifacts: CorpusArtifacts,
    outcomes: dict[QuestionFamily, FamilyOutcome],
    positions: Mapping[str, OperatingPosition],
) -> dict[str, tuple[str, ...]]:
    """The key of each kept POSITION question: walk the valves in the builder's order."""
    outcome = outcomes.get(QuestionFamily.POSITION_OF_VALVE)
    plant = artifacts.gold.plant
    if outcome is None or plant is None:
        return {}
    refused = {valve for refusal in outcome.refusals for valve in refusal.valve_ids}
    nodes = [n for n in sorted(positions) if n not in refused]  # the builder walks sorted ids
    if len(nodes) != len(outcome.kept):
        raise ValueError(f"expected {len(outcome.kept)} POSITION valves, found {len(nodes)}")
    keys: dict[str, tuple[str, ...]] = {}
    for question, node in zip(outcome.kept, nodes, strict=True):
        form = outcome.flags[question.question_id].named_by
        if form is None:
            raise ValueError(f"expected a named_by flag on {question.question_id}, found none")
        keys[question.question_id] = _key_of(plant, node, positions[node], form)
    return keys


def _key_of(
    plant: nx.DiGraph[str], node: str, code: OperatingPosition, form: NamedBy
) -> tuple[str, ...]:
    rows = position_rows(plant, {node: code}, form)
    if len(rows) != 1:
        raise ValueError(f"expected one baseline row for valve {node}, found {len(rows)}")
    return rows[0].key


def write_pool(out_dir: Path, pool: PlantPool) -> None:
    """Write the R pool and the `scope_x/` files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = "".join(q.model_dump_json() + "\n" for q in pool.r_pool)
    (out_dir / "questions.jsonl").write_bytes(lines.encode("utf-8"))
    x_dir = out_dir / X_FOLDER
    x_dir.mkdir(exist_ok=True)
    for family, kept in pool.x_kept.items():
        text = "".join(q.model_dump_json() + "\n" for q in kept)
        (x_dir / f"{family.value}.jsonl").write_bytes(text.encode("utf-8"))
    flags = {qid: f.model_dump(mode="json") for qid, f in pool.flags.items()}
    reports = [r.model_dump(mode="json") for r in pool.reports]
    keys = {qid: list(key) for qid, key in pool.position_keys.items()}
    for name, document in ((FLAGS_FILE, flags), (REPORT_FILE, reports), (KEYS_FILE, keys)):
        (x_dir / name).write_text(
            json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )


def read_pool(pool_dir: Path) -> PlantPool:
    """The pool back from disk."""
    r_pool, _lines = read_questions(pool_dir / "questions.jsonl")
    x_dir = pool_dir / X_FOLDER
    x_kept: dict[QuestionFamily, list[Question]] = {}
    for path in sorted(x_dir.glob("*.jsonl")):
        x_kept[QuestionFamily(path.stem)] = read_questions(path)[0]

    def load(name: str) -> Any:
        return json.loads((x_dir / name).read_text(encoding="utf-8"))

    return PlantPool(
        r_pool=r_pool,
        x_kept=x_kept,
        flags={qid: QuestionFlags.model_validate(f) for qid, f in load(FLAGS_FILE).items()},
        reports=[FamilyReport.model_validate(r) for r in load(REPORT_FILE)],
        position_keys={qid: tuple(key) for qid, key in load(KEYS_FILE).items()},
    )


def run_pool_step(corpora_root: Path, qpool_root: Path, plant_id: str, recipe: Recipe) -> PlantPool:
    """The command behind `questions-pool`: rebuild the A corpus, pool, write `qpool/<id>/`."""
    artifacts = load_corpus_artifacts(plant_id, corpora_root / plant_id / "ingest.json")
    pool = pool_step(artifacts, recipe)
    write_pool(qpool_root / plant_id, pool)
    return pool
