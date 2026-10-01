"""`qa.chatpid_qa`: the ChatP&ID question loader, on a 3-row fixture and the real file."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.qa.chatpid_qa import (
    DEFAULT_PATH,
    ChatPidQA,
    file_sha256,
    format_summary,
    load_chatpid_qa,
    summarise,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "chatpid_qa_3rows.jsonl"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_fixture_loads_three_rows() -> None:
    rows = load_chatpid_qa(_FIXTURE)
    assert [row.qid for row in rows] == ["CP01", "CP11", "CP15"]
    assert all(row.checked_by_human is False for row in rows)
    assert all(row.source_page >= 28 for row in rows)


def test_summary_counts_scope_and_task_type() -> None:
    rows = load_chatpid_qa(_FIXTURE)
    summary = summarise(rows, file_sha256(_FIXTURE))
    assert summary.per_scope == {"out_of_scope_datasheet": 1, "scored": 2}
    assert summary.per_task_type == {"Graph Query (Single)": 1, "Path Exploration": 2}
    assert summary.matches_design_counts is False  # 3 rows, not 19
    assert summary.paper_gives_per_question_scores is False
    assert [qid for qid, _ in summary.out_of_scope] == ["CP01"]


def test_format_summary_prints_hash_and_counts() -> None:
    text = format_summary(summarise(load_chatpid_qa(_FIXTURE), "abc123"))
    assert "sha256: abc123" in text
    assert "per scope" in text and "per task type" in text
    assert "paper gives per-question scores: False" in text


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="expected the ChatP&ID question file"):
        load_chatpid_qa(tmp_path / "absent.jsonl")


def test_bad_line_names_the_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"qid": "CP01"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_chatpid_qa(path)


def test_duplicate_qid_is_rejected(tmp_path: Path) -> None:
    first_line = _FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    path = tmp_path / "dup.jsonl"
    path.write_text(first_line + "\n" + first_line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique qids"):
        load_chatpid_qa(path)


def test_invalid_scope_is_rejected() -> None:
    row = load_chatpid_qa(_FIXTURE)[0].model_dump()
    row["scope"] = "maybe"
    with pytest.raises(ValueError):
        ChatPidQA.model_validate(row)


def test_real_file_matches_the_design_counts() -> None:
    path = _REPO_ROOT / DEFAULT_PATH
    if not path.is_file():
        pytest.skip(f"{path} is git-ignored and absent on this machine")
    summary = summarise(load_chatpid_qa(path), file_sha256(path))
    assert summary.row_count == 19
    assert summary.matches_design_counts
    assert all(row.checked_by_human is False for row in load_chatpid_qa(path))
