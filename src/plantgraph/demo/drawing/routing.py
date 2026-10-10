"""Polylines for the edges: through dummy points for flow edges, along gutters for the rest.

Both kinds only ever run in empty space - in the gutters between columns of boxes and on
horizontal lanes between rows - so no line passes behind a box it does not belong to.
"""

from __future__ import annotations

from dataclasses import dataclass

from plantgraph.demo.drawing.flow_placement import FlowGeometry
from plantgraph.demo.drawing.geometry import Box, Point
from plantgraph.demo.drawing.layering import EdgeChain


@dataclass(frozen=True)
class Terminal:
    """A box together with the two empty vertical channels beside it."""

    box: Box
    left_gutter: float
    right_gutter: float
    lane_y: float  # empty horizontal lane just below the box's row (band cells only)


class BusLanes:
    """Hands out horizontal lanes in the gap between the band and the flow drawing.

    Each line gets its own lane (in turn) so that lines sharing the gap stay tell-apart-able.
    """

    def __init__(self, top: float, height: float, spacing: float = 3.0) -> None:
        self._top = top
        self._count = max(1, int(height / spacing))
        self._spacing = spacing
        self._next = 0

    def next_lane(self) -> float:
        """The y of the next lane."""
        lane = self._top + (self._next % self._count) * self._spacing
        self._next += 1
        return lane


def route_flow_chain(
    chain: EdgeChain, geometry: FlowGeometry, boxes: dict[str, Box]
) -> list[Point]:
    """Polyline of a flow edge, from the source box to the target box, in the true direction.

    Each hop leaves its column horizontally, crosses the gutter on one diagonal and enters the
    next column horizontally; a dummy node is just a point the line passes at its own row.
    """
    path = chain.path
    first, last = boxes[path[0]], boxes[path[-1]]
    points: list[Point] = [(first.right, first.y)]
    for left, right in zip(path, path[1:], strict=False):
        points.append((geometry.zone_right(left), geometry.positions[left][1]))
        points.append((geometry.zone_left(right), geometry.positions[right][1]))
    points.append((last.left, last.y))
    points = _drop_repeats(points)
    return points[::-1] if chain.is_back_edge else points


def route_via_gutters(source: Terminal, target: Terminal, lane_y: float) -> list[Point]:
    """Polyline between two boxes that only uses gutters and one horizontal lane.

    Leave the source sideways into a gutter, run along the gutter to the lane, along the lane
    to the target's gutter, and along that gutter to the target's row.
    """
    source_x, target_x = _closest_gutters(source, target)
    points: list[Point] = [
        (_side_of(source.box, source_x), source.box.y),
        (source_x, source.box.y),
    ]
    if source_x != target_x:
        points += [(source_x, lane_y), (target_x, lane_y)]
    points += [(target_x, target.box.y), (_side_of(target.box, target_x), target.box.y)]
    return _drop_repeats(points)


def _closest_gutters(source: Terminal, target: Terminal) -> tuple[float, float]:
    """The pair of gutters (one per box) that are nearest each other."""
    pairs = [
        (a, b)
        for a in (source.left_gutter, source.right_gutter)
        for b in (target.left_gutter, target.right_gutter)
    ]
    return min(pairs, key=lambda pair: abs(pair[0] - pair[1]))


def _side_of(box: Box, gutter_x: float) -> float:
    """Position (x) of the box edge that faces the gutter."""
    return box.right if gutter_x > box.x else box.left


def _drop_repeats(points: list[Point]) -> list[Point]:
    kept = [points[0]]
    for point in points[1:]:
        if point != kept[-1]:
            kept.append(point)
    return kept
