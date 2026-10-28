"""A client-side wall-clock guard around every Cypher execution (QT-0 finding, ADR-0061).

A query carries a server-side *timeout* (the database aborts it after that many seconds). The
shape bench saw one query hang the server for 8.6 hours *despite* its timeout: the server never
answered, so the client waited for ever. This wrapper adds a second, independent limit measured
by the client: the query runs in a worker thread, and if no answer arrives within
`timeout + grace` seconds the connection is closed and the call fails with `CypherHung`.

No `neo4j` import here: the guard works on any `CypherSource`, so it is tested with fakes.
"""

from __future__ import annotations

import threading

from plantgraph.qa.cypher import CypherExecutionError, CypherResult, CypherSource

#: Seconds past the query timeout before the client gives up (same value as the shape bench).
HANG_GRACE_S = 30.0
#: How long `close()` of a hung connection may take before we stop waiting for it.
_CLOSE_WAIT_S = 10.0

HUNG_PREFIX = "hung: server ignored the timeout"


class CypherHung(CypherExecutionError):
    """The server did not answer within the timeout plus the grace; the connection was closed."""


class GuardedCypherSource:
    """Wraps a `CypherSource`; `run_cypher` can no longer block longer than timeout + grace.

    After a hang the inner source is closed. `Neo4jGraphView` reopens its driver on the next
    call, so later queries still work; another source type must do the same or fail loudly.
    """

    def __init__(self, inner: CypherSource, *, hang_grace_s: float = HANG_GRACE_S) -> None:
        if hang_grace_s <= 0:
            raise ValueError(f"expected a positive hang_grace_s, found {hang_grace_s}")
        self._inner = inner
        self._hang_grace_s = hang_grace_s

    def corpus_id(self) -> str:
        """Which corpus the database holds."""
        return self._inner.corpus_id()

    def schema_text(self) -> str:
        """The schema description shown to the Cypher-writing LLM."""
        return self._inner.schema_text()

    def label_names(self) -> frozenset[str]:
        """Every node label the store holds."""
        return self._inner.label_names()

    def close(self) -> None:
        """Release the database connection."""
        self._inner.close()

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        """Run the query in a worker thread; raise `CypherHung` if it outlives the limit.

        Raises:
            CypherHung: no answer within `timeout_s` + grace; the connection was closed.
            Anything the inner `run_cypher` raises (write clause, database error), unchanged.
        """
        limit_s = timeout_s + self._hang_grace_s
        outcome: list[CypherResult | BaseException] = []
        worker = threading.Thread(target=self._run_into, args=(outcome, query, timeout_s, row_cap))
        worker.daemon = True  # a thread stuck on a dead server must not keep the process alive
        worker.start()
        worker.join(limit_s)
        if not outcome:
            self._abandon()
            raise CypherHung(
                f"{HUNG_PREFIX}: no answer after {limit_s:g} s "
                f"(query timeout {timeout_s:g} s + {self._hang_grace_s:g} s grace); "
                "the connection was closed"
            )
        result = outcome[0]
        if isinstance(result, BaseException):
            raise result  # the worker's own failure, re-raised in the caller's thread
        return result

    def _run_into(
        self,
        outcome: list[CypherResult | BaseException],
        query: str,
        timeout_s: float,
        row_cap: int,
    ) -> None:
        try:
            outcome.append(self._inner.run_cypher(query, timeout_s, row_cap))
        except BaseException as error:  # noqa: BLE001 - handed to the caller, which re-raises it
            outcome.append(error)

    def _abandon(self) -> None:
        """Close the stuck connection; closing it makes the blocked worker raise and end."""
        closer = threading.Thread(target=self._inner.close, daemon=True)
        closer.start()
        closer.join(_CLOSE_WAIT_S)  # `close` itself may block on a dead server: stop waiting
