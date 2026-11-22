"""TOG73 (no line number on short branch pipes): what the frozen modules do with such a branch.

Design 10 asked T3 to prove the frozen line view handles a branch without a line number, and to
defer the rule if it does not. The result is split:
- the line view folds the same edges with or without line numbers: it never reads them (passes);
- the frozen DEXPI builder refuses a run without a parseable line number, so a v2.2 plant cannot
  be written with an unnumbered branch without editing `adapters/pydexpi_builder_v2_lines.py`,
  which the freeze forbids. TOG73 is therefore DEFERRED in the catalogue.
"""

from __future__ import annotations

import pytest

from plantgraph.adapters.pydexpi_builder_v2_lines import line_list_fields
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.registry import RuleStatus
from plantgraph.graph.line_view import LineEdge, fold_line_edges

# a block valve, a tee, a drain valve on the tee's branch, and the pipe on to a second valve
_CLASSES = {
    "valve-1": "GateValve",
    "tee-1": "PipeTee",
    "drain-valve": "GateValve",
    "valve-2": "GateValve",
}
_TAGS: dict[str, str | None] = {
    "valve-1": "V-1",
    "tee-1": None,
    "drain-valve": "V-2",
    "valve-2": "V-3",
}
_FLOW = [("valve-1", "tee-1"), ("tee-1", "valve-2"), ("tee-1", "drain-valve")]


def test_the_line_view_folds_a_plant_with_unnumbered_branch_pipes_like_any_other() -> None:
    """The fold reads classes, tags and flow edges only; a line number is not an input."""
    edges = fold_line_edges(_CLASSES, _TAGS, _FLOW)
    assert edges == [
        LineEdge(source="valve-1", target="drain-valve", n_fittings=1),
        LineEdge(source="valve-1", target="valve-2", n_fittings=1),
    ]


def test_the_frozen_builder_refuses_a_run_without_a_line_number() -> None:
    with pytest.raises(ValueError, match="expected a line number SIZE-SERVICE"):
        line_list_fields("")


def test_tog73_is_deferred_with_the_reason_in_the_catalogue() -> None:
    rule = rule_by_id("TOG73-UNTAGGED-BRANCH-PIPES")
    assert rule.status is RuleStatus.DEFERRED
    assert rule.check is None
    assert "line_list_fields" in (rule.deferral_reason or "")
