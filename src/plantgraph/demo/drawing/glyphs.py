"""Draws one symbol or one line onto a PDF page (fpdf2).

Each symbol family has one glyph; the text printed in it is real PDF text, so a viewer's
search finds it. Text sizes shrink with the sheet's `scale` but never below `MIN_TEXT_PT`.
Everything is drawn in page points, origin top-left, y down - the layout's own coordinates.
"""

from __future__ import annotations

import math

from fpdf import FPDF

from plantgraph.demo.drawing.geometry import Box, symbol_box
from plantgraph.demo.drawing.models import PlacedSymbol, RoutedLine

MIN_TEXT_PT = 4.0  # smallest text the renderer prints, however crowded the sheet
BLACK = (0, 0, 0)
BLUE = (0, 70, 200)  # signals
WHITE = (255, 255, 255)
FLAG_FILL = (255, 247, 214)
_SIGNAL_RELATIONS = frozenset({"send_signal_to", "control", "measured_by"})
_BIG_PT = 7.0  # first (most important) label line at scale 1
_SMALL_PT = 5.0  # the other label lines at scale 1


def draw_line(pdf: FPDF, line: RoutedLine, scale: float) -> None:
    """A polyline with an arrowhead at the target; signals are dashed blue, pipes solid black."""
    is_signal = line.relation in _SIGNAL_RELATIONS
    colour = BLUE if is_signal else BLACK
    pdf.set_draw_color(*colour)
    pdf.set_fill_color(*colour)
    pdf.set_line_width(0.8 * max(scale, 0.6))
    if is_signal:
        pdf.set_dash_pattern(dash=3.0, gap=2.0)
    pdf.polyline(list(line.points))
    pdf.set_dash_pattern()  # back to solid
    _arrowhead(pdf, line.points[-2], line.points[-1], scale)
    if line.line_number is not None:
        _line_number(pdf, line, scale)


def _arrowhead(
    pdf: FPDF, previous: tuple[float, float], tip: tuple[float, float], scale: float
) -> None:
    """A filled triangle at `tip`, pointing along the last segment."""
    angle = math.atan2(tip[1] - previous[1], tip[0] - previous[0])
    length, half_width = 6.0 * max(scale, 0.7), 2.5 * max(scale, 0.7)
    back_x, back_y = tip[0] - length * math.cos(angle), tip[1] - length * math.sin(angle)
    side_x, side_y = -math.sin(angle) * half_width, math.cos(angle) * half_width
    pdf.polygon(
        [tip, (back_x + side_x, back_y + side_y), (back_x - side_x, back_y - side_y)], style="F"
    )


def _line_number(pdf: FPDF, line: RoutedLine, scale: float) -> None:
    """The pipe's line number, just beside the source end (on the side the line leaves to)."""
    size = max(MIN_TEXT_PT, _SMALL_PT * scale)
    text = str(line.line_number)
    _set_font(pdf, size, bold=False)
    width = pdf.get_string_width(text)
    start, second = line.points[0], line.points[1]
    x = start[0] + 3 if second[0] >= start[0] else start[0] - 3 - width
    pdf.set_text_color(*(BLUE if line.relation in _SIGNAL_RELATIONS else BLACK))
    pdf.text(x, start[1] - 1.5, text)


def draw_symbol(pdf: FPDF, symbol: PlacedSymbol, scale: float) -> None:
    """Draw the glyph of the symbol's family and print its labels inside."""
    pdf.set_draw_color(*BLACK)
    pdf.set_fill_color(*WHITE)
    pdf.set_text_color(*BLACK)
    pdf.set_line_width(0.8 * max(scale, 0.6))
    box = symbol_box(symbol)
    if symbol.family == "equipment":
        pdf.rect(box.left, box.top, box.width, box.height, style="DF")
        _stack_labels(pdf, symbol, scale)
    elif symbol.family == "valve":
        _valve(pdf, symbol, box, scale)
    elif symbol.family == "instrument":
        _instrument(pdf, symbol, box, scale)
    else:
        _flag(pdf, symbol, box, scale)


def _valve(pdf: FPDF, symbol: PlacedSymbol, box: Box, scale: float) -> None:
    """Bow-tie (two triangles tip to tip) with the tag above and the class name below."""
    pdf.set_fill_color(*WHITE)
    pdf.rect(box.left, box.top, box.width, box.height, style="F")  # hides lines behind the box
    half = 0.2 * box.height
    pdf.set_fill_color(*WHITE)
    pdf.polygon(
        [
            (box.left, box.y - half),
            (box.right, box.y + half),
            (box.right, box.y - half),
            (box.left, box.y + half),
        ],
        style="DF",
    )
    if "Check" in symbol.node_class:
        pdf.line(box.x, box.y - half, box.x, box.y + half)  # check valve: a bar
    labels = symbol.labels
    if labels:
        _centred(pdf, labels[0], box.x, box.y - half - 1.5, _BIG_PT * scale, True, box.width)
    if len(labels) > 1:
        size = max(MIN_TEXT_PT, _SMALL_PT * scale)
        _centred(pdf, labels[1], box.x, box.y + half + 1.5 + 0.75 * size, size, False, box.width)


def _instrument(pdf: FPDF, symbol: PlacedSymbol, box: Box, scale: float) -> None:
    """ISA bubble (an ellipse); the outline style tells the three instrument classes apart."""
    if symbol.node_class == "ProcessInstrumentationFunction":
        pdf.set_line_width(1.6 * max(scale, 0.6))
    elif symbol.node_class == "ActuatingFunction":
        pdf.set_dash_pattern(dash=2.0, gap=1.5)
    pdf.ellipse(box.left, box.top, box.width, box.height, style="DF")
    pdf.set_dash_pattern()
    _stack_labels(pdf, symbol, scale, width=0.72 * box.width)


def _flag(pdf: FPDF, symbol: PlacedSymbol, box: Box, scale: float) -> None:
    """Off-page connector: a rectangle with a point on the right; signal flags are dashed blue."""
    tip = 0.18 * box.width
    if symbol.family == "signal_flag":
        pdf.set_draw_color(*BLUE)
        pdf.set_dash_pattern(dash=3.0, gap=2.0)
    pdf.set_fill_color(*FLAG_FILL)
    pdf.polygon(
        [
            (box.left, box.top),
            (box.right - tip, box.top),
            (box.right, box.y),
            (box.right - tip, box.bottom),
            (box.left, box.bottom),
        ],
        style="DF",
    )
    pdf.set_dash_pattern()
    pdf.set_draw_color(*BLACK)
    _stack_labels(pdf, symbol, scale, centre_x=box.x - tip / 2, width=box.width - tip - 4)


def _stack_labels(
    pdf: FPDF,
    symbol: PlacedSymbol,
    scale: float,
    centre_x: float | None = None,
    width: float | None = None,
) -> None:
    """Print the labels one under the other, evenly spaced over the symbol's height."""
    labels = symbol.labels
    pitch = symbol.height / (len(labels) + 1)
    x = symbol.x if centre_x is None else centre_x
    fit = (symbol.width - 4) if width is None else width
    for index, text in enumerate(labels):
        base = _BIG_PT if index == 0 else _SMALL_PT
        size = max(MIN_TEXT_PT, min(base * scale, 1.1 * pitch))
        baseline = symbol.y - symbol.height / 2 + pitch * (index + 1) + 0.35 * size
        _centred(pdf, text, x, baseline, size, index == 0, fit)


def _centred(
    pdf: FPDF, text: str, x: float, baseline: float, size: float, bold: bool, max_width: float
) -> None:
    """Print `text` centred on x; shrink towards the floor if wider than `max_width`."""
    size = max(MIN_TEXT_PT, size)
    _set_font(pdf, size, bold)
    width = pdf.get_string_width(text)
    if width > max_width and size > MIN_TEXT_PT:
        size = max(MIN_TEXT_PT, size * max_width / width)
        _set_font(pdf, size, bold)
        width = pdf.get_string_width(text)
    pdf.text(x - width / 2, baseline, text)


def _set_font(pdf: FPDF, size: float, bold: bool) -> None:
    pdf.set_font("helvetica", "B" if bold else "", size)
