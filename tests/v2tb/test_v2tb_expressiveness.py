"""§10.6 (9), amended by §10.8: the gold's names for untagged valves are readable from the B view.

On the forced-untagged seed 1 plant, a canonical program that reads only `NetworkxGraphViewB`
reproduces the canonical descriptor of every untagged valve in the dev X isolation references, and
resolves every descriptor-form POSITION question to exactly its valve and reads its position.
The bar is 100 %: a miss means the gold names something B cannot read.
"""

from __future__ import annotations

from functools import cache

from plants_b import real_corpus
from seed1_b import seed1

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x import SCOPE_X_DEV_FAMILIES, scope_x_candidates
from plantgraph.qa.v2tb.expressiveness_b import ExpressivenessReport, check_expressiveness
from plantgraph.qa.v2tb.store_b import positions_by_local_key
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB


@cache
def _seed1_report() -> ExpressivenessReport:
    plant = seed1()
    return check_expressiveness(
        plant=plant.corpus.plant,
        view=plant.view,
        occurrence_map=plant.corpus.occurrence_map,
        outcomes=plant.outcomes,
        roles=plant.roles,
    )


def test_every_untagged_gold_descriptor_is_reproduced_from_the_view() -> None:
    report = _seed1_report()

    assert report.n_untagged_gold_valves > 100  # the references really hold untagged valves
    assert report.n_descriptors_reproduced == report.n_untagged_gold_valves
    assert [m for m in report.misses if m.check == "descriptor"] == []


def test_every_descriptor_form_position_question_resolves_to_its_valve_and_is_read() -> None:
    report = _seed1_report()
    position = seed1().outcomes[QuestionFamily.POSITION_OF_VALVE]

    assert report.n_position_questions == 1375  # 1,380 kept, 5 named by tag (design §10.8 table)
    assert len(position.kept) == 1380
    assert report.n_resolved_exactly == report.n_position_questions
    assert report.n_position_read == report.n_position_questions
    assert report.misses == [] and report.misses_by_role == {}


def test_the_check_fails_when_the_view_lacks_the_positions() -> None:
    """The same check on a view built without the map: every position read is a miss, by role."""
    corpus = real_corpus()
    config = GeneratorConfigV22(seed=1, n_units=8)
    generated = generate_plant_v2(config)
    planned = dict(positions_of(generated.plan.unit_plans))
    roles = {n: r for plan in generated.plan.unit_plans for n, r in plan.roles.items()}
    outcomes = scope_x_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, planned,
        corpus_id="SMALL", seed=31, families=SCOPE_X_DEV_FAMILIES,
    )  # fmt: skip

    def report(positions: dict[str, str]) -> ExpressivenessReport:
        view = NetworkxGraphViewB("SMALL", corpus.localized_sheets, corpus.resolution, positions)
        return check_expressiveness(
            plant=corpus.plant,
            view=view,
            occurrence_map=corpus.occurrence_map,
            outcomes=outcomes,
            roles=roles,
        )

    with_positions = report(positions_by_local_key(planned, corpus.occurrence_map))
    without = report({})

    assert with_positions.misses == [] and with_positions.n_position_questions > 0
    assert without.n_position_read == 0
    assert len(without.misses) == without.n_position_questions
    assert set(without.misses_by_role) <= set(roles.values())
