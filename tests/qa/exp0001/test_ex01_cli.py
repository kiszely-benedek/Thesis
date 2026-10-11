"""The command line: the paid-call guard, the cache-miss exit code, and review then tally."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from exp0001_toy import QIDS, fake_client, make_settings, run

from plantgraph.qa.exp0001.ex01_cli import main
from plantgraph.qa.exp0001.ex01_review import KEY_NAME, SHEET_NAME, VERDICTS_NAME, load_key


def _flags(root: Path) -> list[str]:
    return [
        "--out-dir", str(root / "out"), "--inputs-dir", str(root / "inputs"),
        "--corpora-root", str(root / "corpora"), "--questions", str(root / "qa.jsonl"),
    ]  # fmt: skip


def test_paid_calls_need_a_cap(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="--cap"):
        main(["ex01", "--allow-paid-calls", *_flags(tmp_path)])


def test_without_the_paid_flag_a_cache_miss_exits_with_code_2(tmp_path: Path) -> None:
    make_settings(tmp_path)
    with pytest.raises(SystemExit) as stop:
        main(["ex01", "--arms", "ctx-high", *_flags(tmp_path)])
    assert stop.value.code == 2


def test_review_writes_the_sheet_and_key_then_tally_reads_the_verdicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = make_settings(tmp_path, arms=["ctx-high"], repeats=1)
    run(settings, fake_client()[0])
    checklist = tmp_path / "ex01_checklist.json"
    items = [{"qid": q, "required_tags": ["T4750"], "ordered": False} for q in QIDS]
    checklist.write_text(json.dumps(items), encoding="utf-8")
    out = settings.out_dir
    main(["ex01-review", "--out-dir", str(out), "--questions", str(tmp_path / "qa.jsonl"),
          "--checklist", str(checklist)])  # fmt: skip
    assert (out / SHEET_NAME).is_file()
    verdicts = [
        {
            "blind_id": e.blind_id,
            "qid": e.qid,
            "verdict": "correct",
            "reason": "ok",
            "reviewer": "t",
        }
        for e in load_key(out / KEY_NAME)
    ]
    (out / VERDICTS_NAME).write_text(json.dumps(verdicts), encoding="utf-8")
    main(["ex01-tally", "--out-dir", str(out)])
    assert "| ctx-high | 5 / 5 |" in capsys.readouterr().out
