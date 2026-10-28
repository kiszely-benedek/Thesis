"""The client-side wall-clock guard: a source that never answers cannot block a query for ever."""

from __future__ import annotations

import threading

import pytest

from plantgraph.qa.cypher import CypherExecutionError, CypherResult, WriteClauseError
from plantgraph.qa.cypher_guard import HUNG_PREFIX, CypherHung, GuardedCypherSource

_OK = CypherResult(rows=[{"tag": "P-1"}], truncated=False)


class _FakeSource:
    """Answers with `outcome`, or blocks until `close()` when `hang` is set (a dead server)."""

    def __init__(self, outcome: CypherResult | Exception = _OK, *, hang: bool = False) -> None:
        self._outcome = outcome
        self._hang = hang
        self._released = threading.Event()
        self.closed = False
        self.calls: list[tuple[str, float, int]] = []

    def corpus_id(self) -> str:
        return "c"

    def schema_text(self) -> str:
        return "schema"

    def label_names(self) -> frozenset[str]:
        return frozenset({"PlantItem"})

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.calls.append((query, timeout_s, row_cap))
        if self._hang:
            self._released.wait()  # only `close()` lets the "server" go
            raise CypherExecutionError("connection closed")
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    def close(self) -> None:
        self.closed = True
        self._released.set()


def test_a_normal_query_passes_through_with_its_arguments() -> None:
    inner = _FakeSource()

    result = GuardedCypherSource(inner, hang_grace_s=1.0).run_cypher("MATCH (n) RETURN n", 5.0, 7)

    assert result == _OK and inner.calls == [("MATCH (n) RETURN n", 5.0, 7)]
    assert not inner.closed


@pytest.mark.parametrize("error", [WriteClauseError("write"), CypherExecutionError("syntax")])
def test_the_inners_own_errors_are_re_raised_unchanged(error: Exception) -> None:
    guarded = GuardedCypherSource(_FakeSource(error), hang_grace_s=1.0)

    with pytest.raises(type(error)) as raised:
        guarded.run_cypher("q", 5.0, 1)

    assert raised.value is error and not isinstance(raised.value, CypherHung)


def test_a_server_that_ignores_its_timeout_is_cut_off_and_the_connection_closed() -> None:
    inner = _FakeSource(hang=True)
    guarded = GuardedCypherSource(inner, hang_grace_s=0.2)

    with pytest.raises(CypherHung, match=HUNG_PREFIX) as raised:
        guarded.run_cypher("q", 0.1, 1)  # waits 0.3 s, not for ever

    assert inner.closed
    assert "0.3 s" in str(raised.value)
    assert isinstance(raised.value, CypherExecutionError)  # callers catching the base still see it


def test_the_wrapper_delegates_the_rest_of_the_source() -> None:
    inner = _FakeSource()
    guarded = GuardedCypherSource(inner)

    assert guarded.corpus_id() == "c" and guarded.schema_text() == "schema"
    assert guarded.label_names() == frozenset({"PlantItem"})
    guarded.close()
    assert inner.closed


def test_a_non_positive_grace_is_refused() -> None:
    with pytest.raises(ValueError, match="positive hang_grace_s"):
        GuardedCypherSource(_FakeSource(), hang_grace_s=0)
