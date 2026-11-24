"""The two corpus views of a B run: the in-memory graph and the Neo4j schema text (design §10 R5).

Both extend a frozen view and change one thing. The frozen constructors refuse a sheet that carries
`operating_position` (`check_contract`), so the property is added **after** the frozen constructor
has run, from a map of opaque local key -> position code. The map holds no gold: it is keyed by the
local keys every strategy already sees.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.neo4j_view import Neo4jGraphView
from plantgraph.qa.v2tb.schema_text_b import build_schema_text_b
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings

if TYPE_CHECKING:  # a type only: the localized sheets carry no answer key, and nothing is imported
    from plantgraph.benchmark.sheet_graph import SheetGraph


class NetworkxGraphViewB(NetworkxGraphView):
    """The frozen occurrence graph, with `operating_position` on the positioned valves.

    `items()`, `find_by_tag()` and `subgraph()` all read the one graph, so they agree. With an empty
    `positions` map the view is the frozen one.
    """

    def __init__(
        self,
        corpus_id: str,
        localized_sheets: Sequence[SheetGraph],
        resolution: Resolution,
        positions: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(corpus_id, localized_sheets, resolution)
        for local_key, code in (positions or {}).items():
            if local_key not in self._graph:
                raise ValueError(
                    f"expected a positioned valve {local_key!r} in the view; found none"
                )
            self._graph.nodes[local_key][OPERATING_POSITION] = code


class Neo4jGraphViewB(Neo4jGraphView):
    """The frozen Neo4j view, whose schema text also describes `operating_position`.

    The queries, the store check and the read-only session are the frozen ones; the plan it is
    given is the patched one, so `check_store` compares against the same counts.
    """

    def __init__(self, settings: Neo4jSettings, plan: LoadPlan) -> None:
        super().__init__(settings, plan)
        self._schema_text = build_schema_text_b(plan)
