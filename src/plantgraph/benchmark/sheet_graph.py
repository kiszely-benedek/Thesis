"""The `SheetGraph` data structure: one sheet's graph, shared by the splitter and connector cutter.

Lives in its own module because both `splitter.py` (partitioning, identity-based
duplication) and `connectors.py` (off-page connector cutting — an off-page connector
is the marker a drawing uses to say "this pipe continues on another sheet") use it;
without this split the two would import each other in a circle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from plantgraph.benchmark.models import OffPageConnector


@dataclass
class SheetGraph:
    """One sheet's graph: the nodes/edges that fall on it, plus its list of off-page connectors.

    A plain dataclass, not a Pydantic model (splitter.md section 2): the graph
    topology is meant for networkx, not for serialization.
    """

    sheet_id: str
    graph: nx.DiGraph[str]
    connectors: list[OffPageConnector] = field(default_factory=list)
