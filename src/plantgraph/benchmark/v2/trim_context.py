"""What a trim needs from its caller: numbers, randomness, the config, the class decks.

A **trim** (design generator-v2-realism.md 6) is the fixed set of small parts a drawing repeats
around a machine or a line: a pump's suction strainer, a control valve's block-and-bypass valves.
Trims are written as functions of a `TrimContext`. The context is created once per process unit,
so every trim of the unit draws its tag numbers from the same counters and no two parts collide.
"""

from __future__ import annotations

import random
from collections import Counter

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config import TrimConvention
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.tags import (
    format_equipment_tag,
    format_fitting_tag,
    format_instrument_tag,
    format_line_number,
    format_safety_tag,
    format_valve_tag,
)
from plantgraph.benchmark.v2.vocabulary import LINE_SIZES, TrainConventions
from plantgraph.graph.schema import CLASS_SPECS, NodeClass


class LineStyle(BaseModel):
    """The line-number fields of a run of pipe: what a trim copies onto the branches it adds."""

    model_config = ConfigDict(frozen=True)

    size: int
    service: str = "P"
    spec: str = "A1A"
    insulation: str = "N"

    def branch(self, size: int | None = None, service: str | None = None) -> LineStyle:
        """The style of a branch: a smaller pipe (default: one size down, at least 1 inch)."""
        smaller = self._smaller_size() if size is None else size
        return self.model_copy(update={"size": smaller, "service": service or self.service})

    def _smaller_size(self) -> int:
        index = LINE_SIZES.index(self.size)
        return LINE_SIZES[max(index - 1, 0)]


class UnitNumbering:
    """The tag-number counters of one unit (design 5: which counter each number comes from).

    Equipment numbers count per (unit, type), manual-valve numbers per (unit, valve code), and one
    counter is shared by instrument loops, local instruments, safety devices and fittings, so
    loop numbers interleave as on a real drawing. Overflow raises in `tags.py`.
    """

    def __init__(self, unit_no: int) -> None:
        self.unit_no = unit_no
        self._counts: Counter[str] = Counter()

    def node_id(self) -> str:
        """A plan id for a part a trim adds; unique within the plant because it has the unit."""
        return f"u{self.unit_no}-t{self._next('node')}"

    def equipment_tag(self, type_code: str, train: str | None = None) -> str:
        """`V-1203`: the next equipment tag of this type."""
        return format_equipment_tag(type_code, self.unit_no, self._next(f"eq:{type_code}"), train)

    def instrument_number(self) -> int:
        """The next number of the shared loop / local-instrument / safety / fitting counter."""
        return self._next("instrument")

    def instrument_tag(self, letters: str) -> str:
        """`PI-12021`: a tag with a fresh number."""
        return format_instrument_tag(letters, self.unit_no, self.instrument_number())

    def line_number(self, style: LineStyle) -> str:
        """The next line number of the unit, with the fields of `style`."""
        sequence = self._next("line")
        return format_line_number(
            style.size, style.service, self.unit_no, sequence, style.spec, style.insulation
        )

    def part_tag(self, node_class: str) -> str | None:
        """The printed tag of a piping part of `node_class`; None when the class prints none.

        Loop-bound parts (control and on-off valve bodies, flow elements) are numbered by the
        trim that creates them, from `instrument_number`, not here.
        """
        spec = CLASS_SPECS[NodeClass(node_class)]
        prefix = spec.tag_prefix
        if prefix is None:
            return None
        if spec.piping_kind in ("operated", "check"):
            return format_valve_tag(prefix, self.unit_no, self._next(f"valve:{prefix}"))
        if spec.piping_kind == "safety":
            return format_safety_tag(prefix, self.unit_no, self.instrument_number())
        if spec.piping_kind == "fitting":
            return format_fitting_tag(prefix, self.unit_no, self.instrument_number())
        raise ValueError(f"expected a valve, safety device or fitting class, got {node_class!r}")

    def _next(self, counter: str) -> int:
        self._counts[counter] += 1
        return self._counts[counter]


class TrimContext:
    """Everything one unit's trims share. Trims never create their own randomness (design 6)."""

    def __init__(
        self,
        unit_no: int,
        rng: random.Random,
        config: TrimConvention,
        conventions: TrainConventions,
        decks: VariantDecks,
        numbering: UnitNumbering | None = None,
    ) -> None:
        self.unit_no = unit_no
        self.rng = rng
        self.config = config
        self.conventions = conventions
        self.decks = decks
        self.numbering = numbering or UnitNumbering(unit_no)
        if self.numbering.unit_no != unit_no:
            raise ValueError(
                f"numbering is for unit {self.numbering.unit_no}, expected unit {unit_no}"
            )

    def chance(self, probability: float) -> bool:
        """True with the given probability, drawn from the unit's stream."""
        return self.rng.random() < probability

    def deal_class(self, role: str) -> str:
        """The next class of the role's deck (see `class_decks.py`)."""
        return self.decks.deal(f"role:{role}")
