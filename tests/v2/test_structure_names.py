"""Task T6b (design 17.15 S7): colour refinement names a node by the structure around it."""

from __future__ import annotations

import pytest

from plantgraph.qa.exp0009.structure_names import refine_colours


def test_a_node_hanging_off_something_else_gets_another_colour() -> None:
    initial = {"p": "P-1", "a": "valve", "b": "valve", "x": "flange", "y": "tee"}
    colours = refine_colours(initial, [("p", "a"), ("p", "b"), ("a", "x"), ("b", "y")])
    assert colours["a"] != colours["b"]


def test_twins_keep_one_colour() -> None:
    initial = {"p": "P-1", "a": "valve", "b": "valve", "x": "flange", "y": "flange"}
    colours = refine_colours(initial, [("p", "a"), ("p", "b"), ("a", "x"), ("b", "y")])
    assert colours["a"] == colours["b"]


def test_an_edge_to_an_uncoloured_node_raises() -> None:
    with pytest.raises(ValueError, match="coloured"):
        refine_colours({"p": "P-1"}, [("p", "ghost")])
