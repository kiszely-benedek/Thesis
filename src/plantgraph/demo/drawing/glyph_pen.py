"""A pen that draws in glyph coordinates and scales them onto the page.

The layout shrinks a crowded sheet by `scale`, but every glyph is designed at full size (a pump is
22 pt across). `Pen` is given the glyph's *unshrunk* box and shrinks each coordinate about the box
centre, so a glyph drawer never has to know the scale. It offers only what the drawers use, with
fpdf2's own names and argument order.
"""

from __future__ import annotations

from fpdf import FPDF

Point = tuple[float, float]


class Pen:
    """Draws onto an `FPDF` page, scaling coordinates by `scale` about `(cx, cy)`."""

    def __init__(self, pdf: FPDF, cx: float, cy: float, scale: float) -> None:
        self._pdf = pdf
        self._cx = cx
        self._cy = cy
        self._scale = scale

    def _x(self, x: float) -> float:
        return self._cx + (x - self._cx) * self._scale

    def _y(self, y: float) -> float:
        return self._cy + (y - self._cy) * self._scale

    def _point(self, point: Point) -> Point:
        return self._x(point[0]), self._y(point[1])

    @property
    def line_width(self) -> float:
        """The current line width, as set (not scaled again)."""
        return float(self._pdf.line_width)

    def set_line_width(self, width: float) -> None:
        """Set the line width in points."""
        self._pdf.set_line_width(width)

    def set_fill_color(self, red: int, green: int, blue: int) -> None:
        """Set the fill colour."""
        self._pdf.set_fill_color(red, green, blue)

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """A line between two points."""
        self._pdf.line(self._x(x1), self._y(y1), self._x(x2), self._y(y2))

    def polyline(self, points: list[Point]) -> None:
        """An open line through the points."""
        self._pdf.polyline([self._point(p) for p in points])

    def polygon(self, points: list[Point], style: str = "DF") -> None:
        """A closed shape through the points."""
        self._pdf.polygon([self._point(p) for p in points], style=style)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        style: str = "D",
        round_corners: bool = False,
        corner_radius: float = 0.0,
    ) -> None:
        """A rectangle with top-left corner (x, y), optionally rounded."""
        self._pdf.rect(
            self._x(x),
            self._y(y),
            w * self._scale,
            h * self._scale,
            style=style,
            round_corners=round_corners,
            corner_radius=corner_radius * self._scale,
        )

    def ellipse(self, x: float, y: float, w: float, h: float, style: str = "D") -> None:
        """An ellipse inside the box whose top-left corner is (x, y)."""
        self._pdf.ellipse(self._x(x), self._y(y), w * self._scale, h * self._scale, style=style)

    def circle(self, cx: float, cy: float, radius: float, style: str = "DF") -> None:
        """A circle by centre and radius."""
        self._pdf.circle(self._x(cx), self._y(cy), radius * self._scale, style=style)
