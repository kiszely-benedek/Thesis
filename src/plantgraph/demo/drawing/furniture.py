"""The page furniture of a drawing sheet: border, title block (bottom right), legend (bottom left).

Real drawings carry these on every sheet; the title block is also what makes "DWG n" searchable.
"""

from __future__ import annotations

from fpdf import FPDF

from plantgraph.demo.drawing.glyphs import BLACK, BLUE, FLAG_FILL, MIN_TEXT_PT, WHITE
from plantgraph.demo.drawing.models import LayoutConfig, SheetLayout

_TITLE_WIDTH = 300.0
_LEGEND_WIDTH = 330.0
_ROW = 13.0  # legend row pitch


def draw_furniture(pdf: FPDF, layout: SheetLayout, corpus_id: str, config: LayoutConfig) -> None:
    """Border, title block and legend of one sheet."""
    pdf.set_draw_color(*BLACK)
    pdf.set_text_color(*BLACK)
    pdf.set_line_width(1.0)
    pdf.rect(
        config.margin - 8,
        config.margin - 8,
        config.page_width - 2 * (config.margin - 8),
        config.page_height - 2 * (config.margin - 8),
    )
    _title_block(pdf, layout, corpus_id, config)
    _legend(pdf, config)


def _title_block(pdf: FPDF, layout: SheetLayout, corpus_id: str, config: LayoutConfig) -> None:
    left = config.page_width - config.margin - _TITLE_WIDTH
    top = config.page_height - config.margin - config.title_block_height + 4
    pdf.set_line_width(0.8)
    pdf.rect(left, top, _TITLE_WIDTH, config.title_block_height - 4)
    units = ", ".join(layout.units) if layout.units else "-"
    n_lines = len(layout.lines)
    rows = [
        (f"DWG {layout.sheet_id}", 16.0, True),
        (f"Corpus {corpus_id}   Units: {units}", 7.0, False),
        (
            f"Symbols: {len(layout.symbols)}   Lines: {n_lines}   Scale: {layout.scale:.2f}",
            7.0,
            False,
        ),
        ("Simplified generated drawing", 7.0, False),
    ]
    y = top + 4
    for text, size, bold in rows:
        y += size + 2
        pdf.set_font("helvetica", "B" if bold else "", size)
        while pdf.get_string_width(text) > _TITLE_WIDTH - 12 and size > MIN_TEXT_PT:
            size -= 0.5
            pdf.set_font("helvetica", "B" if bold else "", size)
        pdf.text(left + 6, y, text)


def _legend(pdf: FPDF, config: LayoutConfig) -> None:
    left = config.margin
    top = config.page_height - config.margin - config.title_block_height + 4
    pdf.set_line_width(0.8)
    pdf.set_draw_color(*BLACK)
    pdf.rect(left, top, _LEGEND_WIDTH, config.title_block_height - 4)
    pdf.set_font("helvetica", "", 6.0)
    pdf.set_text_color(*BLACK)
    rows = (
        "Pipe flow (arrow = direction)",
        "Signal",
        "Off-page connector (FROM / TO DWG n)",
        "Instrument",
    )
    for index, text in enumerate(rows):
        y = top + 10 + index * _ROW
        _legend_sample(pdf, index, left + 6, y)
        pdf.set_text_color(*BLACK)
        pdf.text(left + 44, y + 2, text)


def _legend_sample(pdf: FPDF, index: int, x: float, y: float) -> None:
    pdf.set_draw_color(*BLACK)
    pdf.set_fill_color(*WHITE)
    if index == 0:
        pdf.line(x, y, x + 30, y)
    elif index == 1:
        pdf.set_draw_color(*BLUE)
        pdf.set_dash_pattern(dash=3.0, gap=2.0)
        pdf.line(x, y, x + 30, y)
        pdf.set_dash_pattern()
    elif index == 2:
        pdf.set_fill_color(*FLAG_FILL)
        pdf.polygon(
            [(x, y - 4), (x + 25, y - 4), (x + 30, y), (x + 25, y + 4), (x, y + 4)], style="DF"
        )
    else:
        pdf.ellipse(x + 5, y - 4, 20, 8, style="D")
