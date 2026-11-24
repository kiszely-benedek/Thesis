"""The B audit stratum: size, wrong rows first, dedupe, only the two B types."""

from __future__ import annotations

from pathlib import Path

import pytest
from exp0009_small import built_small
from test_records import two_runs

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009 import audit_b
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.v2tb.descriptor import PlantIndex


def _row(qid: str, correct: bool, key: str = "1") -> audit_b.StratumRow:
    return audit_b.StratumRow(run_id="r", question_id=qid, correct=correct, answer_key=key)


def test_size_is_half_the_main_sample_rounded_up() -> None:
    assert audit_b.stratum_size(7) == 4 and audit_b.stratum_size(10) == 5


def test_every_wrong_row_comes_first_then_a_fixed_seed_sample() -> None:
    rows = [_row(f"w{i}", False) for i in range(3)] + [_row(f"r{i}", True) for i in range(20)]
    picked = audit_b.select_stratum(rows, 20)  # size 10
    assert len(picked) == 10 and [p.question_id for p in picked[:3]] == ["w0", "w1", "w2"]
    assert picked == audit_b.select_stratum(rows, 20)
    assert [p.question_id for p in audit_b.select_stratum(rows, 4)] == ["w0", "w1"]  # size 2


def test_candidates_keep_b_types_and_drop_repeated_answers() -> None:
    runs = two_runs()
    questions = {q.question_id: q for q in runs.b_questions}
    rows = RunDir(runs.b_run).read_rows()
    found = audit_b.candidate_rows([*rows, *rows], questions)
    assert found and all(questions[r.question_id].answer_type in audit_b.B_TYPES for r in found)
    assert len({(r.question_id, r.answer_key) for r in found}) == len(found)


def test_the_sheet_shows_what_each_item_resolved_to(tmp_path: Path) -> None:
    spec, corpora, _record = built_small()
    runs = two_runs()
    questions = {q.question_id: q for q in runs.b_questions}
    rows = {r.question_id: r for r in RunDir(runs.b_run).read_rows()}
    plant = load_corpus_artifacts(spec.b_id, corpora / spec.b_id / "ingest.json").gold.plant
    assert plant is not None
    picked = audit_b.candidate_rows(rows.values(), questions)[:2]
    sheet = audit_b.resolution_sheet(PlantIndex(plant), picked, rows, questions)
    assert picked[0].question_id in sheet
    out = tmp_path / "stratum.jsonl"
    audit_b.write_stratum(out, picked)
    with pytest.raises(FileExistsError):
        audit_b.write_stratum(out, picked)
