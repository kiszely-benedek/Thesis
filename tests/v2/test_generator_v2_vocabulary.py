"""Tests for the v2 code tables, item kinds and per-train conventions (`vocabulary.py`)."""

from __future__ import annotations

import random

import pytest

from plantgraph.benchmark.v2 import tags
from plantgraph.benchmark.v2.vocabulary import (
    ISA_FIRST_LETTERS,
    ItemKind,
    OnOffLetter,
    SpareNaming,
    TrainConventions,
    draw_train_conventions,
    is_isa_letters,
    item_kind,
    numbers_used,
    spare_members,
)
from plantgraph.graph.schema import CLASS_SPECS
from plantgraph.graph.schema_classes import NodeCategory


@pytest.mark.parametrize(
    ("node_class", "letters", "expected"),
    [
        ("CentrifugalPump", "P", ItemKind.EQUIPMENT),
        ("PressureVessel", "R", ItemKind.EQUIPMENT),
        ("PressureVessel", "D", ItemKind.EQUIPMENT),
        ("GateValve", "GTV", ItemKind.MANUAL_VALVE),
        ("BallValve", "BV", ItemKind.MANUAL_VALVE),
        ("BallValve", "XV", ItemKind.ON_OFF_VALVE),
        ("BallValve", "YV", ItemKind.ON_OFF_VALVE),
        ("GlobeValve", "FV", ItemKind.CONTROL_VALVE),
        ("GlobeValve", "GV", ItemKind.MANUAL_VALVE),
        ("AngleValve", "LV", ItemKind.CONTROL_VALVE),
        ("SwingCheckValve", "CHV", ItemKind.CHECK_VALVE),
        ("SpringLoadedGlobeSafetyValve", "PSV", ItemKind.SAFETY_DEVICE),
        ("FlowMeasuringElement", "FE", ItemKind.PRIMARY_ELEMENT),
        ("SteamTrap", "ST", ItemKind.FITTING),
        ("PipeFlangeSpade", "SB", ItemKind.FITTING),
        ("ProcessSignalGeneratingFunction", "ST", ItemKind.TRANSMITTER),
        ("ProcessSignalGeneratingFunction", "PDT", ItemKind.TRANSMITTER),
        ("ProcessSignalGeneratingFunction", "PI", ItemKind.LOCAL_INDICATOR),
        ("ProcessSignalGeneratingFunction", "ZSO", ItemKind.POSITION_SWITCH),
        ("ProcessInstrumentationFunction", "HS", ItemKind.HAND_SWITCH),
        ("ProcessInstrumentationFunction", "LIC", ItemKind.CONTROLLER),
        ("ProcessControlFunction", "FFIC", ItemKind.CONTROLLER),
        ("ProcessInstrumentationFunction", "LAH", ItemKind.ALARM),
        ("ProcessInstrumentationFunction", "LSHH", ItemKind.SWITCH),
        ("ProcessInstrumentationFunction", "FQI", ItemKind.INDICATOR),
    ],
)
def test_item_kind_from_class_and_letters(
    node_class: str, letters: str, expected: ItemKind
) -> None:
    assert item_kind(node_class, letters) is expected


@pytest.mark.parametrize(
    ("node_class", "letters"),
    [
        ("NoSuchClass", "P"),
        ("PipeTee", "X"),  # untagged
        ("ActuatingFunction", "FV"),  # untagged
        ("FlowInPipeOffPageConnector", "X"),
        ("CentrifugalPump", "K"),
        ("GateValve", "FV"),  # a gate valve is never a control valve
        ("ProcessInstrumentationFunction", "GV"),  # not ISA
        ("ProcessSignalGeneratingFunction", "FIC"),  # a sensor does not end in C
    ],
)
def test_item_kind_rejects_what_does_not_fit(node_class: str, letters: str) -> None:
    with pytest.raises(ValueError):
        item_kind(node_class, letters)


def test_every_tagged_class_has_a_kind_for_its_own_prefix() -> None:
    for name, spec in CLASS_SPECS.items():
        prefix = spec.tag_prefix
        if prefix is None or spec.category is NodeCategory.INSTRUMENTATION:
            continue
        assert isinstance(item_kind(name.value, prefix), ItemKind), name


def test_fifteen_isa_first_letters() -> None:
    assert len(ISA_FIRST_LETTERS) == 15
    assert all(is_isa_letters(f"{letter}I") for letter in ISA_FIRST_LETTERS)
    assert not is_isa_letters("GI")


def test_on_off_letters_follow_the_train_convention() -> None:
    x_train = TrainConventions(on_off_letter=OnOffLetter.X, spare_naming=SpareNaming.SUFFIX)
    y_train = TrainConventions(on_off_letter=OnOffLetter.Y, spare_naming=SpareNaming.SUFFIX)
    assert (x_train.on_off_valve_letters, x_train.on_off_solenoid_letters) == ("XV", "XY")
    assert (y_train.on_off_valve_letters, y_train.on_off_solenoid_letters) == ("YV", "YY")
    assert item_kind("BallValve", y_train.on_off_valve_letters) is ItemKind.ON_OFF_VALVE


def test_draw_is_deterministic_and_reaches_every_variant() -> None:
    first = [draw_train_conventions(random.Random(seed)) for seed in range(40)]
    assert first == [draw_train_conventions(random.Random(seed)) for seed in range(40)]
    assert {c.on_off_letter for c in first} == set(OnOffLetter)
    assert {c.spare_naming for c in first} == set(SpareNaming)


def test_suffix_spares_share_one_number() -> None:
    members = spare_members(SpareNaming.SUFFIX, 3)
    assert [(m.sequence_offset, m.train) for m in members] == [(0, "A"), (0, "B"), (0, "C")]
    assert numbers_used(SpareNaming.SUFFIX, 3) == 1


def test_consecutive_spares_take_consecutive_numbers() -> None:
    members = spare_members(SpareNaming.CONSECUTIVE, 3)
    assert [(m.sequence_offset, m.train) for m in members] == [(0, None), (1, None), (2, None)]
    assert numbers_used(SpareNaming.CONSECUTIVE, 3) == 3


@pytest.mark.parametrize("naming", list(SpareNaming))
def test_single_machine_has_a_plain_number(naming: SpareNaming) -> None:
    assert [(m.sequence_offset, m.train) for m in spare_members(naming, 1)] == [(0, None)]


def test_spare_count_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="1 to 3"):
        spare_members(SpareNaming.SUFFIX, 4)


@pytest.mark.parametrize("naming", list(SpareNaming))
def test_spare_tags_are_distinct_across_consecutive_sets(naming: SpareNaming) -> None:
    rng = random.Random(3)
    rendered: list[str] = []
    next_sequence = 1
    for _ in range(25):
        count = rng.randint(1, 3)
        for member in spare_members(naming, count):
            sequence = next_sequence + member.sequence_offset
            rendered.append(tags.format_equipment_tag("P", 12, sequence, member.train))
        next_sequence += numbers_used(naming, count)
    assert len(set(rendered)) == len(rendered)


def test_consecutive_spares_overflow_raises() -> None:
    members = spare_members(SpareNaming.CONSECUTIVE, 3)
    with pytest.raises(ValueError, match="expected a sequence"):
        tags.format_equipment_tag("P", 12, 98 + members[2].sequence_offset)
