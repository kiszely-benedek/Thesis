"""Colour refinement: a name for every node that depends only on the structure around it.

Two untagged valves can sit in the same place: same class, same tagged neighbours. What tells them
apart is what hangs off them (a tee, a blind flange, another valve). **Colour refinement** gives
each node a colour and then, round after round, replaces it with a digest of its own colour and the
sorted colours of the nodes flowing into it and out of it. A tagged node starts with its tag, so
its colour is unique and anchors the rest. When a round splits no colour class, the colouring is
stable: two nodes still sharing a colour cannot be told apart by any walk over the flow graph.

The colours depend on tags, classes and flow edges only, never on node ids, so the system's view
and the gold plant, which number their nodes differently, give the same colour to the same place.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence


def refine_colours(initial: Mapping[str, str], flow: Sequence[tuple[str, str]]) -> dict[str, str]:
    """The stable colouring of the nodes in `initial`, starting from their colours there.

    Args:
        initial: node id -> its first colour (a tag, or a class for a node without one).
        flow: `(from, to)` flow edges between nodes of `initial`.

    Raises:
        ValueError: a flow edge touches a node `initial` does not colour.
    """
    into: dict[str, list[str]] = defaultdict(list)
    out_of: dict[str, list[str]] = defaultdict(list)
    for source, target in flow:
        if source not in initial or target not in initial:
            raise ValueError(f"expected both ends of flow edge {(source, target)} to be coloured")
        out_of[source].append(target)
        into[target].append(source)
    colours = dict(initial)
    n_colours = len(set(colours.values()))
    while True:
        refined = {node: _digest(node, colours, into, out_of) for node in colours}
        refined_count = len(set(refined.values()))
        if refined_count == n_colours:  # nothing split: the colouring is stable
            return refined
        colours, n_colours = refined, refined_count


def _digest(
    node: str,
    colours: Mapping[str, str],
    into: Mapping[str, list[str]],
    out_of: Mapping[str, list[str]],
) -> str:
    before = sorted(colours[n] for n in into.get(node, ()))
    after = sorted(colours[n] for n in out_of.get(node, ()))
    text = f"{colours[node]}|<{','.join(before)}|>{','.join(after)}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
