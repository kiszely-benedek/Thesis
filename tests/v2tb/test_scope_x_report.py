"""The scope X report: counts, refusing roles, the discriminating share and the quarter rule."""

from __future__ import annotations

import json

from scope_x_toy import POSITIONS, toy_manifest, toy_plant, toy_sheets

from plantgraph.qa.exp0009.scope_x_report import (
    FamilyReport,
    PlantReport,
    family_report,
    report_as_json,
)
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x import scope_x_candidates

F = QuestionFamily
_ROLES = {"gc": "pump_discharge_block", "gd": "tank_inlet_block"}


def _reports() -> dict[QuestionFamily, FamilyReport]:
    plant = toy_plant()
    outcomes = scope_x_candidates(
        plant, toy_manifest(), toy_sheets(plant), POSITIONS, corpus_id="TOY", seed=1
    )
    return {family: family_report(outcome, _ROLES) for family, outcome in outcomes.items()}


def test_the_open_valves_report_counts_refusals_by_reason_and_the_discriminating_share() -> None:
    report = _reports()[F.OPEN_VALVES_TO_ISOLATE]

    assert (report.candidates, report.refused_no_descriptor, report.refused_empty_gold) == (4, 1, 1)
    assert report.kept == 2
    assert (report.kept_discriminating, report.discriminating_share) == (1, 0.5)
    assert report.refused_share == 0.5


def test_refusing_roles_count_each_valve_once_per_refused_candidate() -> None:
    reports = _reports()

    assert reports[F.UPSTREAM_ISOLATION_X].refusing_roles == {"tank_inlet_block": 1}
    assert reports[F.DOWNSTREAM_ISOLATION_X].refusing_roles == {"pump_discharge_block": 1}


def test_a_family_without_open_valves_gold_has_no_discriminating_share() -> None:
    assert _reports()[F.UPSTREAM_ISOLATION_X].discriminating_share is None


def test_the_quarter_rule_lists_the_families_that_refuse_more_than_a_quarter() -> None:
    reports = list(_reports().values())
    plant = PlantReport(
        plant_id="T",
        seed=1,
        sheets_target=1,
        sheets=1,
        tagging="untagged",
        seconds={},
        families=reports,
    )

    # the OPEN families lose 2 of 4 (an empty gold and a series pair), POSITION 2 of 6 (the
    # series pair); 1 of 4 is not above a quarter
    assert plant.over_quarter == [
        F.OPEN_VALVES_TO_ISOLATE,
        F.POSITION_OF_VALVE,
        F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM,
    ]


def test_the_json_carries_the_derived_shares() -> None:
    plant = PlantReport(
        plant_id="T",
        seed=1,
        sheets_target=1,
        sheets=1,
        tagging="untagged",
        seconds={},
        families=list(_reports().values()),
    )
    document = json.loads(report_as_json(plant))

    assert document["families"][0]["refused_share"] == 0.5
    assert "over_quarter" in document


def test_the_position_report_counts_the_two_forms_and_their_position_mix() -> None:
    report = _reports()[F.POSITION_OF_VALVE]

    assert (report.candidates, report.refused_no_descriptor, report.kept) == (6, 2, 4)
    assert (report.kept_named_by_descriptor, report.kept_named_by_tag) == (1, 3)
    assert report.kept_position_mix == {"descriptor": {"NO": 1}, "tag": {"NC": 2, "NO": 1}}


def test_a_family_without_forms_has_no_form_counts() -> None:
    report = _reports()[F.UPSTREAM_ISOLATION_X]

    assert report.kept_named_by_descriptor is None and report.kept_named_by_tag is None
    assert report.kept_position_mix == {}
