"""Draws one symbol in the ISO style: a standard symbol per kind of item, tag above, class below.

Equipment, valves and inline items get the symbol `glyph_of` names; an instrument is an ISA
bubble (a circle holding the function letters). Off-page flags are not here: both styles draw
them the same way (`glyphs._flag`).
"""

from __future__ import annotations

from fpdf import FPDF

from plantgraph.demo.drawing.geometry import Box, symbol_box
from plantgraph.demo.drawing.glyph_equipment import EQUIPMENT_DRAWERS
from plantgraph.demo.drawing.glyph_families import glyph_of
from plantgraph.demo.drawing.glyph_inline import INLINE_DRAWERS
from plantgraph.demo.drawing.glyph_instruments import BUBBLE_DRAWERS, bubble_letters
from plantgraph.demo.drawing.glyph_kit import INK, WHITE, Drawer
from plantgraph.demo.drawing.glyph_pen import Pen
from plantgraph.demo.drawing.glyph_text import BIG_PT, MIN_TEXT_PT, SMALL_PT, centred
from plantgraph.demo.drawing.glyph_valves import VALVE_DRAWERS
from plantgraph.demo.drawing.models import PlacedSymbol

#: glyph name -> drawer, over every family. A test checks that every class resolves to one.
DRAWERS: dict[str, Drawer] = {
    **EQUIPMENT_DRAWERS,
    **VALVE_DRAWERS,
    **INLINE_DRAWERS,
    **BUBBLE_DRAWERS,
}

#: Items whose class name is not printed: a pipe tee or a spec break is too small to label.
_UNLABELLED = frozenset({"junction", "spec_break"})
#: How far a symbol reaches above / below its centre in points at scale 1, so that the tag and the
#: class name sit just clear of it. Equipment uses half its box (columns are taller).
_REACH_ABOVE_BY_FAMILY = {"valve": 9.0, "fitting": 8.0, "primary_element": 11.0}
_REACH_BELOW_BY_FAMILY = {"valve": 9.0, "fitting": 8.0, "primary_element": 11.0}
#: Glyphs that stick out further than their family's usual reach (stems, springs, roofs, fans).
_REACH_ABOVE_BY_GLYPH = {
    "gate_valve": 12.0,
    "needle_valve": 12.0,
    "safety_valve": 19.0,
    "breather_valve": 16.0,
    "tank": 16.0,
    "air_cooler": 15.0,
    "ejector": 13.0,
    "vent": 12.0,
    "rotameter": 10.0,
}
_REACH_BELOW_BY_GLYPH = {"angle_valve": 13.0}


def draw_iso_symbol(pdf: FPDF, symbol: PlacedSymbol, scale: float) -> None:
    """Draw the symbol's glyph, then its labels."""
    glyph = glyph_of(symbol.node_class)
    drawer = DRAWERS.get(glyph)
    if drawer is None:
        raise KeyError(f"no drawer for glyph {glyph!r} (class {symbol.node_class!r})")
    pdf.set_draw_color(*INK)
    pdf.set_fill_color(*WHITE)
    pdf.set_text_color(*INK)
    pdf.set_line_width(0.8 * max(scale, 0.6))
    box = symbol_box(symbol)
    # the drawer works at full size around the same centre; the pen shrinks it onto the page
    full = Box(box.x, box.y, box.width / scale, box.height / scale)
    drawer(Pen(pdf, box.x, box.y, scale), full)
    if symbol.family == "instrument":
        _bubble_labels(pdf, symbol, box, scale)
    elif glyph not in _UNLABELLED:
        _outside_labels(pdf, symbol, box, scale)


def _outside_labels(pdf: FPDF, symbol: PlacedSymbol, box: Box, scale: float) -> None:
    """The tag (bold) above the symbol and, if there is one, the class name below it."""
    glyph = glyph_of(symbol.node_class)
    default = box.height / 2
    above = _REACH_ABOVE_BY_GLYPH.get(glyph, _REACH_ABOVE_BY_FAMILY.get(symbol.family, 0.0))
    below = _REACH_BELOW_BY_GLYPH.get(glyph, _REACH_BELOW_BY_FAMILY.get(symbol.family, 0.0))
    above_pt = above * scale if above else default
    below_pt = below * scale if below else default
    labels = symbol.labels
    width = 2.2 * box.width
    if len(labels) == 2:  # a tagged item: the tag is the first line, the class name the second
        centred(pdf, labels[0], box.x, box.y - above_pt - 1.5, BIG_PT * scale, True, width)
    size = max(MIN_TEXT_PT, SMALL_PT * scale)
    centred(pdf, labels[-1], box.x, box.y + below_pt + 0.9 * size + 1.0, size, False, width)


def _bubble_labels(pdf: FPDF, symbol: PlacedSymbol, box: Box, scale: float) -> None:
    """Function letters inside the bubble; the full tag, if different, under it."""
    if not symbol.labels:
        return
    letters, full_tag = bubble_letters(symbol.labels[0])
    glyph = glyph_of(symbol.node_class)
    inside_y = box.y + 0.35 * BIG_PT * scale  # centred in a bare (field-mounted) circle
    if glyph in ("control_room_bubble", "panel_bubble"):
        inside_y = box.y - 1.5 * scale  # sits on top of the mounting line
    centred(pdf, letters, box.x, inside_y, BIG_PT * scale, True, 1.4 * 11 * scale)
    if full_tag is not None:
        size = max(MIN_TEXT_PT, SMALL_PT * scale)
        centred(pdf, full_tag, box.x, box.y + (11 + 1) * scale + 0.9 * size, size, False, box.width)
