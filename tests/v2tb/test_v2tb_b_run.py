"""A whole B run on a small real B corpus: positions file, patched view, B scorer (offline)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2
import pytest
from plants_b import real_corpus

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.models import AnswerType, Question, QuestionResult, RunConfig
from plantgraph.qa.questions.scope_x import SCOPE_X_DEV_FAMILIES, scope_x_candidates
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME
from plantgraph.qa.v2tb.runner_b import run_harness_b
from plantgraph.qa.v2tb.store_b import ingest_positions
from qa_agent_fakes import PIN

CORPUS_ID = "SmallB"
_CONFIG = GeneratorConfigV22(seed=1, n_units=8)


@dataclass(frozen=True)
class SmallB:
    corpora_root: Path
    questions_root: Path
    questions: list[Question]


def _build(root: Path) -> SmallB:
    corpora_root, questions_root = root / "corpora", root / "questions"
    result = run_synthetic(
        corpus_id=CORPUS_ID,
        generator_config=_CONFIG,
        split_config=HeadlinePresetV22().split_config(1),
        check=False,
        settings=None,
        store_profile="plant_lines",
    )
    corpus_dir = corpora_root / CORPUS_ID
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "ingest.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    ingest_positions(_CONFIG, corpus_dir)
    corpus = real_corpus()
    planned = dict(positions_of(generate_plant_v2(_CONFIG).plan.unit_plans))
    outcomes = scope_x_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, planned,
        corpus_id=CORPUS_ID, seed=31, families=SCOPE_X_DEV_FAMILIES,
    )  # fmt: skip
    questions = [q for outcome in outcomes.values() for q in outcome.kept[:4]]
    path = questions_path(questions_root, CORPUS_ID)
    path.parent.mkdir(parents=True)
    path.write_bytes("".join(q.model_dump_json() + "\n" for q in questions).encode("utf-8"))
    return SmallB(corpora_root, questions_root, questions)


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> SmallB:
    return _build(tmp_path_factory.mktemp("small-b"))


def _config(small: SmallB) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "b-run",
            "experiment": "TOOLING",
            "reported": False,
            "corpora": [CORPUS_ID],
            "strategies": {"graph_agent_lines_b": {}},
            "answer_pin": PIN,
            "prompt_hashes": prompt_hashes(),
            "question_set_sha256": question_set_sha256(
                [questions_path(small.questions_root, CORPUS_ID)]
            ),
            "primer": True,
            "git_commit": "0" * 40,
            "git_dirty": False,
            "created_at": "2026-11-24T00:00:00",
            "allow_paid_calls": True,
            "max_spend_usd": 100.0,
        }
    )


def _transport(questions: list[Question]) -> httpx2.Client:
    """The model: an agent step says done; a final prompt gets the gold answer of its question."""
    reference_of = {q.text: q.reference for q in questions}

    def handle(request: httpx2.Request) -> httpx2.Response:
        messages: list[dict[str, Any]] = json.loads(request.content)["messages"]
        if messages[0]["role"] == "system":
            return _reply('{"done": true}')
        prompt = messages[0]["content"]
        reference = next(ref for text, ref in reference_of.items() if text in prompt)
        return _reply(json.dumps({"answer": reference, "not_present": False}))

    return httpx2.Client(transport=httpx2.MockTransport(handle))


def _reply(text: str) -> httpx2.Response:
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}
    choice = {"index": 0, "message": {"role": "assistant", "content": text}}
    choice["finish_reason"] = "stop"
    body = {"id": "gen-2", "object": "chat.completion", "created": 0, "model": "m"}
    return httpx2.Response(200, json={**body, "choices": [choice], "usage": usage})


def _run(small: SmallB, tmp_path: Path) -> list[QuestionResult]:
    run_harness_b(
        config=_config(small),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=small.corpora_root,
        questions_root=small.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=_transport(small.questions),
        progress=lambda _m: None,
    )
    lines = (tmp_path / "runs/b-run/answers.jsonl").read_text("utf-8").splitlines()
    return [QuestionResult.model_validate_json(line) for line in lines]


def test_a_b_run_scores_descriptor_and_position_answers_with_the_b_scorer(
    small: SmallB, tmp_path: Path
) -> None:
    rows = _run(small, tmp_path)

    assert len(rows) == len(small.questions)
    kinds = {q.answer_type for q in small.questions}
    assert kinds == {AnswerType.VALVE_SET, AnswerType.POSITION}
    assert all(row.correct for row in rows), [r.question_id for r in rows if not r.correct]
    assert any(
        isinstance(row.final_answer.answer, list)  # type: ignore[union-attr]
        and any(str(item).startswith("{") for item in row.final_answer.answer)  # type: ignore[union-attr]
        for row in rows
    ), "no descriptor answer was exercised"


def test_the_b_loader_needs_the_positions_file(small: SmallB, tmp_path: Path) -> None:
    (small.corpora_root / CORPUS_ID / POSITIONS_FILE_NAME).rename(
        small.corpora_root / CORPUS_ID / "moved.json"
    )
    try:
        with pytest.raises(FileNotFoundError, match="positions file"):
            _run(small, tmp_path)
    finally:
        (small.corpora_root / CORPUS_ID / "moved.json").rename(
            small.corpora_root / CORPUS_ID / POSITIONS_FILE_NAME
        )
