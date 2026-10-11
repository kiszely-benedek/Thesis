"""The blind sheet hides the arm, the shuffle is seeded, and the tally counts correct / asked."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plantgraph.qa.exp0001.ex01_models import Ex01AnswerRow, Ex01Verdict
from plantgraph.qa.exp0001.ex01_review import (
    KEY_NAME,
    SHEET_NAME,
    build_key,
    load_checklist,
    load_key,
    render_tally,
    tally,
    write_review,
)
from plantgraph.qa.models import Outcome

CHECKLIST = [
    {
        "qid": "CP12",
        "required_tags": ["HV4750.01", "PV4712.02"],
        "ordered": False,
        "forbidden_tags": ["TV4750.03"],
        "required_statements": ["names both valves"],
    },
    {"qid": "CP15", "required_tags": ["P4711", "T4750"], "ordered": True},
]
QUESTIONS = {"CP12": "Which valves?", "CP15": "What is the path?"}


def _row(arm: str, qid: str, repeat: int, text: str | None) -> Ex01AnswerRow:
    fields: dict[str, Any] = {
        "run_id": "r", "qid": qid, "arm": arm, "repeat": repeat,
        "outcome": Outcome.ANSWERED if text else Outcome.TIMED_OUT,
        "answer_text": text, "not_present": False, "cost_usd": 0.001, "latency_s": 1.0,
        "prompt_tokens": 1, "completion_tokens": 1, "context_chars": 1,
    }  # fmt: skip
    return Ex01AnswerRow(**fields)


def _rows() -> list[Ex01AnswerRow]:
    return [
        _row("ctx-high", "CP12", 1, "Close HV4750.01 and PV4712.02."),
        _row("cyp", "CP12", 1, "Close TV4750.03"),
        _row("ctx-high", "CP15", 1, "P4711 -> T4750"),
        _row("cyp", "CP15", 2, None),  # a timeout: no answer text
    ]


def _checklist_file(tmp_path: Path) -> Path:
    path = tmp_path / "ex01_checklist.json"
    path.write_text(json.dumps(CHECKLIST), encoding="utf-8")
    return path


def test_the_shuffle_is_seeded_and_independent_of_row_order(tmp_path: Path) -> None:
    checklist = load_checklist(_checklist_file(tmp_path))
    first = build_key(_rows(), checklist)
    second = build_key(list(reversed(_rows())), checklist)
    assert first == second
    assert [e.blind_id for e in first] == ["B001", "B002", "B003", "B004"]


def test_the_sheet_never_shows_the_arm_or_the_repeat(tmp_path: Path) -> None:
    write_review(tmp_path, _rows(), _checklist_file(tmp_path), QUESTIONS)
    sheet = (tmp_path / SHEET_NAME).read_text(encoding="utf-8")
    for secret in ("ctx-high", "cyp", "repeat", "cascade"):
        assert secret not in sheet
    assert "Which valves?" in sheet and "names both valves" in sheet


def test_an_item_without_an_answer_is_in_the_key_but_not_on_the_sheet(tmp_path: Path) -> None:
    write_review(tmp_path, _rows(), _checklist_file(tmp_path), QUESTIONS)
    key = load_key(tmp_path / KEY_NAME)
    silent = next(e for e in key if e.no_answer)
    assert (silent.arm, silent.qid) == ("cyp", "CP15")
    assert f"## {silent.blind_id}" not in (tmp_path / SHEET_NAME).read_text(encoding="utf-8")


def test_the_tag_check_is_printed_beside_each_answer(tmp_path: Path) -> None:
    key = build_key(_rows(), load_checklist(_checklist_file(tmp_path)))
    by_arm = {(e.arm, e.qid): e for e in key}
    assert by_arm[("ctx-high", "CP12")].tag_hits.missing == []  # type: ignore[union-attr]
    assert by_arm[("cyp", "CP12")].tag_hits.forbidden_present == ["TV4750.03"]  # type: ignore[union-attr]


def _verdicts(key_ids: list[str], qids: list[str], good: set[str]) -> list[Ex01Verdict]:
    return [
        Ex01Verdict(
            blind_id=i, qid=q, verdict="correct" if i in good else "wrong", reason="r", reviewer="x"
        )
        for i, q in zip(key_ids, qids, strict=True)
    ]


def test_the_tally_counts_correct_over_asked_per_arm_and_repeat(tmp_path: Path) -> None:
    key = build_key(_rows(), load_checklist(_checklist_file(tmp_path)))
    answered = [e for e in key if not e.no_answer]
    good = {e.blind_id for e in answered if (e.arm, e.qid) == ("ctx-high", "CP12")}
    verdicts = _verdicts([e.blind_id for e in answered], [e.qid for e in answered], good)
    counts = tally(key, verdicts)
    assert counts["ctx-high"] == {1: (1, 2)}
    assert counts["cyp"] == {1: (0, 1), 2: (0, 1)}  # the timeout is wrong without a verdict
    table = render_tally(counts)
    assert "| ctx-high | 1 / 2 | - |" in table and "| cyp | 0 / 1 | 0 / 1 |" in table


def test_a_missing_or_foreign_verdict_is_an_error(tmp_path: Path) -> None:
    key = build_key(_rows(), load_checklist(_checklist_file(tmp_path)))
    answered = [e for e in key if not e.no_answer]
    with pytest.raises(ValueError, match="missing"):
        tally(key, _verdicts([answered[0].blind_id], [answered[0].qid], set()))
    stranger = [Ex01Verdict(blind_id="B999", qid="CP12", verdict="wrong", reason="", reviewer="x")]
    with pytest.raises(ValueError, match="B999"):
        tally(key, stranger)
    mismatch = _verdicts([e.blind_id for e in answered], ["CP12"] * len(answered), set())
    with pytest.raises(ValueError, match="mismatch"):
        tally(key, mismatch)


def test_the_draft_checklist_on_disk_is_valid_when_present() -> None:
    path = Path("data/runs/exp0001/inputs/ex01_checklist.json")
    if not path.is_file():
        pytest.skip("the draft checklist is local data (git-ignored) and is absent")
    checklist = load_checklist(path)
    assert sorted(checklist) == ["CP11", "CP12", "CP13", "CP14", "CP15"]
    assert checklist["CP13"].ordered and checklist["CP12"].forbidden_tags == ["TV4750.03"]
