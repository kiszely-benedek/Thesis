"""A `SheetGraph` adatszerkezet: egy lap gráfja, a splitter és a connector-vágó közös eleme.

Saját modulban él, mert mind `splitter.py` (particionálás, azonosság-alapú
duplikálás), mind `connectors.py` (off-page connector vágás) használja —
enélkül a kettő körkörösen importálná egymást.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from plantgraph.benchmark.models import OffPageConnector


@dataclass
class SheetGraph:
    """Egy lap gráfja: a rá eső csomópontok/élek, plusz a rajta lévő off-page connectorok listája.

    Sima dataclass, nem Pydantic modell (splitter.md 2. fejezet): a gráf
    topológiáját networkx-nek szánjuk, nem szerializáljuk.
    """

    sheet_id: str
    graph: nx.DiGraph[str]
    connectors: list[OffPageConnector] = field(default_factory=list)
