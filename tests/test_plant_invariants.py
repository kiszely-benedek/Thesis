"""Invariant statements: which profile gets which, their shape, and how the loader judges them.

No database: the loader's check is run against a fake session that answers with a
chosen violation count, so the pass/fail logic is tested without a server. The
queries themselves are run against Neo4j only by `test_plant_layer_integration.py`.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from plantgraph.store.neo4j_loader import _check_invariant
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.plant_invariants import InvariantStatement, invariant_statements
from store_toy_corpus import toy_corpus

_BOTH_IDS = ["INV-1", "INV-2", "INV-3", "INV-4", "INV-5", "INV-6", "INV-7"]
_WRITE_KEYWORDS = re.compile(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP)\b")


def test_occurrence_has_no_invariants() -> None:
    assert invariant_statements("acme", "occurrence") == []


def test_plant_has_only_the_single_layer_invariants() -> None:
    ids = [statement.invariant_id for statement in invariant_statements("acme", "plant")]
    assert ids == ["INV-6", "INV-7"]


def test_both_has_every_invariant_in_order() -> None:
    ids = [statement.invariant_id for statement in invariant_statements("acme", "both")]
    assert ids == _BOTH_IDS


@pytest.mark.parametrize("profile", ["plant", "both"])
def test_every_statement_is_read_only_scoped_to_the_corpus_and_returns_violations(
    profile: str,
) -> None:
    for statement in invariant_statements("acme", profile):  # type: ignore[arg-type]
        assert statement.parameters == {"corpus_id": "acme"}
        assert "$corpus_id" in statement.query
        assert "AS violations" in statement.query
        assert _WRITE_KEYWORDS.search(statement.query) is None, statement.invariant_id


def test_the_topology_invariant_lists_every_topology_relation_and_not_drawn_as() -> None:
    inv_6 = _statement("INV-6")
    for relation in ("send_to", "send_signal_to", "control", "measured_by", "related_to"):
        assert relation in inv_6.query
    assert "drawn_as" not in inv_6.query


@pytest.mark.parametrize(("profile", "count"), [("occurrence", 0), ("plant", 2), ("both", 7)])
def test_the_load_plan_carries_the_invariants_of_its_profile(profile: str, count: int) -> None:
    sheets, resolution = toy_corpus(0.5)
    plan = build_load_plan("acme", sheets, resolution, profile=profile)  # type: ignore[arg-type]
    assert len(plan.invariant_statements) == count


def test_invariants_stay_out_of_the_plan_json() -> None:
    sheets, resolution = toy_corpus(0.0)
    plan = build_load_plan("acme", sheets, resolution, profile="both")
    assert "invariant_statements" not in plan.model_dump()


# --- the loader's verdict, against a fake session -----------------------------------------------


class _FakeRecord:
    def __init__(self, violations: int) -> None:
        self._violations = violations

    def __getitem__(self, key: str) -> int:
        assert key == "violations"
        return self._violations


class _FakeResult:
    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record

    def single(self) -> _FakeRecord | None:
        return self._record


class _FakeTx:
    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record

    def run(self, query: str, parameters: dict[str, object]) -> _FakeResult:
        return _FakeResult(self._record)


class _FakeSession:
    """Answers every read with one fixed record (or none)."""

    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record

    def execute_read(self, work: Callable[[_FakeTx], int]) -> int:
        return work(_FakeTx(self._record))


def _statement(invariant_id: str) -> InvariantStatement:
    statements = invariant_statements("acme", "both")
    return next(s for s in statements if s.invariant_id == invariant_id)


def test_the_loader_accepts_zero_violations() -> None:
    _check_invariant(_FakeSession(_FakeRecord(0)), _statement("INV-1"))  # type: ignore[arg-type]


def test_the_loader_names_the_failing_invariant_and_its_count() -> None:
    with pytest.raises(RuntimeError, match=r"INV-3.*found 4"):
        _check_invariant(_FakeSession(_FakeRecord(4)), _statement("INV-3"))  # type: ignore[arg-type]


def test_the_loader_rejects_a_query_that_returns_no_row() -> None:
    with pytest.raises(RuntimeError, match="INV-2 returned no row"):
        _check_invariant(_FakeSession(None), _statement("INV-2"))  # type: ignore[arg-type]
