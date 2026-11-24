"""The measurement record: a complete run passes, a damaged one fails, a re-score reproduces."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest
from exp0009_small import built_small, gold_transport

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009 import question_files as qf
from plantgraph.qa.exp0009 import questions as qs
from plantgraph.qa.exp0009 import records
from plantgraph.qa.exp0009.position_baselines import FormPrior
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import AnswerType, Question, RunConfig
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.questions.scope_x_models import NamedBy
from plantgraph.qa.v2tb.runner_b import run_harness_b
from qa_agent_fakes import PIN

RECIPE = qs.Recipe("tiny", 1, 3, 3, 20261101, 2, 0, qs.SCOPE_X_DEV_FAMILIES)


@dataclass(frozen=True)
class Runs:
    root: Path
    a_run: Path
    b_run: Path
    a_questions: list[Question]
    b_questions: list[Question]


def _config(run_id: str, corpus: str, strategy: str, qroot: Path) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": run_id, "experiment": "TOOLING", "reported": False, "corpora": [corpus],
            "strategies": {strategy: {}}, "answer_pin": PIN, "prompt_hashes": prompt_hashes(),
            "question_set_sha256": question_set_sha256([questions_path(qroot, corpus)]),
            "primer": True, "git_commit": "0" * 40, "git_dirty": False,
            "created_at": "2026-11-24T00:00:00", "allow_paid_calls": True, "max_spend_usd": 100.0,
        }
    )  # fmt: skip


@cache
def two_runs() -> Runs:
    """Both arms on the small plant with a model that answers with the gold."""
    spec, corpora, _record = built_small()
    root = Path(mkdtemp(prefix="exp0009-runs-"))
    artifacts = load_corpus_artifacts(spec.plant_id, corpora / spec.plant_id / "ingest.json")
    pool = qs.pool_step(artifacts, RECIPE)
    drop = qf.DropSet(frozenset(qs.R_UNAVAILABLE), frozenset())
    priors = {f: FormPrior(form=f, key_fields=(), majority="NO", table={}) for f in NamedBy}
    qf.write_plant_files(spec.plant_id, pool, drop, RECIPE, root / "questions", priors)
    a_q = read_questions(root / "questions" / spec.plant_id / "questions.jsonl")[0]
    b_q = read_questions(root / "questions" / spec.b_id / "questions.jsonl")[0]
    qroot = root / "questions"
    run_harness(
        config=_config("a-run", spec.plant_id, "graph_agent_lines", qroot),
        corpus_roles={spec.plant_id: "dev"}, corpora_root=corpora, questions_root=qroot,
        runs_root=root / "runs", cache_path=root / "cache.sqlite", http_client=gold_transport(a_q),
        progress=lambda _m: None,
    )  # fmt: skip
    run_harness_b(
        config=_config("b-run", spec.b_id, "graph_agent_lines_b", qroot),
        corpus_roles={spec.b_id: "dev"}, corpora_root=corpora, questions_root=qroot,
        runs_root=root / "runs", cache_path=root / "cache_b.sqlite",
        http_client=gold_transport(b_q), progress=lambda _m: None,
    )  # fmt: skip
    return Runs(root, root / "runs" / "a-run", root / "runs" / "b-run", a_q, b_q)


def test_both_arms_ran_on_files_holding_x_questions() -> None:
    runs = two_runs()
    assert any(q.answer_type is AnswerType.TAG_SET for q in runs.a_questions)
    assert any(q.answer_type is AnswerType.POSITION for q in runs.b_questions)


def test_a_full_record_passes_for_both_arms() -> None:
    runs = two_runs()
    assert records.check_run_records(runs.a_run) == []
    assert records.check_run_records(runs.b_run) == []
    records.require_complete_records(runs.b_run)


def _copy(src: Path, tmp: Path) -> Path:
    tmp.mkdir()
    for path in src.iterdir():
        (tmp / path.name).write_bytes(path.read_bytes())
    return tmp


def test_a_deleted_call_record_fails_the_check(tmp_path: Path) -> None:
    run = _copy(two_runs().b_run, tmp_path / "run")
    lines = (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])["question_id"]  # drop every call of one answered question
    kept = [x for x in lines if json.loads(x)["question_id"] != first]
    (run / "calls.jsonl").write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert any("no call record" in p for p in records.check_run_records(run))
    with pytest.raises(ValueError, match="complete record"):
        records.require_complete_records(run)


def test_a_blanked_cost_fails_the_check(tmp_path: Path) -> None:
    run = _copy(two_runs().a_run, tmp_path / "run")
    rows = [json.loads(x) for x in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["response"]["cost_usd"] = None
    (run / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert any("cost_usd" in p for p in records.check_run_records(run))


def test_an_empty_timings_file_fails_the_check(tmp_path: Path) -> None:
    run = _copy(two_runs().a_run, tmp_path / "run")
    (run / "timings.jsonl").write_bytes(b"")
    assert any("timings.jsonl" in p for p in records.check_run_records(run))


@pytest.mark.parametrize("arm", ["a", "b"])
def test_rescore_reproduces_correct_and_gives_precision_recall(arm: str) -> None:
    spec, corpora, _record = built_small()
    runs = two_runs()
    if arm == "a":
        corpus, run, questions = spec.plant_id, runs.a_run, runs.a_questions
    else:
        corpus, run, questions = spec.b_id, runs.b_run, runs.b_questions
    inputs = records.inputs_from_corpus(corpus, corpora / corpus / "ingest.json", is_b=arm == "b")
    report = records.rescore(run, {q.question_id: q for q in questions}, inputs)
    assert report.rows and report.mismatches == []
    with_sets = [r for r in report.rows if r.precision is not None and r.recall is not None]
    assert with_sets
    assert all(0.0 <= r.precision <= 1.0 and 0.0 <= r.recall <= 1.0 for r in with_sets)  # type: ignore[operator]
    exact = [r for r in with_sets if r.correct]
    assert all(r.precision == r.recall == 1.0 for r in exact)


@pytest.mark.parametrize("arm", ["a_run", "b_run"])
def test_exp0007_health_runs_on_a_run_that_holds_x_questions(arm: str) -> None:
    from plantgraph.qa.exp0007 import cli

    run = getattr(two_runs(), arm)
    with contextlib.suppress(SystemExit):  # a verdict of "technical fault" exits; it still ran
        cli.main(["health", "--run-dir", str(run), "--kind", "tier"])
