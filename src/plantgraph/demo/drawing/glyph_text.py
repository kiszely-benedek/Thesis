"""Text printing shared by the classic and ISO glyph modules (fpdf2, helvetica).

Text sizes shrink with the sheet's `scale` but never below `MIN_TEXT_PT`.
"""

from __future__ import annotations

from fpdf import FPDF

MIN_TEXT_PT = 4.0  # smallest text the renderer prints, however crowded the sheet
BIG_PT = 7.0  # first (most important) label line at scale 1
SMALL_PT = 5.0  # the other label lines at scale 1


def centred(
    pdf: FPDF, text: str, x: float, baseline: float, size: float, bold: bool, max_width: float
) -> None:
    """Print `text` centred on x; shrink towards the floor if wider than `max_width`."""
    size = max(MIN_TEXT_PT, size)
    set_font(pdf, size, bold)
    width = pdf.get_string_width(text)
    if width > max_width and size > MIN_TEXT_PT:
        size = max(MIN_TEXT_PT, size * max_width / width)
        set_font(pdf, size, bold)
        width = pdf.get_string_width(text)
    pdf.text(x - width / 2, baseline, text)


def set_font(pdf: FPDF, size: float, bold: bool) -> None:
    """Select helvetica at `size`, bold or regular."""
    pdf.set_font("helvetica", "B" if bold else "", size)
