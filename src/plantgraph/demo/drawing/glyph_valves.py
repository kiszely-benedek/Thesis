"""ISO-style symbols for valves, check valves and safety devices.

A valve sits on a pipe, so every drawer joins the pipe to a symbol only about 18 pt wide.
A bow-tie (two triangles tip to tip) is the plain valve; the extra mark says what kind.
"""

from __future__ import annotations

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.glyph_kit import (
    INK,
    WHITE,
    Drawer,
    black_dot,
    bow_tie,
    circle,
    polygon,
    stubs,
    tint,
    zigzag,
)
from plantgraph.demo.drawing.glyph_pen import Pen

_HW = 9.0  # half width of the bow-tie
_HH = 6.0  # half height


def _body(pdf: Pen, box: Box) -> None:
    stubs(pdf, box, _HW)
    tint(pdf, WHITE)
    bow_tie(pdf, box.x, box.y, _HW, _HH)


def valve(pdf: Pen, box: Box) -> None:
    """The plain bow-tie: a valve of a kind with no mark of its own (e.g. straightway)."""
    _body(pdf, box)


def gate_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a stem and a handwheel bar (the gate is lifted by the stem)."""
    _body(pdf, box)
    pdf.line(box.x, box.y, box.x, box.y - _HH - 5)
    pdf.line(box.x - 3, box.y - _HH - 5, box.x + 3, box.y - _HH - 5)


def globe_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a black dot at the centre."""
    _body(pdf, box)
    black_dot(pdf, box.x, box.y, 2.3)


def ball_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a white ball (circle) at the centre."""
    _body(pdf, box)
    circle(pdf, box.x, box.y, 3.2)


def butterfly_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with the disc drawn edge-on as a vertical bar."""
    _body(pdf, box)
    pdf.line(box.x, box.y - _HH - 2, box.x, box.y + _HH + 2)


def needle_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a pointed stem on top."""
    _body(pdf, box)
    tint(pdf, INK)
    polygon(
        pdf, [(box.x - 2.5, box.y - _HH - 6), (box.x + 2.5, box.y - _HH - 6), (box.x, box.y - _HH)]
    )
    tint(pdf, WHITE)


def plug_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a black diamond (the plug) at the centre."""
    _body(pdf, box)
    tint(pdf, INK)
    polygon(
        pdf,
        [(box.x, box.y - 3.5), (box.x + 3.5, box.y), (box.x, box.y + 3.5), (box.x - 3.5, box.y)],
    )
    tint(pdf, WHITE)


def angle_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie with a downward arrow: the flow turns 90 degrees through the body."""
    _body(pdf, box)
    pdf.line(box.x, box.y + _HH, box.x, box.y + _HH + 4)
    tint(pdf, INK)
    polygon(
        pdf, [(box.x - 2, box.y + _HH + 3), (box.x + 2, box.y + _HH + 3), (box.x, box.y + _HH + 7)]
    )
    tint(pdf, WHITE)


def check_valve(pdf: Pen, box: Box) -> None:
    """A triangle pointing downstream with a bar at its tip: flow may pass only one way."""
    stubs(pdf, box, 6)
    tint(pdf, WHITE)
    x, y = box.x, box.y
    polygon(pdf, [(x - 6, y - 6), (x - 6, y + 6), (x + 6, y)])
    pdf.line(x + 6, y - 6.5, x + 6, y + 6.5)


def swing_check_valve(pdf: Pen, box: Box) -> None:
    """The check valve with the hinge of its swinging flap marked."""
    check_valve(pdf, box)
    black_dot(pdf, box.x - 6, box.y - 6, 1.4)


def _spring(pdf: Pen, box: Box, height: float) -> None:
    """The safety valve's spring: a zigzag stem above the body, capped by a bar."""
    top = box.y - _HH
    pdf.line(box.x, top, box.x, top - 2)
    x = box.x
    points = [(x, top - 2), (x - 3, top - 4), (x + 3, top - 6), (x - 3, top - 8), (x + 3, top - 10)]
    pdf.polyline(points + [(x, top - height)])
    pdf.line(x - 4, top - height, x + 4, top - height)


def safety_valve(pdf: Pen, box: Box) -> None:
    """Bow-tie body with a spring on top: it lifts when the pressure gets too high."""
    _body(pdf, box)
    _spring(pdf, box, 12)


def breather_valve(pdf: Pen, box: Box) -> None:
    """The safety valve with a vent ring on top: a tank's pressure-vacuum valve."""
    _body(pdf, box)
    pdf.line(box.x, box.y - _HH, box.x, box.y - _HH - 4)
    circle(pdf, box.x, box.y - _HH - 7, 3, style="D")


def rupture_disc(pdf: Pen, box: Box) -> None:
    """Two flanges with a thin curved disc between them (a membrane that bursts)."""
    stubs(pdf, box, 4)
    tint(pdf, WHITE)
    x, y = box.x, box.y
    pdf.line(x - 4, y - 7, x - 4, y + 7)
    pdf.line(x + 4, y - 7, x + 4, y + 7)
    pdf.ellipse(x - 2.5, y - 6, 5, 12, style="D")


def flame_arrestor(pdf: Pen, box: Box) -> None:
    """A square with a fine grid (the element that cools a flame out)."""
    stubs(pdf, box, 7)
    tint(pdf, WHITE)
    x, y = box.x, box.y
    pdf.rect(x - 7, y - 7, 14, 14, style="DF")
    zigzag(pdf, x - 7, x + 7, y, 3.0, 2)


VALVE_DRAWERS: dict[str, Drawer] = {
    "valve": valve,
    "gate_valve": gate_valve,
    "globe_valve": globe_valve,
    "ball_valve": ball_valve,
    "butterfly_valve": butterfly_valve,
    "needle_valve": needle_valve,
    "plug_valve": plug_valve,
    "angle_valve": angle_valve,
    "check_valve": check_valve,
    "swing_check_valve": swing_check_valve,
    "safety_valve": safety_valve,
    "breather_valve": breather_valve,
    "rupture_disc": rupture_disc,
    "flame_arrestor": flame_arrestor,
}
