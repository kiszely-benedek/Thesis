"""Check of TOG309-SPLIT-PAIRING (Toghraei 2019 p.309): the control pairing of a drum split.

In a distillation column the overhead liquid collects in a **reflux drum**; a pump sends part of it
back to the column (the **reflux**) and the rest leaves as **distillate**. At that split one stream
gets flow control and the other holds the drum level. The book puts flow control on the smaller
stream. Which one is smaller depends on the column's **reflux class** (the reflux ratio L/D, low or
high), a design quantity no drawing shows; v2.2 keeps it in `HiddenDesignState.reflux`.

| Reflux class | Reflux stream | Distillate stream |
|---|---|---|
| low (reflux is the smaller stream) | flow control | level control |
| high (distillate is the smaller one) | level control | flow control |

A level valve may be a **cascade**: the level controller sets the set point of a flow controller
that moves the valve. Such a stream still counts as level-controlled, so the check follows the
signals back from each valve to the controllers that drive it.
"""

from __future__ import annotations

from collections import deque

import networkx as nx

from plantgraph.benchmark.v2.hidden_state import RefluxClass
from plantgraph.benchmark.v2.rules.checks_pumps import nodes_with_role
from plantgraph.benchmark.v2.rules.checks_v21_plant import reach
from plantgraph.benchmark.v2.rules.control_graph import FLOW, LEVEL, loop_of
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import Relation

_RULE_ID = "TOG309-SPLIT-PAIRING"
_SPLIT_ROLE = "reflux_split_tee"
_COLUMN = "ProcessColumn"
_SIGNAL_RELATIONS = (Relation.CONTROL.value, Relation.SEND_SIGNAL_TO.value)

#: reflux class -> (what controls the reflux stream, what controls the distillate stream)
_EXPECTED = {
    RefluxClass.LOW: (FLOW, LEVEL),
    RefluxClass.HIGH: (LEVEL, FLOW),
}


def _controlling_variables(graph: nx.DiGraph[str], valve: str) -> set[str]:
    """The measured variables of every controller whose signal leads to `valve` (cascades too)."""
    seen, queue = {valve}, deque([valve])
    variables: set[str] = set()
    while queue:
        for source, _, data in graph.in_edges(queue.popleft(), data=True):
            if data["relation"] not in _SIGNAL_RELATIONS or source in seen:
                continue
            seen.add(source)
            queue.append(source)
            if graph.nodes[source]["node_class"] == "ProcessControlFunction":
                variables.add(str(graph.nodes[source].get("measured_variable", "")))
    return variables


def _stream_control(view: RuleView, parts: set[str]) -> str | None:
    """`LEVEL` if a valve of the stream is level-driven, else `FLOW` if flow-driven, else None."""
    valves = [n for n in sorted(parts) if loop_of(view.graph, n) is not None]
    variables = set().union(*(_controlling_variables(view.graph, v) for v in valves))
    if LEVEL in variables:
        return LEVEL
    return FLOW if FLOW in variables else None


def _split_problem(view: RuleView, split: str) -> str | None:
    piping, graph = view.piping, view.graph
    streams = {}  # first part of each branch -> (parts of the branch, equipment it reaches)
    for first in piping.successors(split):
        parts, equipment = reach(piping, graph, first, up=False)
        streams[first] = ({first, *parts}, equipment)
    columns = {
        first: [e for e in eq if graph.nodes[e]["node_class"] == _COLUMN]
        for first, (_, eq) in streams.items()
    }
    to_column = [first for first, found in columns.items() if found]
    away = [first for first in streams if first not in to_column]
    if len(to_column) != 1 or len(away) != 1:
        return (
            "expected one stream to the column and one leaving, "
            f"found {len(to_column)} and {len(away)}"
        )
    column = columns[to_column[0]][0]
    reflux_class = view.hidden.reflux.get(column)
    if reflux_class is None:
        return f"expected a hidden reflux class for column {column}, found none"
    expected = _EXPECTED[reflux_class]
    found = (
        _stream_control(view, streams[to_column[0]][0]),
        _stream_control(view, streams[away[0]][0]),
    )
    if found != expected:
        return (
            f"expected (reflux, distillate) control {expected} for a {reflux_class.value} reflux "
            f"class, found {found}"
        )
    return None


def check_split_pairing(view: RuleView) -> CheckResult:
    """TOG309-SPLIT-PAIRING: the reflux class decides which stream of the drum split holds level."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    # rule TOG309-SPLIT-PAIRING: flow on the smaller stream, level on the other (Toghraei p.309)
    splits = nodes_with_role(view, view.graph.nodes, [_SPLIT_ROLE])
    violations = [
        Violation(rule_id=_RULE_ID, node_id=split, detail=problem)
        for split in splits
        if (problem := _split_problem(view, split))
    ]
    return CheckResult(checked=len(splits), violations=tuple(violations))
