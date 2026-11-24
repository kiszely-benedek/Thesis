"""Each gate passes on a good input and fails on a spoiled one (design §19.12 4)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from exp0009_small import built_small

from plantgraph.qa.exp0009 import gates
from plantgraph.qa.exp0009.scope_x_report import FamilyReport
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME


def test_g0c_rules_pass_then_fail_on_a_violation(tmp_path: Path) -> None:
    spec, root, _record = built_small()
    assert gates.g0c_rules(root / spec.plant_id / "rules.json").passed
    report = json.loads((root / spec.plant_id / "rules.json").read_text(encoding="utf-8"))
    report["rows"][0]["violations"] = 1
    spoiled = tmp_path / "rules.json"
    spoiled.write_text(json.dumps(report), encoding="utf-8")
    result = gates.g0c_rules(spoiled)
    assert not result.passed and "violation" in result.detail


def test_g0c_fails_when_a_fix_is_owed(monkeypatch: pytest.MonkeyPatch) -> None:
    spec, root, _record = built_small()
    monkeypatch.setattr(gates.owed, "OWED_FIXES", {"R1": "T99"})
    assert not gates.g0c_rules(root / spec.plant_id / "rules.json").passed


def test_g0c_validation_passes_on_the_small_plant() -> None:
    spec, _root, _record = built_small()
    assert gates.g0c_validation(spec).passed


def test_g0k_passes_then_fails_on_a_flipped_flag_or_a_sheet_off_by_one() -> None:
    spec, root, _record = built_small()
    ingest = root / spec.plant_id / "ingest.json"
    # the tiny plant is far below the 90-sheet band, so only the flag and total rules are judged
    detail = gates.g0k(spec, ingest).detail
    assert "differ" not in detail and "predicted" not in detail
    flags = tuple(not f for f in spec.document_untagged)
    assert (
        "differ from the plan"
        in gates.g0k(spec.model_copy(update={"document_untagged": flags}), ingest).detail
    )
    off = spec.model_copy(update={"predicted_sheets": spec.predicted_sheets + 1})
    assert "predicted" in gates.g0k(off, ingest).detail


def test_g0g_and_line_view_pass_on_the_built_plant() -> None:
    spec, root, _record = built_small()
    ingest = root / spec.plant_id / "ingest.json"
    assert gates.g0g(ingest, spec.plant_id).passed
    assert not gates.g0g(ingest, "WrongId").passed
    assert gates.line_view(spec.plant_id, ingest).passed


def test_g0b_passes_then_fails_on_a_deleted_position() -> None:
    spec, root, _record = built_small()
    b_dir = root / spec.b_id
    assert gates.g0b_checks(spec.b_id, b_dir, spec).passed
    path = b_dir / POSITIONS_FILE_NAME
    original = path.read_bytes()
    try:
        document = json.loads(original)
        table = document["positions"] if "positions" in document else document
        table.pop(next(iter(table)))
        path.write_text(json.dumps(document), encoding="utf-8")
        assert not gates.g0b_checks(spec.b_id, b_dir, spec).passed
    finally:
        path.write_bytes(original)


def _report(refused: int, candidates: int) -> FamilyReport:
    return FamilyReport(
        family=QuestionFamily.OPEN_VALVES_TO_ISOLATE, candidates=candidates,
        refused_no_descriptor=refused, refused_empty_gold=0, kept=candidates - refused,
        kept_with_untagged_gold=0, kept_discriminating=None, kept_named_by_descriptor=None,
        kept_position_mix={}, refusing_roles={},
    )  # fmt: skip


def test_g0l_fails_at_26_percent_and_passes_at_25() -> None:
    assert gates.g0l({"p": [_report(25, 100)]}).passed
    assert not gates.g0l({"p": [_report(26, 100)]}).passed


def test_g0e_drops_a_family_short_on_any_plant() -> None:
    kept = {"p1": Counter({"A": 50, "B": 12}), "p2": Counter({"A": 40, "B": 9})}
    assert gates.families_below_minimum(kept) == {"B"}
    assert gates.families_below_minimum({"p1": Counter({"A": 10})}) == set()


def test_g1_g1b_g1b2() -> None:
    weak_both = {"p1": {"FLOW_PATH": (4, 10)}, "p2": {"FLOW_PATH": (3, 10)}}
    ok = {"p1": {"FLOW_PATH": (4, 10)}, "p2": {"FLOW_PATH": (8, 10)}}
    assert not gates.g1(weak_both).passed and gates.g1(ok).passed
    assert not gates.g1_b(weak_both).passed and gates.g1_b(ok).passed
    x = "OPEN_VALVES_TO_ISOLATE"
    a2 = {"p1": {"FLOW_PATH": (8, 10)}, "p2": {"FLOW_PATH": (8, 10)}}
    b_fine = {"p1": {"FLOW_PATH": (8, 10), x: (0, 10)}, "p2": {"FLOW_PATH": (7, 10), x: (0, 10)}}
    b_worse = {"p1": {"FLOW_PATH": (6, 10)}, "p2": {"FLOW_PATH": (7, 10)}}
    assert gates.g1_b2(a2, b_fine).passed  # mean -0.05 exactly; X questions do not count
    assert not gates.g1_b2(a2, b_worse).passed


def test_r14f_item_lines_are_exact_on_the_built_b_corpus() -> None:
    spec, root, _record = built_small()
    assert gates.r14f_exactness(spec.b_id, root / spec.b_id).passed
