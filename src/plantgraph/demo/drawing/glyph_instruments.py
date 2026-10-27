"""ISA instrument bubbles: a circle whose line style says where the instrument is mounted.

ISA 5.1 is the drawing standard for instruments. A bare circle is mounted in the field (next to
the pipe), a circle with a solid line across is on the operator's control-room display, one with a
dashed line is on a local panel. A hexagon is used for the electrical actuating function.
The function letters (`FIC` in `FIC-12014`) are printed by `glyphs_iso`, not here.
"""

from __future__ import annotations

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.glyph_kit import BUBBLE_FILL, Drawer, circle, polygon, stubs, tint
from plantgraph.demo.drawing.glyph_pen import Pen

RADIUS = 11.0


def _bubble(pdf: Pen, box: Box) -> None:
    stubs(pdf, box, RADIUS)
    tint(pdf, BUBBLE_FILL)
    circle(pdf, box.x, box.y, RADIUS)


def field_bubble(pdf: Pen, box: Box) -> None:
    """A bare circle: a field-mounted instrument (a transmitter or gauge by the pipe)."""
    _bubble(pdf, box)


def control_room_bubble(pdf: Pen, box: Box) -> None:
    """A circle with a solid line across: shown on the operator's control-room display."""
    _bubble(pdf, box)
    pdf.line(box.x - RADIUS, box.y, box.x + RADIUS, box.y)


def panel_bubble(pdf: Pen, box: Box) -> None:
    """A circle with a dashed line across: on a local panel (used for the actuating function)."""
    _bubble(pdf, box)
    for start in (-RADIUS, -3.0, 5.0):
        pdf.line(box.x + start, box.y, box.x + start + 4.0, box.y)


def electrical_bubble(pdf: Pen, box: Box) -> None:
    """A hexagon: an electrical actuating function (a motor starter, a solenoid)."""
    stubs(pdf, box, RADIUS)
    tint(pdf, BUBBLE_FILL)
    x, y, h = box.x, box.y, RADIUS * 0.87
    polygon(
        pdf,
        [
            (x - RADIUS, y),
            (x - RADIUS / 2, y - h),
            (x + RADIUS / 2, y - h),
            (x + RADIUS, y),
            (x + RADIUS / 2, y + h),
            (x - RADIUS / 2, y + h),
        ],
    )


def bubble_letters(tag: str) -> tuple[str, str | None]:
    """Split `FIC-12014` into the letters for the bubble and the full tag for under it.

    A tag with no dash goes in the bubble whole and nothing is printed under it.
    """
    letters, dash, _ = tag.partition("-")
    return (letters, tag) if dash else (tag, None)


BUBBLE_DRAWERS: dict[str, Drawer] = {
    "field_bubble": field_bubble,
    "control_room_bubble": control_room_bubble,
    "panel_bubble": panel_bubble,
    "electrical_bubble": electrical_bubble,
}
