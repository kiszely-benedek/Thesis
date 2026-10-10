"""Layered (Sugiyama-style) ordering of the pipe-flow graph: which column, which row order.

Steps, in order: break cycles, give every node a column ("layer") by longest path, put a dummy
node in every column an edge skips, then reorder each column with barycenter sweeps to cut
line crossings. Pure graph code: no coordinates, no knowledge of symbols.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

import networkx as nx

Edge = tuple[str, str]


@dataclass(frozen=True)
class EdgeChain:
    """The columns one edge crosses, left to right, ends included."""

    path: tuple[str, ...]  # real source, dummies, real target - in layering direction
    is_back_edge: bool  # True: the edge really runs right to left; `path` is its reverse


@dataclass(frozen=True)
class LayeredFlow:
    """The result of layering: ordered columns plus one chain per edge."""

    columns: list[list[str]]  # node ids per layer, top to bottom, dummies included
    chains: dict[Edge, EdgeChain]  # keyed by the edge in its true direction
    dummies: frozenset[str]
    layer_of: dict[str, int]


def layer_flow_graph(
    graph: nx.DiGraph[str],
    node_order: Sequence[str],
    push_to_end: Collection[str],
    sweeps: int,
) -> LayeredFlow:
    """Layer `graph` into columns, ordered by barycenter sweeps.

    `node_order` is the starting order inside a column; `push_to_end` lists sinks (flow leaving
    the sheet) that get a column of their own after all others.
    """
    _reject_self_loops(graph)
    back_edges = find_back_edges(graph)
    layer_of = assign_layers(_acyclic_orientation(graph, back_edges), push_to_end)
    chains, dummy_layers = _build_chains(graph, back_edges, layer_of)
    layer_of = {**layer_of, **dummy_layers}
    columns = _initial_columns(node_order, chains, layer_of)
    up, down = _neighbours(chains)
    for _ in range(sweeps):
        _sweep(columns, up, range(1, len(columns)), -1)
        _sweep(columns, down, range(len(columns) - 2, -1, -1), +1)
    return LayeredFlow(columns, chains, frozenset(dummy_layers), layer_of)


def find_back_edges(graph: nx.DiGraph[str]) -> set[Edge]:
    """The edges that close a cycle in a depth-first walk; reversing them makes the graph acyclic.

    One cycle gives exactly one back edge. Insertion order of the graph fixes the walk, so the
    result is deterministic.
    """
    on_stack: set[str] = set()
    back_edges: set[Edge] = set()
    for source, target, label in nx.dfs_labeled_edges(graph):
        if label == "forward":
            on_stack.add(target)
        elif label == "reverse":
            on_stack.discard(target)
        elif target in on_stack:  # "nontree" edge to a node still being explored: closes a cycle
            back_edges.add((source, target))
    return back_edges


def assign_layers(dag: nx.DiGraph[str], push_to_end: Collection[str]) -> dict[str, int]:
    """Longest path from the sources; `push_to_end` sinks get one column past all the others."""
    layer_of: dict[str, int] = {}
    for layer, nodes in enumerate(nx.topological_generations(dag)):
        layer_of.update({node: layer for node in nodes})
    last_sinks = [node for node in push_to_end if node in dag and dag.out_degree(node) == 0]
    others = [layer for node, layer in layer_of.items() if node not in last_sinks]
    end_layer = max(others, default=-1) + 1
    for node in last_sinks:
        layer_of[node] = end_layer
    return layer_of


def _reject_self_loops(graph: nx.DiGraph[str]) -> None:
    loops = sorted(node for node, target in graph.edges if node == target)
    if loops:
        raise ValueError(f"cannot layer a flow edge from a node to itself; found it on {loops}")


def _acyclic_orientation(graph: nx.DiGraph[str], back_edges: set[Edge]) -> nx.DiGraph[str]:
    """Copy of `graph` with every back edge reversed - only used to compute layers."""
    dag: nx.DiGraph[str] = nx.DiGraph()
    dag.add_nodes_from(graph.nodes)
    for source, target in graph.edges:
        if (source, target) in back_edges:
            dag.add_edge(target, source)
        else:
            dag.add_edge(source, target)
    return dag


def _build_chains(
    graph: nx.DiGraph[str], back_edges: set[Edge], layer_of: dict[str, int]
) -> tuple[dict[Edge, EdgeChain], dict[str, int]]:
    """One chain per edge, with a dummy node in each column the edge skips over."""
    chains: dict[Edge, EdgeChain] = {}
    dummy_layers: dict[str, int] = {}
    for source, target in graph.edges:
        is_back = (source, target) in back_edges
        first, last = (target, source) if is_back else (source, target)
        span = layer_of[last] - layer_of[first]
        if span < 1:
            raise ValueError(f"edge {first}->{last} spans {span} layers; expected at least 1")
        dummies = [f"~{source}>{target}#{step}" for step in range(1, span)]
        for step, dummy in enumerate(dummies, start=1):
            dummy_layers[dummy] = layer_of[first] + step
        chains[(source, target)] = EdgeChain((first, *dummies, last), is_back)
    return chains, dummy_layers


def _initial_columns(
    node_order: Sequence[str], chains: dict[Edge, EdgeChain], layer_of: dict[str, int]
) -> list[list[str]]:
    """Real nodes in the given order, then the dummies in edge order."""
    columns: list[list[str]] = [[] for _ in range(max(layer_of.values(), default=-1) + 1)]
    for node in node_order:
        columns[layer_of[node]].append(node)
    for chain in chains.values():
        for dummy in chain.path[1:-1]:
            columns[layer_of[dummy]].append(dummy)
    return columns


def _neighbours(
    chains: dict[Edge, EdgeChain],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """For each node, its neighbours one column to the left (up) and to the right (down)."""
    up: dict[str, list[str]] = {}
    down: dict[str, list[str]] = {}
    for chain in chains.values():
        for left, right in zip(chain.path, chain.path[1:], strict=False):
            down.setdefault(left, []).append(right)
            up.setdefault(right, []).append(left)
    return up, down


def _sweep(
    columns: list[list[str]],
    neighbours: dict[str, list[str]],
    order: Collection[int],
    reference_offset: int,
) -> None:
    """Reorder the columns in `order`, each by the mean position of its neighbours next to it."""
    for index in order:
        reference = columns[index + reference_offset]
        columns[index] = _by_barycenter(columns[index], reference, neighbours)


def _by_barycenter(
    column: list[str], reference: list[str], neighbours: dict[str, list[str]]
) -> list[str]:
    """Sort a column by the mean index of each node's neighbours in `reference`.

    A node with no neighbour there keeps its own index as the sort key, so it does not jump.
    """
    position = {node: index for index, node in enumerate(reference)}

    def sort_key(item: tuple[int, str]) -> tuple[float, int]:
        index, node = item
        indices = [position[n] for n in neighbours.get(node, ()) if n in position]
        return (sum(indices) / len(indices) if indices else float(index), index)

    return [node for _, node in sorted(enumerate(column), key=sort_key)]
