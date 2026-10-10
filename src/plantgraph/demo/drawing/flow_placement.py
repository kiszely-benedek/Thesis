"""Coordinates for the pipe-flow drawing: one x per layer, one shared row grid.

Layers are columns of boxes with an empty channel (gutter) between neighbours; long lines and
the lines coming down from the instrument band run in these gutters, so they never cross a box.
The first and last column are as wide as a flag and sit at the canvas edges, which is how
incoming flags end up on the left edge and outgoing flags on the right.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from plantgraph.demo.drawing.geometry import Point
from plantgraph.demo.drawing.layering import LayeredFlow
from plantgraph.demo.drawing.models import LayoutConfig


@dataclass(frozen=True)
class FlowGeometry:
    """Where every real and dummy node of the flow graph sits, and the gutters around columns."""

    positions: dict[str, Point]  # centre of each node, dummies included
    layer_of: dict[str, int]
    column_x: list[float]  # centre of each column
    column_width: list[float]  # width of the widest box in each column
    canvas_width: float

    def zone_left(self, node: str) -> float:
        """Left border of the node's column."""
        layer = self.layer_of[node]
        return self.column_x[layer] - self.column_width[layer] / 2

    def zone_right(self, node: str) -> float:
        """Right border of the node's column."""
        layer = self.layer_of[node]
        return self.column_x[layer] + self.column_width[layer] / 2

    def left_gutter(self, layer: int) -> float:
        """Position (x) of the gutter left of a column (canvas edge for the first)."""
        if layer == 0:
            return 0.0
        return self._gutter_between(layer - 1, layer)

    def right_gutter(self, layer: int) -> float:
        """Position (x) of the gutter right of a column (canvas edge for the last)."""
        if layer == len(self.column_x) - 1:
            return self.canvas_width
        return self._gutter_between(layer, layer + 1)

    def _gutter_between(self, left: int, right: int) -> float:
        left_border = self.column_x[left] + self.column_width[left] / 2
        right_border = self.column_x[right] - self.column_width[right] / 2
        return (left_border + right_border) / 2


def column_widths(
    columns: Sequence[Sequence[str]], widths: Mapping[str, float], config: LayoutConfig
) -> list[float]:
    """Width of each column: its widest box; never narrower than a box, ends as wide as a flag."""
    result = [
        max([config.box_width, *(widths.get(node, 0.0) for node in column)]) for column in columns
    ]
    if result:
        result[0] = result[-1] = max(result[0], result[-1], config.flag_width)
    return result


def width_needed(widths: Sequence[float], config: LayoutConfig) -> float:
    """Canvas width at which the columns just fit with the minimum gutter between them."""
    if not widths:
        return 0.0
    between_columns = sum(_minimum_pitches(widths, config))
    return between_columns + (widths[0] + widths[-1]) / 2 + config.gutter


def rows_needed(columns: Sequence[Sequence[str]]) -> int:
    """Height of the tallest column, in rows (dummy nodes take a row too)."""
    return max((len(column) for column in columns), default=0)


def place_flow(
    layered: LayeredFlow,
    widths: Mapping[str, float],
    config: LayoutConfig,
    canvas_width: float,
    flow_top: float,
    flow_height: float,
) -> FlowGeometry:
    """Assign x to every column and y to every node of the flow graph."""
    column_w = column_widths(layered.columns, widths, config)
    column_x = _column_positions(column_w, config, canvas_width)
    positions: dict[str, Point] = {}
    row_count = rows_needed(layered.columns)
    pitch = min(config.max_row_pitch, flow_height / row_count) if row_count else 0.0
    for x, column in zip(column_x, layered.columns, strict=True):
        # centre a short column on the shared row grid, so rows line up across columns
        first_row = (row_count - len(column)) / 2
        for index, node in enumerate(column):
            positions[node] = (x, flow_top + (first_row + index + 0.5) * pitch)
    return FlowGeometry(positions, layered.layer_of, column_x, column_w, canvas_width)


def _minimum_pitches(widths: Sequence[float], config: LayoutConfig) -> list[float]:
    return [(a + b) / 2 + config.gutter for a, b in zip(widths, widths[1:], strict=False)]


def _column_positions(
    widths: Sequence[float], config: LayoutConfig, canvas_width: float
) -> list[float]:
    """Spread the columns between the two edges; leftover width is shared by all gaps."""
    if not widths:
        return []
    first = widths[0] / 2 + config.gutter / 2
    if len(widths) == 1:
        return [first]
    last = canvas_width - widths[-1] / 2 - config.gutter / 2
    pitches = _minimum_pitches(widths, config)
    extra = ((last - first) - sum(pitches)) / len(pitches)
    positions = [first]
    for pitch in pitches:
        positions.append(positions[-1] + pitch + extra)
    return positions
