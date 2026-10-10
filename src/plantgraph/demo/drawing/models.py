"""The geometry model of one laid-out sheet: boxes, routed lines and the page settings.

All coordinates are PDF points on the page, origin at the top-left corner, y growing downwards.
The layout knows nothing about PDF; the renderer knows nothing about graphs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

#: What a symbol is drawn as. `*_flag` is an off-page connector: the arrow-shaped marker a
#: drawing uses to say "this pipe (or signal) continues on another sheet".
Family = Literal["equipment", "valve", "instrument", "pipe_flag", "signal_flag"]


class LayoutConfig(BaseModel):
    """Page and symbol sizes (points) and the few knobs of the layout."""

    model_config = ConfigDict(frozen=True)

    page_width: float = 1190.0  # A3 landscape
    page_height: float = 842.0
    margin: float = 24.0
    title_block_height: float = 66.0  # strip under the drawing kept free for title block + legend
    box_width: float = 56.0  # equipment, valve and instrument boxes
    box_height: float = 28.0
    flag_width: float = 76.0
    flag_height: float = 36.0
    gutter: float = 20.0  # empty channel between two columns of boxes; lines run in it
    min_row_pitch: float = 40.0  # below this the whole drawing is scaled down instead
    max_row_pitch: float = 64.0
    band_fraction: float = 0.25  # share of the drawing height for the instrument band (top)
    flow_fraction: float = 0.70  # share for the pipe-flow drawing (bottom); the rest is a gap
    band_rows: int = 4
    sweeps: int = 4  # barycenter sweeps; fixed, so the result is deterministic

    @property
    def region_width(self) -> float:
        """Width of the drawing area inside the margins."""
        return self.page_width - 2 * self.margin

    @property
    def region_height(self) -> float:
        """Height of the drawing area above the title block."""
        return self.page_height - 2 * self.margin - self.title_block_height


class PlacedSymbol(BaseModel):
    """One symbol: its centre (x, y), size and the text lines the renderer prints in it."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    family: Family
    node_class: str
    x: float
    y: float
    width: float
    height: float
    labels: tuple[str, ...]
    target_sheet: str | None = None  # flags only: the sheet the flag points to


class RoutedLine(BaseModel):
    """One edge as a polyline, in its true direction (`points[0]` at the source symbol)."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relation: str
    points: tuple[tuple[float, float], ...]
    line_number: str | None = None
    is_back_edge: bool = False  # flow edge that runs against the left-to-right direction


class SheetLayout(BaseModel):
    """Everything the renderer needs to draw one sheet."""

    model_config = ConfigDict(frozen=True)

    sheet_id: str
    units: tuple[str, ...]
    scale: float  # 1.0 normally; below 1.0 when a crowded sheet was shrunk to fit the page
    symbols: tuple[PlacedSymbol, ...]
    lines: tuple[RoutedLine, ...]


class DrawingReport(BaseModel):
    """What the export drew and how it checked itself (sidecar file and CLI output)."""

    pages: int
    symbols: int  # counted by the renderer while drawing; must equal resolution.n_occurrences
    lines: int  # must equal the edges of the localized sheets
    flags: int  # off-page connectors drawn; must equal resolution.n_connectors
    flags_linked: int  # flags whose target sheet is in the corpus: clickable
    dangling_flags: int  # flags drawn without a link (target sheet missing from the corpus)
    overlaps: int  # pairs of overlapping symbol boxes (must be 0)
    foreign_crossings: int  # (segment, symbol) pairs where a line runs through a foreign symbol
    min_scale: float
    layout_s: float
    render_s: float


class DrawingIndex(BaseModel):
    """The sidecar `drawings.index.json`: which sheet is on which page, and the self-check."""

    corpus_id: str
    pdf_sha256: str
    pages: dict[str, int]  # sheet_id -> 1-based page number
    report: DrawingReport
