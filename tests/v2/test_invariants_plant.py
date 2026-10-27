"""Structural invariants S1-S12, S19 and S21-S24 on whole v2 plants of seeds 1-5 (design 12.2).

Each test names its rule. The checks are in `plant_invariants.py` (S1-S3, S5, S6, S10-S12),
`plant_invariants_naming.py` (S21, S23, S24), `instrument_invariants.py` (S4, S7, S8, S9, S22)
and `machine_checks.py` (S19). Two invariants live elsewhere: S17 (the v1 goldens) in
`tests/test_v1_goldens.py` and S18 in `tests/test_schema_vocabulary.py`; S13-S16 and S20 are in
`test_invariants_corpus.py`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from instrument_invariants import check_s4, check_s7, check_s8, check_s9, check_s22
from machine_checks import check_s19
from plant_invariants import (
    PlantView,
    check_s1,
    check_s2,
    check_s3,
    check_s5,
    check_s6,
    check_s10,
    check_s11,
    check_s12,
    plant_view,
)
from plant_invariants_naming import check_s21, check_s23, check_s24

from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
SHEETS = 30  # about 30 sheets per plant: every pattern turns up in some seed


def _units(seed: int) -> int:
    return smallest_n_units_v2(SHEETS, HeadlinePresetV2(), seed).n_units


@pytest.fixture(scope="module", params=SEEDS, ids=[f"seed{s}" for s in SEEDS])
def view(request: pytest.FixtureRequest) -> PlantView:
    return plant_view(request.param, _units(request.param))


def _solenoids(view: PlantView) -> dict[str, str | None]:
    """On-off valve id -> the sub-tag of its solenoid, read from the DEXPI model."""
    systems = view.model.conceptualModel.actuatingSystems  # type: ignore[union-attr]
    return {
        s.operatedValveReference.valve.id: (
            s.controlledActuator.subTagName if s.controlledActuator else None
        )
        for s in systems
    }


def test_s1_a_centrifugal_pump_draws_through_a_block_valve_then_a_strainer(view: PlantView) -> None:
    assert check_s1(view) > 0


def test_s2_every_discharge_has_gauge_tap_then_check_valve_then_block_valve(
    view: PlantView,
) -> None:
    assert check_s2(view) > 0


def test_s3_every_positive_displacement_pump_has_a_relief_to_its_suction(view: PlantView) -> None:
    check_s3(view)  # a seed may draw no PD pump at 30 sheets: the all-seeds test counts them


def test_s4_every_actuator_drives_a_valve_with_its_loops_number(view: PlantView) -> None:
    assert check_s4(view.graph) > 0


def test_s5_every_control_valve_station_is_two_blocks_and_a_bypass(view: PlantView) -> None:
    assert check_s5(view) > 0


def test_s6_every_pressure_vessel_reaches_a_safety_valve_but_the_drain_pot(view: PlantView) -> None:
    assert check_s6(view) > 0


def test_s7_every_on_off_valve_has_a_driver_and_a_solenoid(view: PlantView) -> None:
    assert check_s7(view.graph, _solenoids(view)) > 0


def test_s8_every_loop_has_one_sensor_one_bubble_and_one_number(view: PlantView) -> None:
    assert check_s8(view.graph) > 0


def test_s9_every_tag_is_unique_parses_and_fits_its_class(view: PlantView) -> None:
    assert check_s9(view.graph) > 0


def test_s10_line_numbers_parse_are_unique_and_change_at_every_spec_break(view: PlantView) -> None:
    assert check_s10(view) > 0


def test_s11_spare_set_members_are_alike_and_parallel(view: PlantView) -> None:
    assert check_s11(view) > 0


def test_s12_gas_does_not_meet_liquid_and_no_pump_feeds_its_own_suction(view: PlantView) -> None:
    check_s12(view)


def test_s19_control_into_equipment_comes_from_an_actuating_electrical_function(
    view: PlantView,
) -> None:
    assert check_s19(view.graph) > 0


def test_s21_every_motor_driven_machine_has_one_motor_with_its_number(view: PlantView) -> None:
    assert check_s21(view) > 0


def test_s22_a_cascade_slave_has_one_sensor_and_one_master(view: PlantView) -> None:
    check_s22(view.graph)


def test_s23_on_off_letter_and_spare_naming_are_constant_within_a_train(view: PlantView) -> None:
    check_s23(view)


def test_s24_only_the_77_classes_no_custom_classes_and_two_parents(view: PlantView) -> None:
    assert check_s24(view) > 50


# ---- the five plants together --------------------------------------------------------------------


def test_across_the_five_seeds_every_rule_found_something_to_check() -> None:
    """No check is vacuous: pumps of both kinds, spare sets, a station and a drain pot all occur."""
    views = [plant_view(seed, _units(seed)) for seed in SEEDS]
    assert sum(check_s3(v) for v in views) > 0  # positive-displacement pumps
    assert sum(check_s12(v) for v in views) > 0  # wired phases and pump loops
    assert sum(check_s23(v) for v in views) > 0  # spare sets with a train naming
    assert sum(check_s22(v.graph) for v in views) > 0  # cascades
    drain_pots = [n for v in views for n, r in v.roles.items() if r == "condensate_drain_pot"]
    assert drain_pots, "no seed drew a condensate drain pot: the S6 exemption is untested"


def test_the_trains_draw_both_conventions_somewhere_in_the_five_seeds() -> None:
    conventions = {
        (t.conventions.on_off_letter, t.conventions.spare_naming)
        for seed in SEEDS
        for t in plant_view(seed, _units(seed)).generated.plan.trains
    }
    assert len({c[0] for c in conventions}) == 2 and len({c[1] for c in conventions}) == 2


def test_the_plants_have_about_30_sheets() -> None:
    sheets = [plant_view(seed, _units(seed)).generated.plan.sheet_count for seed in SEEDS]
    assert all(SHEETS <= count < SHEETS + 8 for count in sheets), sheets


# ---- the checks can fail -------------------------------------------------------------------------


def test_s6_fails_on_a_plant_whose_safety_valves_were_removed() -> None:
    view = plant_view(1, _units(1))
    graph = view.graph.copy()
    graph.remove_nodes_from(
        [n for n, d in graph.nodes(data=True) if "SafetyValve" in d["node_class"]]
    )
    with pytest.raises(AssertionError, match="no safety valve"):
        check_s6(replace(view, graph=graph))


def test_s1_fails_when_the_strainers_are_gone() -> None:
    view = plant_view(1, _units(1))
    roles = {n: r for n, r in view.roles.items() if r != "suction_strainer"}
    with pytest.raises(AssertionError, match="no block valve followed by a strainer"):
        check_s1(replace(view, roles=roles))


def test_s11_fails_when_a_spare_set_member_is_fed_from_elsewhere() -> None:
    view = plant_view(1, _units(1))
    graph = view.graph.copy()
    (first, second, *_), *_ = [r.node_ids for r in view.generated.record.spare_sets]
    graph.add_edge(first, second, relation="send_to", line_number="x", fluid_code="P")
    with pytest.raises(AssertionError, match="not parallel|classes"):
        check_s11(replace(view, graph=graph))
