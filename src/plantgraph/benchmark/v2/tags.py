"""Write and read the identifiers printed on a drawing: tags and line numbers (design 5).

Every identifier is `CODE "-" UNIT SEQUENCE [SPARE]`: the unit number has any width, the sequence
after it has a fixed width, so the two digit runs never blur and the identifier is unique per
(code, unit, sequence). Every output is one token of the question-anchor pattern in `qa/anchors.py`
(letters and digits joined by `-`), so a question can name it.

```
equipment     P-1203A   TK-1202    unit 12, sequence 03 (2 digits), spare suffix A
instrument    FIC-12014 XV-12030   unit 12, sequence 014 (3 digits); loop members share the number
manual valve  GTV-12107  safety PSV-12012  fitting STR-12041
line number   6-P-120017-A1A-N     size, service, unit 12 + sequence 0017, spec, insulation
```
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.vocabulary import (
    EQUIPMENT_TYPE_CODES,
    FITTING_CODES,
    LINE_INSULATIONS,
    LINE_SERVICES,
    LINE_SIZES,
    LINE_SPECS,
    SAFETY_CODES,
    SPARE_SUFFIXES,
    VALVE_CODES,
    is_isa_letters,
)

TagKind = Literal["equipment", "instrument", "valve", "safety", "fitting"]

#: Digits of the fixed-width sequence field, per identifier family.
EQUIPMENT_SEQUENCE_WIDTH = 2
INSTRUMENT_SEQUENCE_WIDTH = 3
LINE_SEQUENCE_WIDTH = 4

_TAG_RE = re.compile(r"([A-Z]+)-([0-9]+)([A-Z]?)")


class ParsedTag(BaseModel):
    """A tag split into its fields. `functions` is every letter after the first (`IC` of `FIC`)."""

    model_config = ConfigDict(frozen=True)

    kind: TagKind
    letters: str
    first: str
    functions: str
    unit: int
    sequence: int
    train: str | None = None


class ParsedLineNumber(BaseModel):
    """A line number split into its fields."""

    model_config = ConfigDict(frozen=True)

    size: int
    service: str
    unit: int
    sequence: int
    spec: str
    insulation: str


# --- formatting --------------------------------------------------------------------------------


def format_equipment_tag(type_code: str, unit: int, sequence: int, train: str | None = None) -> str:
    """`P-1203` or, for an installed spare, `P-1203A`."""
    _require_member(type_code, EQUIPMENT_TYPE_CODES, "equipment type code")
    if train is not None:
        _require_member(train, frozenset(SPARE_SUFFIXES), "spare suffix")
    number = _join_number(unit, sequence, EQUIPMENT_SEQUENCE_WIDTH)
    return f"{type_code}-{number}{train or ''}"


def format_instrument_tag(letters: str, unit: int, sequence: int) -> str:
    """`FIC-12014`; the letters must be valid ISA instrument letters (a control valve is `FV`)."""
    if not is_isa_letters(letters):
        raise ValueError(f"expected valid ISA instrument letters, got {letters!r}")
    return f"{letters}-{_join_number(unit, sequence, INSTRUMENT_SEQUENCE_WIDTH)}"


def format_valve_tag(code: str, unit: int, sequence: int) -> str:
    """`GTV-12107`: a manual or check valve."""
    return _format_coded(code, VALVE_CODES, "valve code", unit, sequence)


def format_safety_tag(code: str, unit: int, sequence: int) -> str:
    """`PSV-12012`: a safety device, numbered like an instrument."""
    return _format_coded(code, SAFETY_CODES, "safety device code", unit, sequence)


def format_fitting_tag(code: str, unit: int, sequence: int) -> str:
    """`STR-12041`: a tagged fitting."""
    return _format_coded(code, FITTING_CODES, "fitting code", unit, sequence)


def format_line_number(
    size: int, service: str, unit: int, sequence: int, spec: str, insulation: str
) -> str:
    """`6-P-120017-A1A-N`."""
    if size not in LINE_SIZES:
        raise ValueError(f"expected a line size in {LINE_SIZES}, got {size!r}")
    _require_member(service, frozenset(LINE_SERVICES), "line service")
    _require_member(spec, frozenset(LINE_SPECS), "line spec")
    _require_member(insulation, frozenset(LINE_INSULATIONS), "line insulation")
    number = _join_number(unit, sequence, LINE_SEQUENCE_WIDTH)
    return f"{size}-{service}-{number}-{spec}-{insulation}"


def _format_coded(code: str, allowed: frozenset[str], what: str, unit: int, sequence: int) -> str:
    _require_member(code, allowed, what)
    return f"{code}-{_join_number(unit, sequence, INSTRUMENT_SEQUENCE_WIDTH)}"


def _require_member(value: str, allowed: frozenset[str], what: str) -> None:
    if value not in allowed:
        raise ValueError(f"expected a {what} in {sorted(allowed)}, got {value!r}")


def _join_number(unit: int, sequence: int, width: int) -> str:
    """`unit` then `sequence` zero-padded to `width`; raises on overflow instead of truncating."""
    if unit < 1:
        raise ValueError(f"expected a unit number of at least 1, got {unit}")
    largest = 10**width - 1
    if not 1 <= sequence <= largest:
        raise ValueError(f"expected a sequence in 1..{largest} ({width} digits), got {sequence}")
    return f"{unit}{sequence:0{width}d}"


# --- parsing -----------------------------------------------------------------------------------


def parse_tag(tag: str) -> ParsedTag | None:
    """Split a tag into fields, or return None when `tag` is not a tag of this grammar.

    A few codes are both hardware and ISA letters (`ST` steam trap, speed transmitter); this reads
    them as hardware. The authoritative kind is `vocabulary.item_kind(node_class, letters)`.
    """
    match = _TAG_RE.fullmatch(tag)
    if match is None:
        return None
    letters, digits, train = match.groups()
    kind = _kind_of_letters(letters)
    if kind is None or not _train_fits(kind, train):
        return None
    split = _split_number(digits, _sequence_width(kind))
    if split is None:
        return None
    unit, sequence = split
    return ParsedTag(
        kind=kind,
        letters=letters,
        first=letters[0],
        functions=letters[1:],
        unit=unit,
        sequence=sequence,
        train=train or None,
    )


def parse_line_number(text: str) -> ParsedLineNumber | None:
    """Split a line number into fields, or return None when `text` is not one."""
    parts = text.split("-")
    if len(parts) != 5:
        return None
    size, service, digits, spec, insulation = parts
    split = _split_number(digits, LINE_SEQUENCE_WIDTH)
    size_value = int(size) if size.isdigit() else None
    if split is None or size_value not in LINE_SIZES or str(size_value) != size:
        return None
    if service not in LINE_SERVICES or spec not in LINE_SPECS or insulation not in LINE_INSULATIONS:
        return None
    return ParsedLineNumber(
        size=size_value,
        service=service,
        unit=split[0],
        sequence=split[1],
        spec=spec,
        insulation=insulation,
    )


def _kind_of_letters(letters: str) -> TagKind | None:
    """Hardware codes first, then ISA letters (see `parse_tag` for the overlap)."""
    if letters in VALVE_CODES:
        return "valve"
    if letters in SAFETY_CODES:
        return "safety"
    if letters in FITTING_CODES:
        return "fitting"
    if letters in EQUIPMENT_TYPE_CODES:
        return "equipment"
    return "instrument" if is_isa_letters(letters) else None


def _train_fits(kind: TagKind, train: str) -> bool:
    """Only equipment carries a spare suffix, and only a known one."""
    if not train:
        return True
    return kind == "equipment" and train in SPARE_SUFFIXES


def _sequence_width(kind: TagKind) -> int:
    return EQUIPMENT_SEQUENCE_WIDTH if kind == "equipment" else INSTRUMENT_SEQUENCE_WIDTH


def _split_number(digits: str, width: int) -> tuple[int, int] | None:
    """Undo `_join_number`: the last `width` digits are the sequence, the rest the unit."""
    if not digits.isdigit() or len(digits) <= width or digits[0] == "0":
        return None  # the unit starts at 1, so a leading zero never came from `_join_number`
    sequence = int(digits[-width:])
    return (int(digits[:-width]), sequence) if sequence >= 1 else None
