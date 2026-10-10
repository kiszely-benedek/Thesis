"""The instrument band: a grid of cells above the pipe-flow drawing.

Each cell is as wide as its box plus one gutter, so the vertical borders between cells are
empty channels that lines can use. Signal flags fill the cells at the two ends (incoming on the
left, outgoing on the right); instruments fill the cells between, as near as the grid allows
to the flow symbols they are attached to. Row 0 is the row nearest the flow drawing.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from plantgraph.demo.drawing.geometry import Box
from plantgraph.demo.drawing.models import LayoutConfig
from plantgraph.demo.drawing.routing import Terminal


@dataclass(frozen=True)
class BandCounts:
    """How many symbols the band has to hold."""

    instruments: int
    in_flags: int
    out_flags: int


def flag_columns(flag_count: int, config: LayoutConfig) -> int:
    """Cell columns reserved for one side's flags: at least one, so both ends stay reserved."""
    return max(1, math.ceil(flag_count / config.band_rows))


def band_width_needed(counts: BandCounts, config: LayoutConfig) -> float:
    """Canvas width at which flags and instruments fit in the band."""
    flag_cell = config.flag_width + config.gutter
    side_columns = flag_columns(counts.in_flags, config) + flag_columns(counts.out_flags, config)
    instrument_columns = math.ceil(counts.instruments / config.band_rows)
    return side_columns * flag_cell + instrument_columns * (config.box_width + config.gutter)


def desired_x(
    instruments: Sequence[str],
    neighbours: Mapping[str, Collection[str]],
    flow_x: Mapping[str, float],
    default_x: float,
) -> dict[str, float]:
    """Preferred x of each instrument: the mean x of what it is attached to.

    Two passes: the first uses flow symbols, the second lets an instrument that only touches
    other instruments (a controller between a transmitter and a valve) follow them.
    """
    known: dict[str, float] = {}
    for _ in range(2):
        snapshot = dict(known)
        for node in instruments:
            if node not in known:
                known_x = _known_positions(neighbours.get(node, ()), flow_x, snapshot)
                if known_x:
                    known[node] = sum(known_x) / len(known_x)
    return {node: known.get(node, default_x) for node in instruments}


def place_band(
    instruments: Sequence[str],
    in_flags: Sequence[str],
    out_flags: Sequence[str],
    preferred_x: Mapping[str, float],
    canvas_width: float,
    band_bottom: float,
    config: LayoutConfig,
) -> dict[str, Terminal]:
    """A `Terminal` (box, gutters, lane) for every instrument and signal flag."""
    flag_cell = config.flag_width + config.gutter
    left_edge = flag_columns(len(in_flags), config) * flag_cell
    right_edge = canvas_width - flag_columns(len(out_flags), config) * flag_cell
    placed = _place_flags(in_flags, +1, canvas_width, band_bottom, config)
    placed.update(_place_flags(out_flags, -1, canvas_width, band_bottom, config))
    placed.update(
        _place_instruments(instruments, preferred_x, (left_edge, right_edge), band_bottom, config)
    )
    return placed


def _known_positions(
    neighbours: Collection[str], flow_x: Mapping[str, float], known: Mapping[str, float]
) -> list[float]:
    positions = [flow_x[node] for node in sorted(neighbours) if node in flow_x]
    positions += [known[node] for node in sorted(neighbours) if node in known]
    return positions


def _place_flags(
    flags: Sequence[str],
    direction: int,
    canvas_width: float,
    band_bottom: float,
    config: LayoutConfig,
) -> dict[str, Terminal]:
    """Stack flags bottom-up in columns from one canvas edge (+1: left edge, -1: right edge)."""
    cell_width = config.flag_width + config.gutter
    edge = 0.0 if direction > 0 else canvas_width
    terminals: dict[str, Terminal] = {}
    for index, node in enumerate(flags):
        column, row = divmod(index, config.band_rows)
        centre = edge + direction * (column + 0.5) * cell_width
        box_size = (config.flag_width, config.flag_height)
        terminals[node] = _cell(centre, row, cell_width, box_size, band_bottom, config)
    return terminals


def _place_instruments(
    instruments: Sequence[str],
    preferred_x: Mapping[str, float],
    span: tuple[float, float],
    band_bottom: float,
    config: LayoutConfig,
) -> dict[str, Terminal]:
    """Give each instrument, in order of preferred x, the nearest cell that is still free."""
    cell_width = config.box_width + config.gutter
    left_edge, right_edge = span
    count = int((right_edge - left_edge + 1e-6) // cell_width)
    if count * config.band_rows < len(instruments):
        raise ValueError(
            f"band holds {count * config.band_rows} instruments, found {len(instruments)}"
        )
    margin = (right_edge - left_edge - count * cell_width) / 2
    centres = [left_edge + margin + (i + 0.5) * cell_width for i in range(count)]
    used = [0] * count
    terminals: dict[str, Terminal] = {}
    for node in sorted(instruments, key=lambda n: (preferred_x[n], n)):
        free = [i for i in range(count) if used[i] < config.band_rows]
        slot = min(free, key=lambda i: (abs(centres[i] - preferred_x[node]), i))
        box_size = (config.box_width, config.box_height)
        terminals[node] = _cell(
            centres[slot], used[slot], cell_width, box_size, band_bottom, config
        )
        used[slot] += 1
    return terminals


def _cell(
    centre: float,
    row: int,
    cell_width: float,
    box_size: tuple[float, float],
    band_bottom: float,
    config: LayoutConfig,
) -> Terminal:
    pitch = config.min_row_pitch
    row_y = band_bottom - pitch / 2 - row * pitch
    box = Box(centre, row_y, box_size[0], box_size[1])
    return Terminal(box, centre - cell_width / 2, centre + cell_width / 2, row_y + pitch / 2)
