"""The forced-untagged 100-sheet seed 1 plant, built once for the T14c tests (not a test module).

About 20 s to build. It carries what the B tests need from one plant: the gold side (plant, plan,
positions as the plan and as DEXPI give them, roles), the B view, a patched load plan and the dev
scope X outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.ingest.pipeline import SyntheticCorpus
from plantgraph.qa.exp0009.dev_plants import dev_corpus, forced_config
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x import SCOPE_X_DEV_FAMILIES, scope_x_candidates
from plantgraph.qa.questions.scope_x_models import FamilyOutcome
from plantgraph.qa.v2tb.positions import read_operating_positions
from plantgraph.qa.v2tb.store_b import positions_by_local_key, with_positions
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

CORPUS_ID = "D100g22s1B"


@dataclass(frozen=True)
class Seed1:
    """One plant with every artifact a T14c test reads."""

    corpus: SyntheticCorpus
    planned: dict[str, str]
    from_dexpi: dict[str, str]
    roles: dict[str, str]
    by_local_key: dict[str, str]
    view: NetworkxGraphViewB
    plan: LoadPlan
    patched_plan: LoadPlan
    outcomes: dict[QuestionFamily, FamilyOutcome]


@cache
def seed1() -> Seed1:
    corpus = dev_corpus(100, 1, untagged=True)
    generated = generate_plant_v2(forced_config(100, 1, untagged=True))
    planned = dict(positions_of(generated.plan.unit_plans))
    roles: dict[str, str] = {}
    for plan in generated.plan.unit_plans:
        roles.update(plan.roles)
    by_local_key = positions_by_local_key(planned, corpus.occurrence_map)
    plan = build_load_plan(
        CORPUS_ID, corpus.localized_sheets, corpus.resolution, profile="plant_lines"
    )
    outcomes = scope_x_candidates(
        corpus.plant,
        corpus.manifest,
        corpus.sheets,
        planned,
        corpus_id="D100g22s1",
        seed=31,
        families=SCOPE_X_DEV_FAMILIES,
    )
    return Seed1(
        corpus=corpus,
        planned=planned,
        from_dexpi=read_operating_positions(generated.model),
        roles=roles,
        by_local_key=by_local_key,
        view=NetworkxGraphViewB(
            CORPUS_ID, corpus.localized_sheets, corpus.resolution, by_local_key
        ),
        plan=plan,
        patched_plan=with_positions(plan, by_local_key),
        outcomes=outcomes,
    )
