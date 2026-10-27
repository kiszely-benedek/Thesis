"""ISO-style symbols for the small items on a pipe that are not valves.

Fittings (reducer, flange, strainer, ...), the pipe tee (a dot), flow meters and the marker
where the pipe specification changes. They are kept small and thin so that they do not compete
with the equipment.
"""

from __future__ import annotations

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.glyph_kit import (
    INK,
    WHITE,
    Drawer,
    black_dot,
    circle,
    polygon,
    stubs,
    tint,
    wave,
    zigzag,
)
from plantgraph.demo.drawing.glyph_pen import Pen


def _plain(pdf: Pen, box: Box, half_width: float) -> None:
    stubs(pdf, box, half_width)
    tint(pdf, WHITE)


# --- junction and spec break ------------------------------------------------------------------


def junction(pdf: Pen, box: Box) -> None:
    """A pipe tee: a dot where a branch joins the line."""
    pdf.line(box.left, box.y, box.right, box.y)
    black_dot(pdf, box.x, box.y, 2.4)


def spec_break(pdf: Pen, box: Box) -> None:
    """A small diamond: the pipe's specification (class) changes here; it is not a part."""
    _plain(pdf, box, 5)
    x, y = box.x, box.y
    polygon(pdf, [(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)])


# --- fittings ---------------------------------------------------------------------------------


def flanges(pdf: Pen, box: Box) -> None:
    """Two short bars: a flanged joint (also the fallback for any fitting)."""
    _plain(pdf, box, 2.5)
    pdf.line(box.x - 2.5, box.y - 5, box.x - 2.5, box.y + 5)
    pdf.line(box.x + 2.5, box.y - 5, box.x + 2.5, box.y + 5)


def reducer(pdf: Pen, box: Box) -> None:
    """A trapezoid: the pipe narrows from left to right."""
    _plain(pdf, box, 8)
    x, y = box.x, box.y
    polygon(pdf, [(x - 8, y - 6), (x + 8, y - 3), (x + 8, y + 3), (x - 8, y + 6)])


def blind_flange(pdf: Pen, box: Box) -> None:
    """A heavy bar that closes the pipe end."""
    _plain(pdf, box, 0)
    thin = pdf.line_width
    pdf.set_line_width(2.5 * thin)
    pdf.line(box.x, box.y - 6, box.x, box.y + 6)
    pdf.set_line_width(thin)


def spectacle_blind(pdf: Pen, box: Box) -> None:
    """Two linked discs, one open (flow passes) and one filled (flow blocked): a figure eight."""
    _plain(pdf, box, 9)
    x, y = box.x, box.y
    circle(pdf, x - 5, y, 4)
    black_dot(pdf, x + 5, y, 4)


def spade(pdf: Pen, box: Box) -> None:
    """A filled thin plate between two flanges: the pipe is blanked off."""
    _plain(pdf, box, 2)
    tint(pdf, INK)
    pdf.rect(box.x - 2, box.y - 6, 4, 12, style="DF")
    tint(pdf, WHITE)


def spacer(pdf: Pen, box: Box) -> None:
    """The same plate drawn hollow: a spacer ring that leaves the pipe open."""
    _plain(pdf, box, 2)
    pdf.rect(box.x - 2, box.y - 6, 4, 12, style="DF")


def strainer(pdf: Pen, box: Box) -> None:
    """A small box with a diagonal screen."""
    _plain(pdf, box, 6)
    x, y = box.x, box.y
    pdf.rect(x - 6, y - 5, 12, 10, style="DF")
    pdf.line(x - 6, y + 5, x + 6, y - 5)


def cone_strainer(pdf: Pen, box: Box) -> None:
    """A cone pointing downstream with two dots (the perforations)."""
    _plain(pdf, box, 6)
    x, y = box.x, box.y
    polygon(pdf, [(x - 6, y - 6), (x - 6, y + 6), (x + 6, y)])
    black_dot(pdf, x - 2, y - 2, 0.7)
    black_dot(pdf, x - 2, y + 2, 0.7)


def restriction_orifice(pdf: Pen, box: Box) -> None:
    """Two bars with a gap at the middle: a plate with a small hole."""
    _plain(pdf, box, 0)
    thin = pdf.line_width
    pdf.set_line_width(2 * thin)
    pdf.line(box.x, box.y - 7, box.x, box.y - 2)
    pdf.line(box.x, box.y + 2, box.x, box.y + 7)
    pdf.set_line_width(thin)


def steam_trap(pdf: Pen, box: Box) -> None:
    """A circle with a small filled triangle: it lets condensate out and keeps steam in."""
    _plain(pdf, box, 5.5)
    x, y = box.x, box.y
    circle(pdf, x, y, 5.5)
    tint(pdf, INK)
    polygon(pdf, [(x - 2.5, y - 2), (x + 2.5, y - 2), (x, y + 2.5)])
    tint(pdf, WHITE)


def sight_glass(pdf: Pen, box: Box) -> None:
    """A circle with a bar across the pipe: a window onto the fluid."""
    _plain(pdf, box, 5.5)
    circle(pdf, box.x, box.y, 5.5)
    pdf.line(box.x, box.y - 5.5, box.x, box.y + 5.5)


def inline_mixer(pdf: Pen, box: Box) -> None:
    """A short pipe section with a zigzag of mixing elements."""
    _plain(pdf, box, 8)
    pdf.rect(box.x - 8, box.y - 5, 16, 10, style="DF")
    zigzag(pdf, box.x - 7, box.x + 7, box.y, 3.0, 3)


def silencer(pdf: Pen, box: Box) -> None:
    """A box with two baffles."""
    _plain(pdf, box, 9)
    pdf.rect(box.x - 9, box.y - 6, 18, 12, style="DF")
    pdf.line(box.x - 3, box.y - 6, box.x - 3, box.y + 6)
    pdf.line(box.x + 3, box.y - 6, box.x + 3, box.y + 6)


def bellows(pdf: Pen, box: Box) -> None:
    """A zigzag between two flanges: an expansion joint that flexes."""
    _plain(pdf, box, 8)
    zigzag(pdf, box.x - 8, box.x + 8, box.y, 5.0, 4)


def hose(pdf: Pen, box: Box) -> None:
    """A wavy line: a flexible hose."""
    _plain(pdf, box, 9)
    wave(pdf, box.x - 9, box.x + 9, box.y, 3.0)


def funnel(pdf: Pen, box: Box) -> None:
    """A funnel open at the top, draining into the line."""
    _plain(pdf, box, 2)
    x, y = box.x, box.y
    polygon(pdf, [(x - 7, y - 8), (x + 7, y - 8), (x + 2, y), (x - 2, y)])


def vent(pdf: Pen, box: Box) -> None:
    """A stem with a hood: an opening to the atmosphere."""
    _plain(pdf, box, 0)
    x, y = box.x, box.y
    pdf.line(x, y, x, y - 6)
    polygon(pdf, [(x - 5, y - 6), (x + 5, y - 6), (x, y - 11)])


def wall(pdf: Pen, box: Box) -> None:
    """A hatched wall that the pipe passes through."""
    _plain(pdf, box, 2)
    pdf.rect(box.x - 2, box.y - 8, 4, 16, style="DF")
    for offset in (-5, 0, 5):
        pdf.line(box.x - 2, box.y + offset + 2, box.x + 2, box.y + offset - 2)


# --- inline primary elements (flow meters) ----------------------------------------------------


def flow_meter(pdf: Pen, box: Box) -> None:
    """A circle on the line: a flow meter of a kind with no symbol of its own."""
    _plain(pdf, box, 6)
    circle(pdf, box.x, box.y, 6)


def orifice_plate(pdf: Pen, box: Box) -> None:
    """A circle crossed by a bar: the orifice plate that makes the pressure drop."""
    flow_meter(pdf, box)
    pdf.line(box.x, box.y - 8, box.x, box.y + 8)


def venturi(pdf: Pen, box: Box) -> None:
    """An hourglass: the pipe narrows and widens again."""
    _plain(pdf, box, 9)
    x, y = box.x, box.y
    polygon(
        pdf,
        [
            (x - 9, y - 6),
            (x, y - 2.5),
            (x + 9, y - 6),
            (x + 9, y + 6),
            (x, y + 2.5),
            (x - 9, y + 6),
        ],
    )


def magnetic_meter(pdf: Pen, box: Box) -> None:
    """A circle with a coil above and below (it measures with a magnetic field)."""
    flow_meter(pdf, box)
    pdf.rect(box.x - 3, box.y - 10, 6, 4, style="D")
    pdf.rect(box.x - 3, box.y + 6, 6, 4, style="D")


def coriolis_meter(pdf: Pen, box: Box) -> None:
    """A circle with a smaller loop inside (the vibrating tube)."""
    flow_meter(pdf, box)
    circle(pdf, box.x, box.y, 2.5, style="D")


def rotameter(pdf: Pen, box: Box) -> None:
    """A tapered tube with a float: the float rises with the flow."""
    _plain(pdf, box, 4)
    x, y = box.x, box.y
    polygon(pdf, [(x - 4, y - 9), (x + 4, y - 9), (x + 1.5, y + 9), (x - 1.5, y + 9)])
    black_dot(pdf, x, y, 1.3)


def displacement_meter(pdf: Pen, box: Box) -> None:
    """A square with a circle: it counts fixed volumes passing through."""
    _plain(pdf, box, 6)
    pdf.rect(box.x - 6, box.y - 6, 12, 12, style="DF")
    circle(pdf, box.x, box.y, 3, style="D")


def turbine_meter(pdf: Pen, box: Box) -> None:
    """A circle with a crossed rotor."""
    flow_meter(pdf, box)
    pdf.line(box.x - 4, box.y - 4, box.x + 4, box.y + 4)
    pdf.line(box.x - 4, box.y + 4, box.x + 4, box.y - 4)


INLINE_DRAWERS: dict[str, Drawer] = {
    "junction": junction,
    "spec_break": spec_break,
    "flanges": flanges,
    "reducer": reducer,
    "blind_flange": blind_flange,
    "spectacle_blind": spectacle_blind,
    "spade": spade,
    "spacer": spacer,
    "strainer": strainer,
    "cone_strainer": cone_strainer,
    "restriction_orifice": restriction_orifice,
    "steam_trap": steam_trap,
    "sight_glass": sight_glass,
    "inline_mixer": inline_mixer,
    "silencer": silencer,
    "bellows": bellows,
    "hose": hose,
    "funnel": funnel,
    "vent": vent,
    "wall": wall,
    "flow_meter": flow_meter,
    "orifice_plate": orifice_plate,
    "venturi": venturi,
    "magnetic_meter": magnetic_meter,
    "coriolis_meter": coriolis_meter,
    "rotameter": rotameter,
    "displacement_meter": displacement_meter,
    "turbine_meter": turbine_meter,
}
