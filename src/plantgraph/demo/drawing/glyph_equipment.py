"""ISO-style symbols for equipment: pumps, compressors, vessels, columns, exchangers, ...

Each drawer is sized for the standard box (56 x 28 pt); a column is drawn in a taller box.
The names are the values of `glyph_families.GLYPH_FAMILIES`.
"""

from __future__ import annotations

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.glyph_kit import (
    EQUIPMENT_FILL,
    INK,
    Drawer,
    circle,
    polygon,
    stubs,
    tint,
    zigzag,
)
from plantgraph.demo.drawing.glyph_pen import Pen

_R = 11.0  # radius of the round machines


def _capsule(pdf: Pen, box: Box, width: float, height: float) -> None:
    """A rounded rectangle centred in `box`: the body of a vessel."""
    pdf.rect(
        box.x - width / 2,
        box.y - height / 2,
        width,
        height,
        style="DF",
        round_corners=True,
        corner_radius=min(width, height) / 2,
    )


def _round_machine(pdf: Pen, box: Box) -> None:
    stubs(pdf, box, _R)
    tint(pdf, EQUIPMENT_FILL)
    circle(pdf, box.x, box.y, _R)


def pump(pdf: Pen, box: Box) -> None:
    """A circle with a triangle pointing at the discharge (right)."""
    _round_machine(pdf, box)
    polygon(
        pdf,
        [(box.x - 5, box.y - 6.5), (box.x - 5, box.y + 6.5), (box.x + 8, box.y)],
        style="D",
    )


def positive_pump(pdf: Pen, box: Box) -> None:
    """A circle with a square: a pump that pushes a fixed volume (piston, gear, screw)."""
    _round_machine(pdf, box)
    pdf.rect(box.x - 5, box.y - 5, 10, 10, style="D")


def compressor(pdf: Pen, box: Box) -> None:
    """A circle with two lines narrowing towards the outlet."""
    _round_machine(pdf, box)
    pdf.line(box.x - 7.5, box.y - 7.5, box.x + 10, box.y - 3)
    pdf.line(box.x - 7.5, box.y + 7.5, box.x + 10, box.y + 3)


def ejector(pdf: Pen, box: Box) -> None:
    """A venturi (hourglass) with a suction branch on top."""
    stubs(pdf, box, 14)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    polygon(
        pdf,
        [
            (x - 14, y - 8),
            (x - 3, y - 3),
            (x + 14, y - 8),
            (x + 14, y + 8),
            (x - 3, y + 3),
            (x - 14, y + 8),
        ],
    )
    pdf.line(x - 3, y - 3, x - 3, y - 12)


def vessel(pdf: Pen, box: Box) -> None:
    """A horizontal rounded rectangle: a drum or pressure vessel."""
    stubs(pdf, box, 20)
    tint(pdf, EQUIPMENT_FILL)
    _capsule(pdf, box, 40, 22)


def tank(pdf: Pen, box: Box) -> None:
    """A storage tank: straight walls and a cone roof."""
    stubs(pdf, box, 12)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    pdf.rect(x - 12, y - 9, 24, 21, style="DF")
    polygon(pdf, [(x - 12, y - 9), (x, y - 15), (x + 12, y - 9)])


def column(pdf: Pen, box: Box) -> None:
    """A tall rounded body with trays (the short horizontal lines) inside."""
    stubs(pdf, box, 9)
    tint(pdf, EQUIPMENT_FILL)
    x, y, height = box.x, box.y, box.height
    pdf.rect(x - 9, y - height / 2, 18, height, style="DF", round_corners=True, corner_radius=9)
    for offset in (-0.3, -0.1, 0.1, 0.3):
        pdf.line(x - 6, y + offset * height, x + 6, y + offset * height)


def scrubber(pdf: Pen, box: Box) -> None:
    """A tall vessel with a mesh pad (zigzag) across the upper part."""
    stubs(pdf, box, 9)
    tint(pdf, EQUIPMENT_FILL)
    x, y, height = box.x, box.y, box.height
    pdf.rect(x - 9, y - height / 2, 18, height, style="DF", round_corners=True, corner_radius=9)
    zigzag(pdf, x - 7, x + 7, y - 0.15 * height, 2.0, 3)


def separator(pdf: Pen, box: Box) -> None:
    """A horizontal vessel with a weir (the vertical line) that splits the liquids."""
    stubs(pdf, box, 20)
    tint(pdf, EQUIPMENT_FILL)
    _capsule(pdf, box, 40, 22)
    pdf.line(box.x + 6, box.y + 11, box.x + 6, box.y - 3)


def electric_separator(pdf: Pen, box: Box) -> None:
    """A horizontal vessel with electrode plates."""
    stubs(pdf, box, 20)
    tint(pdf, EQUIPMENT_FILL)
    _capsule(pdf, box, 40, 22)
    for offset in (-6, 0, 6):
        pdf.line(box.x + offset, box.y - 6, box.x + offset, box.y + 6)


def filter_(pdf: Pen, box: Box) -> None:
    """A rectangle crossed by diagonal lines (the filter medium)."""
    stubs(pdf, box, 13)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    pdf.rect(x - 13, y - 10, 26, 20, style="DF")
    for shift in (-6, 0, 6):
        pdf.line(x + shift - 5, y + 10, x + shift + 5, y - 10)


def static_mixer(pdf: Pen, box: Box) -> None:
    """A pipe section with a zigzag of mixing elements."""
    stubs(pdf, box, 16)
    tint(pdf, EQUIPMENT_FILL)
    pdf.rect(box.x - 16, box.y - 8, 32, 16, style="DF")
    zigzag(pdf, box.x - 13, box.x + 13, box.y, 4.5, 4)


def rotary_mixer(pdf: Pen, box: Box) -> None:
    """A circle with a propeller (two crossed blades): a mixer with a driven rotor."""
    _round_machine(pdf, box)
    x, y = box.x, box.y
    pdf.line(x - 6, y - 6, x + 6, y + 6)
    pdf.line(x - 6, y + 6, x + 6, y - 6)


def agitator(pdf: Pen, box: Box) -> None:
    """A motor (the small circle) driving a shaft that ends in a blade."""
    stubs(pdf, box, 1)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    circle(pdf, x, y - 8, 4)
    pdf.line(x, y - 4, x, y + 9)
    pdf.line(x - 6, y + 9, x + 6, y + 9)


def tubular_exchanger(pdf: Pen, box: Box) -> None:
    """A circle with a zigzag across it: a heat exchanger (heat passes through the coil)."""
    _round_machine(pdf, box)
    zigzag(pdf, box.x - _R, box.x + _R, box.y, 4.0, 3)


def plate_exchanger(pdf: Pen, box: Box) -> None:
    """A rectangle with parallel plates."""
    stubs(pdf, box, 14)
    tint(pdf, EQUIPMENT_FILL)
    pdf.rect(box.x - 14, box.y - 10, 28, 20, style="DF")
    for offset in (-8, -4, 0, 4, 8):
        pdf.line(box.x + offset, box.y - 10, box.x + offset, box.y + 10)


def spiral_exchanger(pdf: Pen, box: Box) -> None:
    """A circle with a smaller circle in it (the spiral)."""
    _round_machine(pdf, box)
    circle(pdf, box.x, box.y, 5.5, style="D")


def air_cooler(pdf: Pen, box: Box) -> None:
    """A tube bundle with a fan (the circle with a cross) above it."""
    stubs(pdf, box, 17)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    pdf.rect(x - 17, y - 3, 34, 13, style="DF")
    pdf.line(x - 17, y + 2, x + 17, y + 2)
    pdf.line(x - 17, y + 6, x + 17, y + 6)
    circle(pdf, x, y - 9, 5)
    pdf.line(x - 3.5, y - 12.5, x + 3.5, y - 5.5)
    pdf.line(x - 3.5, y - 5.5, x + 3.5, y - 12.5)


def electric_heater(pdf: Pen, box: Box) -> None:
    """A rectangle with a heating element (zigzag)."""
    stubs(pdf, box, 17)
    tint(pdf, EQUIPMENT_FILL)
    pdf.rect(box.x - 17, box.y - 9, 34, 18, style="DF")
    zigzag(pdf, box.x - 13, box.x + 13, box.y, 5.0, 4)


def furnace(pdf: Pen, box: Box) -> None:
    """A fired heater: a box with a coil and a burner flame at the bottom."""
    stubs(pdf, box, 17)
    tint(pdf, EQUIPMENT_FILL)
    x, y = box.x, box.y
    pdf.rect(x - 17, y - 11, 34, 22, style="DF")
    zigzag(pdf, x - 13, x + 13, y - 3, 3.5, 4)
    tint(pdf, INK)
    polygon(pdf, [(x - 4, y + 9), (x + 4, y + 9), (x, y + 2)])


def equipment_box(pdf: Pen, box: Box) -> None:
    """The plain rounded box for an item with no symbol of its own (e.g. `GenericItem`)."""
    stubs(pdf, box, 20)
    tint(pdf, EQUIPMENT_FILL)
    pdf.rect(box.x - 20, box.y - 10, 40, 20, style="DF", round_corners=True, corner_radius=3)


EQUIPMENT_DRAWERS: dict[str, Drawer] = {
    "pump": pump,
    "positive_pump": positive_pump,
    "compressor": compressor,
    "ejector": ejector,
    "vessel": vessel,
    "tank": tank,
    "column": column,
    "scrubber": scrubber,
    "separator": separator,
    "electric_separator": electric_separator,
    "filter": filter_,
    "static_mixer": static_mixer,
    "rotary_mixer": rotary_mixer,
    "agitator": agitator,
    "tubular_exchanger": tubular_exchanger,
    "plate_exchanger": plate_exchanger,
    "spiral_exchanger": spiral_exchanger,
    "air_cooler": air_cooler,
    "electric_heater": electric_heater,
    "furnace": furnace,
    "equipment_box": equipment_box,
}
