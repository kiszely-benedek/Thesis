"""Small drawing helpers shared by the ISO-style glyph modules (fpdf2, page points, y down).

A glyph drawer is a function `(pdf, box) -> None`: it draws one standard symbol centred in `box`
and joins it to the box's left and right edges with short pipe stubs, because the layout's lines
end on those edges. Lines are drawn before symbols, so a symbol's white or tinted fill hides
whatever lies behind it.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.glyph_pen import Pen

Drawer = Callable[[Pen, Box], None]

INK = (0, 0, 0)
WHITE = (255, 255, 255)
EQUIPMENT_FILL = (226, 236, 247)  # a pale blue-grey, so equipment stands out from the pipework
BUBBLE_FILL = (255, 255, 255)


def tint(pdf: Pen, colour: tuple[int, int, int]) -> None:
    """Set the fill colour for the shapes drawn next."""
    pdf.set_fill_color(*colour)


def stubs(pdf: Pen, box: Box, half_width: float) -> None:
    """Pipe stubs from the box's left and right edges to `half_width` either side of the centre."""
    pdf.line(box.left, box.y, box.x - half_width, box.y)
    pdf.line(box.x + half_width, box.y, box.right, box.y)


def circle(pdf: Pen, cx: float, cy: float, radius: float, style: str = "DF") -> None:
    """A circle given by its centre and radius."""
    pdf.circle(cx, cy, radius, style=style)


def polygon(pdf: Pen, points: list[tuple[float, float]], style: str = "DF") -> None:
    """A closed shape through `points`."""
    pdf.polygon(points, style=style)


def zigzag(pdf: Pen, x_from: float, x_to: float, y: float, amplitude: float, teeth: int) -> None:
    """A horizontal zigzag with `teeth` peaks: the sign for a coil, heating element or mixer."""
    step = (x_to - x_from) / (2 * teeth)
    points = [(x_from, y)]
    for index in range(1, 2 * teeth):
        sign = -1 if index % 2 else 1
        points.append((x_from + index * step, y + sign * amplitude))
    points.append((x_to, y))
    pdf.polyline(points)


def wave(pdf: Pen, x_from: float, x_to: float, y: float, amplitude: float) -> None:
    """A sine-like wave, drawn as short segments (a hose)."""
    steps = 16
    points = [
        (
            x_from + (x_to - x_from) * i / steps,
            y + amplitude * math.sin(2 * math.pi * 2 * i / steps),
        )
        for i in range(steps + 1)
    ]
    pdf.polyline(points)


def bow_tie(pdf: Pen, cx: float, cy: float, half_width: float, half_height: float) -> None:
    """The valve body: two triangles meeting tip to tip at the centre."""
    polygon(
        pdf,
        [
            (cx - half_width, cy - half_height),
            (cx + half_width, cy + half_height),
            (cx + half_width, cy - half_height),
            (cx - half_width, cy + half_height),
        ],
    )


def black_dot(pdf: Pen, cx: float, cy: float, radius: float) -> None:
    """A filled black dot; the fill colour is restored to white afterwards."""
    tint(pdf, INK)
    circle(pdf, cx, cy, radius)
    tint(pdf, WHITE)
