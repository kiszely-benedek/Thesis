"""The code tables behind the v2 tags: which letters exist, and what kind of item a tag names.

A **tag** is the identifier printed next to a symbol on a P&ID (`P-1203A`, `FIC-12014`). Its letters
say what the item is. Two code families meet here: **hardware codes** (`GTV` = gate valve, `TK` =
tank) and **ISA letters** (ISA-5.1 is the instrument-letter standard: `F` = flow, `T` =
transmitter, `IC` = indicating controller). The class-to-prefix table is not repeated here: it is
read from the generated schema vocabulary (`graph/schema_vocabulary.py`, from T1).

The module also holds the two *per-train conventions* (generator-v2-pid-vocabulary.md 5.2): one
train is one design contractor, so the on-off valve letter and the spare-numbering style are drawn
once per train and kept.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, ConfigDict

from plantgraph.graph.schema import (
    CLASS_SPECS,
    CONTROL_VALVE_BODY_CLASSES,
    EQUIPMENT_CLASSES,
    FITTING_CLASSES,
    OPERATED_VALVE_CLASSES,
    VALVE_CLASSES,
)
from plantgraph.graph.schema_classes import NodeCategory, NodeClass

# --- code sets read from the schema vocabulary -------------------------------------------------


def _prefixes(node_classes: Iterable[str]) -> frozenset[str]:
    """The tag prefixes of `node_classes`; a class with no prefix (a pipe tee) adds nothing."""
    specs = (CLASS_SPECS[NodeClass(name)] for name in node_classes)
    return frozenset(spec.tag_prefix for spec in specs if spec.tag_prefix is not None)


def _prefix_of(node_class: str) -> str | None:
    return CLASS_SPECS[NodeClass(node_class)].tag_prefix


_CHECK_CLASSES = frozenset(
    name.value for name, spec in CLASS_SPECS.items() if spec.piping_kind == "check"
)

#: Reactor `R` and reflux drum `D` reuse the `PressureVessel` class (table prefix: drum `V`).
PRESSURE_VESSEL_ROLE_CODES: dict[str, str] = {"drum": "V", "reactor": "R", "reflux_drum": "D"}
EQUIPMENT_TYPE_CODES: frozenset[str] = _prefixes(EQUIPMENT_CLASSES) | frozenset(
    PRESSURE_VESSEL_ROLE_CODES.values()
)
#: Manual valves and check valves: `GTV`, `GV`, `BV`, `CHV`, ...
VALVE_CODES: frozenset[str] = _prefixes(OPERATED_VALVE_CLASSES | _CHECK_CLASSES)
#: Safety devices: `PSV`, `PSE`, `PVSV`, `FA`.
SAFETY_CODES: frozenset[str] = _prefixes(VALVE_CLASSES - OPERATED_VALVE_CLASSES - _CHECK_CLASSES)
#: Tagged fittings that are not drawn as instruments: `STR`, `FO`, `ST`, `SG`, `MX`, `SB`, `SL`.
FITTING_CODES: frozenset[str] = _prefixes(FITTING_CLASSES)

# --- ISA letters -------------------------------------------------------------------------------

#: First letters (the measured or initiating variable): 15 of them (design 5.3).
ISA_FIRST_LETTERS = "ABCFHILPSTUVXYZ"
#: Modifier after the first letter: D = differential, F = ratio, Q = totalised, S = safety.
#: `S` is also the switch function letter (`PSHH` = pressure switch high-high), and `PSV` reads as
#: P + safety + V (pressure safety valve). The parser stores only `letters`/`first`/`functions`,
#: so it never has to decide which role an `S` plays.
ISA_MODIFIERS = "DFQS"
#: Function letters: E element, G gauge, I indicate, T transmit, C control, S switch, V valve,
#: A alarm, Y relay.
ISA_FUNCTION_LETTERS = "EGITCSVAY"
#: Trailing function modifiers: high, low, high-high, low-low, open, closed.
ISA_FUNCTION_MODIFIERS = ("HH", "LL", "H", "L", "O", "C")

ISA_LETTERS_PATTERN = re.compile(
    rf"[{ISA_FIRST_LETTERS}][{ISA_MODIFIERS}]?[{ISA_FUNCTION_LETTERS}]{{1,3}}"
    rf"(?:{'|'.join(ISA_FUNCTION_MODIFIERS)})?"
)

#: Spare letters after an equipment number: `P-1203A`, `P-1203B` (design 5 grammar, TRAIN).
SPARE_SUFFIXES = ("A", "B", "C")


def is_isa_letters(letters: str) -> bool:
    """True when `letters` is a valid ISA instrument-letter code such as `FIC` or `PDT`."""
    return ISA_LETTERS_PATTERN.fullmatch(letters) is not None


#: Letter codes that are both a hardware code and valid ISA (`ST` steam trap or speed transmitter).
#: Reading a tag alone cannot tell them apart; `item_kind` can, because it also gets the class.
AMBIGUOUS_LETTERS: frozenset[str] = frozenset(
    code
    for code in VALVE_CODES | SAFETY_CODES | FITTING_CODES | EQUIPMENT_TYPE_CODES
    if is_isa_letters(code)
)

# --- line-number fields -------------------------------------------------------------------------
# A **line number** names one pipe run in the line list: size, service, number, spec, insulation.
# The codes are invented but plausible (design 5); real companies use their own.

#: Nominal pipe size in inches.
LINE_SIZES: tuple[int, ...] = (1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24)
#: Service: process liquid / gas, cooling water supply / return, low / medium pressure steam,
#: condensate, fuel gas, flare, instrument air, nitrogen.
LINE_SERVICES: tuple[str, ...] = (
    "P",
    "PG",
    "CWS",
    "CWR",
    "LPS",
    "MPS",
    "CD",
    "FG",
    "FL",
    "IA",
    "N",
)
#: Piping class (the pipe's material and pressure rating), in rating order.
LINE_SPECS: tuple[str, ...] = ("A1A", "B1A", "C1A", "D1A")
#: Insulation: none, hot, cold, personnel protection, heat traced.
LINE_INSULATIONS: tuple[str, ...] = ("N", "H", "C", "P", "HT")

# --- what kind of item a tag names -------------------------------------------------------------


class ItemKind(str, Enum):
    """What an item is, for a reader of the drawing: derived from its class and tag letters."""

    EQUIPMENT = "equipment"
    MANUAL_VALVE = "manual_valve"
    CHECK_VALVE = "check_valve"
    CONTROL_VALVE = "control_valve"
    ON_OFF_VALVE = "on_off_valve"
    SAFETY_DEVICE = "safety_device"
    FITTING = "fitting"
    PRIMARY_ELEMENT = "primary_element"
    TRANSMITTER = "transmitter"
    LOCAL_INDICATOR = "local_indicator"
    POSITION_SWITCH = "position_switch"
    CONTROLLER = "controller"
    HAND_SWITCH = "hand_switch"
    ALARM = "alarm"
    SWITCH = "switch"
    INDICATOR = "indicator"


_POSITION_SWITCH_LETTERS = frozenset({"ZSO", "ZSC"})
_ON_OFF_VALVE_LETTERS = frozenset({"XV", "YV"})


def item_kind(node_class: str, letters: str) -> ItemKind:
    """The kind of the item of class `node_class` whose tag letters are `letters`.

    Raises:
        ValueError: the class is unknown, carries no printed tag, or the letters do not fit it.
    """
    if node_class not in {member.value for member in NodeClass}:
        raise ValueError(f"unknown node class {node_class!r}")
    spec = CLASS_SPECS[NodeClass(node_class)]
    if spec.category is NodeCategory.EQUIPMENT:
        return _equipment_kind(node_class, letters)
    if spec.category is NodeCategory.PIPING:
        return _piping_kind(node_class, letters)
    if spec.category is NodeCategory.INSTRUMENTATION:
        return _instrument_kind(node_class, letters)
    raise ValueError(f"{node_class} is not a tagged item (category {spec.category.value})")


def _equipment_kind(node_class: str, letters: str) -> ItemKind:
    allowed = _equipment_codes_of(node_class)
    if letters not in allowed:
        raise ValueError(f"{node_class} takes tag letters {sorted(allowed)}, got {letters!r}")
    return ItemKind.EQUIPMENT


def _equipment_codes_of(node_class: str) -> frozenset[str]:
    prefix = _prefix_of(node_class)
    codes = frozenset() if prefix is None else frozenset({prefix})
    if node_class == NodeClass.PRESSURE_VESSEL.value:
        return codes | frozenset(PRESSURE_VESSEL_ROLE_CODES.values())
    return codes


def _piping_kind(node_class: str, letters: str) -> ItemKind:
    spec = CLASS_SPECS[NodeClass(node_class)]
    # control and on-off valves are tagged by the loop (`FV-...`), not by the class prefix
    if spec.piping_kind == "operated" and _is_loop_valve_tag(node_class, letters):
        return _loop_valve_kind(node_class, letters)
    if spec.tag_prefix is None:
        raise ValueError(f"{node_class} is an untagged pipe part; it has no item kind")
    if letters != spec.tag_prefix:
        raise ValueError(f"{node_class} takes tag letters {spec.tag_prefix!r}, got {letters!r}")
    return _KIND_OF_PIPING[spec.piping_kind or "fitting"]


_KIND_OF_PIPING: dict[str, ItemKind] = {
    "check": ItemKind.CHECK_VALVE,
    "operated": ItemKind.MANUAL_VALVE,
    "safety": ItemKind.SAFETY_DEVICE,
    "primary_element": ItemKind.PRIMARY_ELEMENT,
    "fitting": ItemKind.FITTING,
    "junction": ItemKind.FITTING,
    "break": ItemKind.FITTING,
}


def _is_loop_valve_tag(node_class: str, letters: str) -> bool:
    """True for a tag like `FV` or `XV` on a class that can be a loop valve."""
    can_be_loop_valve = (
        node_class in CONTROL_VALVE_BODY_CLASSES or node_class == NodeClass.BALL_VALVE.value
    )
    is_loop_tag = letters.endswith("V") and is_isa_letters(letters)
    return can_be_loop_valve and is_loop_tag and letters != _prefix_of(node_class)


def _loop_valve_kind(node_class: str, letters: str) -> ItemKind:
    if letters in _ON_OFF_VALVE_LETTERS:
        return ItemKind.ON_OFF_VALVE
    if node_class not in CONTROL_VALVE_BODY_CLASSES:
        raise ValueError(f"{node_class} cannot be a control valve (tag letters {letters!r})")
    return ItemKind.CONTROL_VALVE


def _instrument_kind(node_class: str, letters: str) -> ItemKind:
    if not is_isa_letters(letters):
        raise ValueError(f"{node_class} takes ISA instrument letters, got {letters!r}")
    if node_class == NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
        return _sensor_kind(letters)
    if node_class in (
        NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        NodeClass.PROCESS_CONTROL_FUNCTION.value,
    ):
        return _bubble_kind(node_class, letters)
    raise ValueError(f"{node_class} is not a tagged item; it has no item kind")


def _sensor_kind(letters: str) -> ItemKind:
    if letters in _POSITION_SWITCH_LETTERS:
        return ItemKind.POSITION_SWITCH
    if letters[-1] in "TE":
        return ItemKind.TRANSMITTER
    if letters[-1] in "IG":
        return ItemKind.LOCAL_INDICATOR
    if _is_switch_sensor(letters):
        return ItemKind.SWITCH
    raise ValueError(
        "a sensor's letters end in T, E, I or G, are ZSO/ZSC or are a switch such as LSH, "
        f"got {letters!r}"
    )


def _is_switch_sensor(letters: str) -> bool:
    """A point switch (`LSH`, `LSL`): S among the function letters, then a high / low modifier."""
    return "S" in letters[1:] and letters.endswith(("H", "L"))


def _bubble_kind(node_class: str, letters: str) -> ItemKind:
    functions = letters[1:]
    if node_class == NodeClass.PROCESS_CONTROL_FUNCTION.value:
        return ItemKind.CONTROLLER
    if letters == "HS":
        return ItemKind.HAND_SWITCH
    if functions.endswith("C"):
        return ItemKind.CONTROLLER
    if "A" in functions:
        return ItemKind.ALARM
    if "S" in functions:
        return ItemKind.SWITCH
    return ItemKind.INDICATOR


# --- per-train conventions ---------------------------------------------------------------------


class OnOffLetter(str, Enum):
    """First letter of an on-off valve's tag: `XV`/`XY` or `YV`/`YY` (samples: both are used)."""

    X = "X"
    Y = "Y"


class SpareNaming(str, Enum):
    """How installed spares are numbered: `P-1203A`/`B` (suffix) or `P-1203`/`P-1204`."""

    SUFFIX = "suffix"
    CONSECUTIVE = "consecutive"


#: Declared draw weights (design 7.1): letters 1 : 1, spare naming 3 : 2. Not frequency claims.
ON_OFF_LETTER_WEIGHTS: tuple[int, int] = (1, 1)
SPARE_NAMING_WEIGHTS: tuple[int, int] = (3, 2)


class TrainConventions(BaseModel):
    """The two naming conventions of one train; every tag of the train follows them."""

    model_config = ConfigDict(frozen=True)

    on_off_letter: OnOffLetter
    spare_naming: SpareNaming

    @property
    def on_off_valve_letters(self) -> str:
        """Tag letters of an on-off valve body: `XV` or `YV`."""
        return f"{self.on_off_letter.value}V"

    @property
    def on_off_solenoid_letters(self) -> str:
        """Tag letters of the valve's solenoid (the small electric actuator): `XY` or `YY`."""
        return f"{self.on_off_letter.value}Y"


def draw_train_conventions(rng: random.Random) -> TrainConventions:
    """Draw one train's conventions; call once per train, from that train's own stream."""
    letter = rng.choices(list(OnOffLetter), weights=ON_OFF_LETTER_WEIGHTS)[0]
    naming = rng.choices(list(SpareNaming), weights=SPARE_NAMING_WEIGHTS)[0]
    return TrainConventions(on_off_letter=letter, spare_naming=naming)


class SpareMember(BaseModel):
    """One machine of a spared set: its number offset from the first number, and its suffix."""

    model_config = ConfigDict(frozen=True)

    sequence_offset: int
    train: str | None


def spare_members(naming: SpareNaming, count: int) -> tuple[SpareMember, ...]:
    """The tag parts of `count` identical machines (1 to 3) under the given spare naming.

    A single machine has no spare, so it carries a plain number under both namings.
    """
    if not 1 <= count <= len(SPARE_SUFFIXES):
        raise ValueError(f"a spared set has 1 to {len(SPARE_SUFFIXES)} machines, got {count}")
    if count == 1:
        return (SpareMember(sequence_offset=0, train=None),)
    if naming is SpareNaming.SUFFIX:  # one shared number, letters tell the machines apart
        return tuple(SpareMember(sequence_offset=0, train=SPARE_SUFFIXES[i]) for i in range(count))
    return tuple(SpareMember(sequence_offset=i, train=None) for i in range(count))


def numbers_used(naming: SpareNaming, count: int) -> int:
    """How many equipment numbers a set of `count` machines uses; the planner advances by it."""
    return 1 if naming is SpareNaming.SUFFIX else count
