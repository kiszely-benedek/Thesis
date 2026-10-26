"""Tests for the v2 tag and line-number grammar (`benchmark/v2/tags.py`)."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from plantgraph.benchmark.v2 import tags
from plantgraph.benchmark.v2.vocabulary import (
    AMBIGUOUS_LETTERS,
    EQUIPMENT_TYPE_CODES,
    FITTING_CODES,
    LINE_INSULATIONS,
    LINE_SERVICES,
    LINE_SIZES,
    LINE_SPECS,
    SAFETY_CODES,
    SPARE_SUFFIXES,
    VALVE_CODES,
)
from plantgraph.qa.anchors import _TOKEN_RE  # the pattern a question uses to find a tag

_RANDOM_FIELDS = 10_000
_Formatter = Callable[[str, int, int], str]


def _random_unit_and_sequence(rng: random.Random, width: int) -> tuple[int, int]:
    return rng.randint(1, 120), rng.randint(1, 10**width - 1)


def test_examples_of_each_production() -> None:
    assert tags.format_equipment_tag("P", 12, 3, "A") == "P-1203A"
    assert tags.format_equipment_tag("TK", 12, 2) == "TK-1202"
    assert tags.format_instrument_tag("FIC", 12, 14) == "FIC-12014"
    assert tags.format_instrument_tag("XV", 12, 30) == "XV-12030"
    assert tags.format_valve_tag("GTV", 12, 107) == "GTV-12107"
    assert tags.format_safety_tag("PSV", 12, 12) == "PSV-12012"
    assert tags.format_fitting_tag("STR", 12, 41) == "STR-12041"
    assert tags.format_line_number(6, "P", 12, 17, "A1A", "N") == "6-P-120017-A1A-N"


@pytest.mark.parametrize("type_code", sorted(EQUIPMENT_TYPE_CODES))
@pytest.mark.parametrize("train", [None, *SPARE_SUFFIXES])
def test_equipment_round_trip(type_code: str, train: str | None) -> None:
    parsed = tags.parse_tag(tags.format_equipment_tag(type_code, 12, 3, train))
    assert parsed == tags.ParsedTag(
        kind="equipment",
        letters=type_code,
        first=type_code[0],
        functions=type_code[1:],
        unit=12,
        sequence=3,
        train=train,
    )


@pytest.mark.parametrize("letters", ["FIC", "PDT", "XV", "YY", "LSHH", "ZSO", "UC", "FQI", "LIAH"])
def test_instrument_round_trip(letters: str) -> None:
    parsed = tags.parse_tag(tags.format_instrument_tag(letters, 7, 999))
    assert parsed is not None
    assert (parsed.kind, parsed.letters) == ("instrument", letters)
    assert (parsed.unit, parsed.sequence) == (7, 999)
    assert (parsed.first, parsed.functions) == (letters[0], letters[1:])


@pytest.mark.parametrize(
    ("kind", "codes", "formatter"),
    [
        ("valve", VALVE_CODES, tags.format_valve_tag),
        ("safety", SAFETY_CODES, tags.format_safety_tag),
        ("fitting", FITTING_CODES, tags.format_fitting_tag),
    ],
)
def test_hardware_code_round_trip(kind: str, codes: frozenset[str], formatter: _Formatter) -> None:
    for code in sorted(codes):
        parsed = tags.parse_tag(formatter(code, 31, 5))
        assert parsed is not None
        assert (parsed.kind, parsed.letters, parsed.unit, parsed.sequence) == (kind, code, 31, 5)


def test_ambiguous_codes_are_the_documented_ones() -> None:
    # hardware codes that are also valid ISA letters; parse reads them as hardware
    assert AMBIGUOUS_LETTERS == {"BFV", "BV", "FA", "PGV", "PSE", "PSV", "PVSV", "SG", "ST"}


def test_line_number_round_trip() -> None:
    for size in LINE_SIZES:
        for service in LINE_SERVICES:
            text = tags.format_line_number(size, service, 9, 44, "B1A", "HT")
            assert tags.parse_line_number(text) == tags.ParsedLineNumber(
                size=size, service=service, unit=9, sequence=44, spec="B1A", insulation="HT"
            )
    for spec in LINE_SPECS:
        for insulation in LINE_INSULATIONS:
            text = tags.format_line_number(4, "CWS", 120, 9999, spec, insulation)
            parsed = tags.parse_line_number(text)
            assert parsed is not None
            assert (parsed.unit, parsed.sequence, parsed.spec) == (120, 9999, spec)


def test_equipment_tags_are_injective_over_random_fields() -> None:
    rng = random.Random(0)
    types = sorted(EQUIPMENT_TYPE_CODES)
    fields = {
        (rng.choice(types), *_random_unit_and_sequence(rng, 2), rng.choice([None, *SPARE_SUFFIXES]))
        for _ in range(_RANDOM_FIELDS)
    }
    rendered = {tags.format_equipment_tag(t, u, s, tr) for t, u, s, tr in fields}
    assert len(rendered) == len(fields)


def test_instrument_and_line_numbers_are_injective_over_random_fields() -> None:
    rng = random.Random(1)
    letters = ["FIC", "PT", "XV", "LSHH", "FV", "PDI", "AT"]
    instrument_fields = {
        (rng.choice(letters), *_random_unit_and_sequence(rng, 3)) for _ in range(_RANDOM_FIELDS)
    }
    rendered = {tags.format_instrument_tag(*fields) for fields in instrument_fields}
    assert len(rendered) == len(instrument_fields)
    line_fields = {
        (rng.choice(LINE_SIZES), rng.choice(LINE_SERVICES), *_random_unit_and_sequence(rng, 4))
        for _ in range(_RANDOM_FIELDS)
    }
    lines = {tags.format_line_number(z, v, u, s, "A1A", "N") for z, v, u, s in line_fields}
    assert len(lines) == len(line_fields)


def test_random_fields_parse_back_to_themselves() -> None:
    rng = random.Random(2)
    for _ in range(_RANDOM_FIELDS):
        unit, sequence = _random_unit_and_sequence(rng, 2)
        parsed = tags.parse_tag(tags.format_equipment_tag("P", unit, sequence, "B"))
        assert parsed is not None
        assert (parsed.unit, parsed.sequence) == (unit, sequence)


@pytest.mark.parametrize(
    "call",
    [
        lambda: tags.format_equipment_tag("P", 1, 100),
        lambda: tags.format_instrument_tag("FIC", 1, 1000),
        lambda: tags.format_valve_tag("GTV", 1, 1000),
        lambda: tags.format_line_number(6, "P", 1, 10000, "A1A", "N"),
        lambda: tags.format_equipment_tag("P", 1, 0),
        lambda: tags.format_equipment_tag("P", 0, 1),
        lambda: tags.format_equipment_tag("ZZ", 1, 1),
        lambda: tags.format_equipment_tag("P", 1, 1, "D"),
        lambda: tags.format_instrument_tag("GV", 1, 1),
        lambda: tags.format_valve_tag("PSV", 1, 1),
        lambda: tags.format_line_number(5, "P", 1, 1, "A1A", "N"),
        lambda: tags.format_line_number(6, "XX", 1, 1, "A1A", "N"),
    ],
)
def test_overflow_and_unknown_codes_raise(call: Callable[[], str]) -> None:
    with pytest.raises(ValueError, match="expected"):
        call()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "P-3",
        "P-03",
        "P-0103",
        "P-1203Z",
        "FIC-12014A",
        "ZZ-12014",
        "p-1203",
        "P 1203",
        "P-1200",
    ],
)
def test_parse_tag_rejects_non_tags(text: str) -> None:
    assert tags.parse_tag(text) is None


@pytest.mark.parametrize(
    "text",
    ["6-P-120017", "5-P-120017-A1A-N", "6-XX-120017-A1A-N", "06-P-120017-A1A-N", "6-P-17-A1A-N"],
)
def test_parse_line_number_rejects_non_lines(text: str) -> None:
    assert tags.parse_line_number(text) is None


def test_every_generated_identifier_is_one_anchor_token() -> None:
    samples = [tags.format_equipment_tag(t, 12, 3, "A") for t in sorted(EQUIPMENT_TYPE_CODES)]
    samples += [tags.format_valve_tag(c, 12, 9) for c in sorted(VALVE_CODES)]
    samples += [tags.format_safety_tag(c, 12, 9) for c in sorted(SAFETY_CODES)]
    samples += [tags.format_fitting_tag(c, 12, 9) for c in sorted(FITTING_CODES)]
    samples += [tags.format_instrument_tag(c, 12, 9) for c in ("FIC", "LSHH", "XV", "ZSC")]
    samples += [tags.format_line_number(24, s, 120, 9999, "D1A", "HT") for s in LINE_SERVICES]
    for sample in samples:
        assert _TOKEN_RE.fullmatch(sample) is not None, sample
