"""Plain 2-D geometry for the layout: boxes, overlap and segment-versus-box tests."""

from __future__ import annotations

from itertools import combinations
from typing import NamedTuple

from plantgraph.demo.drawing.models import PlacedSymbol, SheetLayout

Point = tuple[float, float]


class Box(NamedTuple):
    """An axis-aligned rectangle given by its centre and size."""

    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        """Edge coordinate."""
        return self.x - self.width / 2

    @property
    def right(self) -> float:
        """Edge coordinate."""
        return self.x + self.width / 2

    @property
    def top(self) -> float:
        """Edge coordinate."""
        return self.y - self.height / 2

    @property
    def bottom(self) -> float:
        """Edge coordinate."""
        return self.y + self.height / 2


def symbol_box(symbol: PlacedSymbol) -> Box:
    """The rectangle a placed symbol occupies."""
    return Box(symbol.x, symbol.y, symbol.width, symbol.height)


def boxes_overlap(a: Box, b: Box) -> bool:
    """True if the interiors intersect (boxes that only touch do not overlap)."""
    return a.left < b.right and b.left < a.right and a.top < b.bottom and b.top < a.bottom


def segment_hits_box(start: Point, end: Point, box: Box) -> bool:
    """True if the segment touches the closed rectangle (Liang-Barsky clipping)."""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    sides = (
        (-delta_x, start[0] - box.left),
        (delta_x, box.right - start[0]),
        (-delta_y, start[1] - box.top),
        (delta_y, box.bottom - start[1]),
    )
    visible = (0.0, 1.0)  # the part of the segment, as a fraction, still inside so far
    for direction, distance in sides:
        clipped = _clip(visible, direction, distance)
        if clipped is None:
            return False
        visible = clipped
    return True


def _clip(
    visible: tuple[float, float], direction: float, distance: float
) -> tuple[float, float] | None:
    """Narrow `visible` by one side of the rectangle; None if nothing is left."""
    first, last = visible
    if direction == 0:
        return None if distance < 0 else visible  # parallel to this side: inside or outside
    fraction = distance / direction
    if direction < 0:
        first = max(first, fraction)
    else:
        last = min(last, fraction)
    return None if first > last else (first, last)


def count_overlaps(layout: SheetLayout) -> int:
    """Number of symbol pairs whose boxes overlap (a correct layout has none)."""
    boxes = [symbol_box(symbol) for symbol in layout.symbols]
    return sum(boxes_overlap(a, b) for a, b in combinations(boxes, 2))


def count_foreign_crossings(layout: SheetLayout) -> int:
    """Number of (segment, symbol) pairs where a line runs through a symbol it does not join."""
    boxes = {symbol.node_id: symbol_box(symbol) for symbol in layout.symbols}
    return sum(
        _line_crossings(line.points, boxes, (line.source, line.target)) for line in layout.lines
    )


def _line_crossings(
    points: tuple[Point, ...], boxes: dict[str, Box], own_ends: tuple[str, str]
) -> int:
    foreign = [box for node_id, box in boxes.items() if node_id not in own_ends]
    segments = zip(points, points[1:], strict=False)
    return sum(segment_hits_box(start, end, box) for start, end in segments for box in foreign)
