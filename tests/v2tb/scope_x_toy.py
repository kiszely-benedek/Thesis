"""A hand-built one-sheet plant for the scope X tests (not a test module).

Every line is `send_to`; `tee` is a `PipeTee`. Node ids are lower case, tags upper case.

    SRC-1 -> ga -> TK-1                 ga: untagged gate valve, NO
    SRC-2 -> HV-2 -> TK-2               HV-2: tagged gate valve, NC (so TK-2 has nothing to close)
    SRC-3 -> gc -> gd -> TK-3           gc, gd: two untagged gate valves in series, NO
    SRC-5 -> tee -> HV-5A -> join -> TK-5
              tee -> HV-5B -> join      HV-5A is NO, HV-5B is NC
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.v2.plan_models import OperatingPosition

LINE = '6"-P-1203-A1A'

_NODES: list[tuple[str, str, str | None]] = [
    ("src1", "Tank", "SRC-1"),
    ("ga", "GateValve", None),
    ("tk1", "Tank", "TK-1"),
    ("src2", "Tank", "SRC-2"),
    ("hv2", "GateValve", "HV-2"),
    ("tk2", "Tank", "TK-2"),
    ("src3", "Tank", "SRC-3"),
    ("gc", "GateValve", None),
    ("gd", "GateValve", None),
    ("tk3", "Tank", "TK-3"),
    ("src5", "Tank", "SRC-5"),
    ("tee", "PipeTee", None),
    ("hv5a", "GateValve", "HV-5A"),
    ("hv5b", "GateValve", "HV-5B"),
    ("join", "PipeTee", None),
    ("tk5", "Tank", "TK-5"),
]
_CHAINS = [
    ["src1", "ga", "tk1"],
    ["src2", "hv2", "tk2"],
    ["src3", "gc", "gd", "tk3"],
    ["src5", "tee", "hv5a", "join", "tk5"],
    ["tee", "hv5b", "join"],
]

POSITIONS: dict[str, OperatingPosition] = {
    "ga": "NO",
    "hv2": "NC",
    "gc": "NO",
    "gd": "NO",
    "hv5a": "NO",
    "hv5b": "NC",
}


def toy_plant() -> nx.DiGraph[str]:
    """The ground-truth plant."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in _NODES:
        plant.add_node(node_id, node_class=node_class, **({"tag": tag} if tag else {}))
    for chain in _CHAINS:
        for source, target in zip(chain, chain[1:], strict=False):
            plant.add_edge(source, target, relation="send_to", line_number=LINE)
    return plant


def toy_sheets(plant: nx.DiGraph[str]) -> list[SheetGraph]:
    """One sheet holding the whole plant, so no evidence edge crosses a sheet."""
    return [SheetGraph(sheet_id="S1", graph=plant.copy())]


def toy_manifest() -> SplitManifest:
    """A manifest of one sheet and no connector."""
    return SplitManifest(source="scope_x_toy", sheet_files=["S1"])
