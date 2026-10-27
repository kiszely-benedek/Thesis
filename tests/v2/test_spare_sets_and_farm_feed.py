"""The spare-set gold field, and the `p_shared_farm_feed` knob that v2.0 does not implement."""

from __future__ import annotations

import json

import pytest
from plant_invariants import plant_view
from pydantic import ValidationError

from plantgraph.benchmark.v2.config import FlowsheetKnobs, GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.patterns.assembly import spare_set_plan
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, GenerationRecordV2
from plantgraph.benchmark.v2.vocabulary import SpareNaming

# ---- spare sets ----------------------------------------------------------------------------------


def _machines(count: int) -> list[EquipmentSpec]:
    return [
        EquipmentSpec(node_id=f"p{i}", node_class="CentrifugalPump", unit_no=1, tag=f"P-10{i}")
        for i in range(count)
    ]


def test_two_or_more_machines_are_a_spare_set_and_one_machine_is_not() -> None:
    assert spare_set_plan(_machines(3), "pump").spare_sets == (("p0", "p1", "p2"),)
    assert spare_set_plan(_machines(2), "pump").spare_sets == (("p0", "p1"),)
    assert spare_set_plan(_machines(1), "pump").spare_sets == ()


def test_the_plan_keeps_its_equipment_and_roles_as_before() -> None:
    plan = spare_set_plan(_machines(2), "transfer_pump")
    assert [e.node_id for e in plan.equipment] == ["p0", "p1"]
    assert plan.roles == {"p0": "transfer_pump", "p1": "transfer_pump"}


def test_the_spare_sets_stay_out_of_the_plan_dump_so_the_plan_digest_means_what_is_drawn() -> None:
    assert "spare_sets" not in spare_set_plan(_machines(2), "pump").model_dump()


def test_the_record_lists_every_set_with_its_unit_role_and_members() -> None:
    view = plant_view(1, 20)
    record = view.generated.record
    assert record.spare_sets
    nodes = set(view.graph.nodes)
    for spare in record.spare_sets:
        assert len(spare.node_ids) >= 2 and set(spare.node_ids) <= nodes
        assert {view.roles[n] for n in spare.node_ids} == {spare.role}
    members = [n for spare in record.spare_sets for n in spare.node_ids]
    assert len(members) == len(set(members))  # a machine belongs to at most one set


def test_the_record_names_sets_whose_tags_give_no_hint_under_consecutive_naming() -> None:
    """The reason for the field: consecutive naming (`P-1203`, `P-1204`) hides a set in the tag."""
    views = [plant_view(seed, 20) for seed in (1, 2, 3)]
    conventions = {
        t.train_no: t.conventions.spare_naming for v in views for t in v.generated.plan.trains
    }
    assert SpareNaming.CONSECUTIVE in conventions.values()  # some train draws it in these seeds
    for view in views:
        by_train = {t.train_no: t.conventions.spare_naming for t in view.generated.plan.trains}
        unit_train = {u.slot.unit_no: u.slot.train_no for u in view.generated.plan.units}
        for spare in view.generated.record.spare_sets:
            if by_train[unit_train[spare.unit_no]] is SpareNaming.CONSECUTIVE:
                tags = [view.graph.nodes[n]["tag"] for n in spare.node_ids]
                assert not any(tag[-1].isalpha() for tag in tags), tags  # no A/B in the tag


def test_the_record_with_spare_sets_survives_json_and_is_deterministic() -> None:
    config = GeneratorConfigV2(seed=4, n_units=12)
    first = generate_plant_v2(config).record
    again = generate_plant_v2(config).record
    assert first.model_dump_json() == again.model_dump_json()
    restored = GenerationRecordV2.model_validate(json.loads(first.model_dump_json()))
    assert restored.spare_sets == first.spare_sets and first.spare_sets


# ---- p_shared_farm_feed --------------------------------------------------------------------------


def test_the_farm_feed_probability_defaults_to_zero() -> None:
    assert FlowsheetKnobs().p_shared_farm_feed == 0.0
    assert GeneratorConfigV2(n_units=1).flowsheet.p_shared_farm_feed == 0.0


@pytest.mark.parametrize("value", [0.05, 0.2, 1.0])
def test_any_other_farm_feed_probability_is_refused(value: float) -> None:
    with pytest.raises(ValidationError, match="not implemented in v2.0"):
        FlowsheetKnobs(p_shared_farm_feed=value)


def test_a_config_read_back_from_json_with_the_old_default_is_refused_too() -> None:
    stored = GeneratorConfigV2(n_units=1).model_dump(mode="json")
    stored["flowsheet"]["p_shared_farm_feed"] = 0.2
    with pytest.raises(ValidationError, match="not implemented in v2.0"):
        GeneratorConfigV2.model_validate(stored)
