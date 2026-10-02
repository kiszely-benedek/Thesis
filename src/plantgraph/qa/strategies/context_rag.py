"""ContextRAG: put the whole corpus in the prompt (`qa-system.md` §7; ADR-0022 S1).

The baseline to beat, not the system. ChatP&ID's best strategy serializes
the entire graph; this does the same with the occurrence graph (one node per
symbol drawn on a sheet) and does no retrieval at all: every question gets
the identical context. At plant scale that context outgrows the model's
context window, which the fit check turns into `DID_NOT_FIT`.
"""

from __future__ import annotations

from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import RetrievalResult
from plantgraph.qa.serialize import serialize_occurrence_graph


class ContextRag:
    """Serializes the whole corpus view once and returns it for every question."""

    name = "context_rag"

    def __init__(self, view: GraphView) -> None:
        self._view = view
        self._context: str | None = None

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Return the whole serialized corpus; `question_text` is deliberately unused."""
        if self._context is None:
            # The corpus never changes between questions, so serialize once;
            # at 1,000 sheets this is the only expensive step.
            self._context = serialize_occurrence_graph(self._view).text
        return RetrievalResult(
            context=self._context,
            failure=None,
            trace={"serializer": "occurrence_graph", "context_chars": len(self._context)},
        )
