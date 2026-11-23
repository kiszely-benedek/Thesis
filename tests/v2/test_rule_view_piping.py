"""`RuleView.piping` is built once per view and equals the piping graph `flow` builds on demand."""

from __future__ import annotations

import networkx as nx
from t9_support import view_v22

from plantgraph.benchmark.v2.rules.checks_v21_plant import flow


def test_piping_is_cached_on_the_view() -> None:
    view = view_v22(1)
    assert view.piping is view.piping


def test_piping_equals_the_flow_graph() -> None:
    view = view_v22(1)
    expected = flow(view.graph)
    assert set(view.piping.edges) == set(expected.edges)
    assert nx.utils.graphs_equal(view.piping, expected)


def test_a_replaced_view_does_not_inherit_the_old_piping() -> None:
    from dataclasses import replace

    view = view_v22(1)
    _ = view.piping  # fill the memo, then swap in an empty graph
    emptied = replace(view, graph=nx.DiGraph())
    assert emptied.piping.number_of_edges() == 0
