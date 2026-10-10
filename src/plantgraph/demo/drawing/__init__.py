"""Draws the sheets of a corpus: a pure layout step (this package) and, later, a PDF renderer.

A sheet here is one page of a P&ID (piping and instrumentation diagram: the engineering
drawing of a plant's equipment, pipes and instruments). The corpus stores each sheet as a
graph without coordinates; `layout_sheet` invents the coordinates so the sheet can be drawn.
"""

from plantgraph.demo.drawing.layout import layout_sheet
from plantgraph.demo.drawing.models import (
    LayoutConfig,
    PlacedSymbol,
    RoutedLine,
    SheetLayout,
)

__all__ = ["LayoutConfig", "PlacedSymbol", "RoutedLine", "SheetLayout", "layout_sheet"]
