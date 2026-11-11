"""The readiness checklist: each programmatic item with injected probes (F15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.qa.exp0008 import readiness


def test_part_a_is_missing_or_unfinished(tmp_path: Path) -> None:
    assert readiness.check_prereg_a(tmp_path).status == "FAIL"
    (tmp_path / "PREREG_A.md").write_text("Frozen code commit: <<FILL: sha>>\n", encoding="utf-8")
    check = readiness.check_prereg_a(tmp_path)
    assert check.status == "FAIL" and "<<FILL" in check.detail and "no drawn seeds" in check.detail


def test_the_smoke_evidence_must_exist_and_match_head(tmp_path: Path) -> None:
    assert readiness.check_smoke(None).status == "SKIP"
    assert readiness.check_smoke(tmp_path / "SMOKE_PASSED").status == "FAIL"
    stale = tmp_path / "SMOKE_PASSED"
    stale.write_text("0" * 40 + "\n", encoding="utf-8")
    assert "HEAD is" in readiness.check_smoke(stale).detail


def test_a_smoke_at_an_ancestor_counts_only_while_no_frozen_file_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = tmp_path / "SMOKE_PASSED"
    evidence.write_text("a" * 40, encoding="utf-8")
    monkeypatch.setattr(readiness, "_git", lambda *args: "b" * 40)
    monkeypatch.setattr(readiness, "frozen_changes_since", lambda commit: [])
    assert readiness.check_smoke(evidence).status == "OK"
    monkeypatch.setattr(readiness, "frozen_changes_since", lambda commit: ["src/plantgraph/x.py"])
    check = readiness.check_smoke(evidence)
    assert check.status == "FAIL" and "src/plantgraph/x.py" in check.detail


def test_neo4j_needs_the_plant_database_and_no_leftover_temporary_one() -> None:
    assert readiness.check_neo4j(None).status == "SKIP"
    assert readiness.check_neo4j(lambda: ["neo4j", "system"]).status == "OK"
    leftover = readiness.check_neo4j(lambda: ["neo4j", "e7tune"])
    assert leftover.status == "INFO" and "M0 drops it" in leftover.detail  # not a failure

    def down() -> list[str]:
        raise ConnectionError("no server")

    assert "ConnectionError" in readiness.check_neo4j(down).detail
    assert readiness.check_neo4j(lambda: ["system"]).status == "FAIL"


def test_the_neo4j_home_must_be_set_and_exist(tmp_path: Path) -> None:
    assert readiness.check_neo4j_home(None).status == "FAIL"
    assert readiness.check_neo4j_home(str(tmp_path / "nope")).status == "FAIL"
    assert readiness.check_neo4j_home(str(tmp_path)).status == "OK"


def test_the_balance_check_uses_the_launchers_own_reader() -> None:
    def credits(total: float) -> str:
        return json.dumps({"data": {"total_credits": total, "total_usage": 0}})

    assert readiness.check_balance(None).status == "SKIP"
    assert readiness.check_balance(lambda: credits(45.0)).status == "OK"
    assert readiness.check_balance(lambda: credits(12.0)).status == "FAIL"
    assert readiness.check_balance(lambda: "not json").status == "FAIL"


def test_three_items_are_left_to_a_person() -> None:
    assert {c.status for c in readiness.hand_checks()} == {"HAND"}
    assert len(readiness.hand_checks()) == 3


def test_the_pilot_inputs_are_reported_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    check = readiness.check_inputs(tmp_path / "exp0008")
    assert check.status == "FAIL" and "valves_counts.txt" in check.detail
