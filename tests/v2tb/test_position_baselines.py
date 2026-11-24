"""The POSITION baselines: fitting, falling back to the majority, scoring, a reproducible file."""

from __future__ import annotations

import json

import pytest
from scope_x_toy import POSITIONS, toy_plant

from plantgraph.qa.exp0009.position_baselines import (
    PositionRow,
    fit_on_all,
    fit_on_first_score_on_rest,
    fit_prior,
    fluid_field,
    leave_one_seed_out,
    position_rows,
    priors_as_json,
    score,
    sha256_of,
)
from plantgraph.qa.questions.scope_x_models import NamedBy


def _row(key: str, position: str) -> PositionRow:
    return PositionRow(key=(key,), position=position)


_TRAIN = [
    _row("vent", "NC"),
    _row("vent", "NC"),
    _row("vent", "NO"),
    _row("block", "NO"),
    _row("block", "NO"),
]


def test_the_prior_is_the_commonest_code_per_key_and_the_majority_the_commonest_overall() -> None:
    prior = fit_prior(NamedBy.TAG, _TRAIN)

    assert prior.table == {("vent",): "NC", ("block",): "NO"}
    assert prior.majority == "NO"  # three NO against two NC


def test_a_tie_goes_to_the_code_met_first() -> None:
    prior = fit_prior(NamedBy.TAG, [_row("a", "NO"), _row("a", "NC")])

    assert prior.table == {("a",): "NO"}
    assert prior.majority == "NO"


def test_an_unseen_key_falls_back_to_the_majority() -> None:
    prior = fit_prior(NamedBy.TAG, _TRAIN)

    assert prior.predict(("never seen",)) == prior.majority


def test_score_counts_hits_for_both_baselines_and_the_unseen_keys() -> None:
    prior = fit_prior(NamedBy.TAG, _TRAIN)
    accuracy = score(prior, [_row("vent", "NC"), _row("block", "NC"), _row("new", "NO")])

    assert (accuracy.rows, accuracy.prior_hits, accuracy.majority_hits) == (3, 2, 1)
    assert accuracy.unseen_keys == 1
    assert accuracy.prior == pytest.approx(2 / 3)


def test_fitting_on_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="expected rows"):
        fit_prior(NamedBy.TAG, [])


def test_fit_on_the_first_seed_scores_the_others_and_leave_one_out_scores_each() -> None:
    by_seed = {1: _TRAIN, 2: [_row("vent", "NC")], 3: [_row("block", "NO")]}

    assert set(fit_on_first_score_on_rest(by_seed, NamedBy.TAG)) == {2, 3}
    assert set(leave_one_seed_out(by_seed, NamedBy.TAG)) == {1, 2, 3}
    assert leave_one_seed_out(by_seed, NamedBy.TAG)[2].prior_hits == 1


def test_the_file_is_the_same_bytes_for_the_same_fit_and_its_hash_follows() -> None:
    first = priors_as_json({NamedBy.TAG: fit_on_all({1: _TRAIN}, NamedBy.TAG)})
    again = priors_as_json({NamedBy.TAG: fit_on_all({1: list(reversed(_TRAIN))}, NamedBy.TAG)})

    assert first == again
    assert sha256_of(first) == sha256_of(again)
    assert json.loads(first)["tag"]["table"][0] == {"key": ["block"], "position": "NO"}


def test_rows_of_the_tag_form_come_from_tagged_valves_and_descriptor_rows_from_untagged_ones() -> (
    None
):
    plant = toy_plant()

    tag_rows = position_rows(plant, POSITIONS, NamedBy.TAG)
    descriptor_rows = position_rows(plant, POSITIONS, NamedBy.DESCRIPTOR)

    assert sorted(r.key for r in tag_rows) == [("HV", "GateValve")] * 3
    # ga is the only untagged valve with a descriptor (gc and gd have none)
    assert descriptor_rows == [
        PositionRow(key=("GateValve", "upstream", "Tank", "P"), position="NO")
    ]


def test_the_fluid_field_is_the_second_dash_field_of_the_line_number() -> None:
    assert fluid_field('6"-P-1203-A1A') == "P"
    with pytest.raises(ValueError, match="expected a line number"):
        fluid_field("nodash")
