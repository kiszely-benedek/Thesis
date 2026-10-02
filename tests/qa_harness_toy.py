"""A tiny generated corpus, its sampled questions and a run config, shared by the harness tests.

Everything is offline: the corpus comes from the real ingest CLI with
`--no-neo4j`, the questions from the real sampler, and model replies from
`FakeTransport`, which records every request it is asked to serve.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from plantgraph.ingest.__main__ import main as ingest_main
from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatResponse, ModelPin
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.final_answer import render_final_answer_request
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.models import Question, RunConfig
from plantgraph.qa.questions.availability import BinTargets
from plantgraph.qa.questions.cli import build_question_set, write_question_set
from plantgraph.qa.strategies.context_rag import ContextRag

CORPUS_ID = "pytest-harness-toy"

#: Abstains on everything: right for unanswerable questions, wrong for the rest,
#: and a valid reply for every answer type (an abstention needs no answer shape).
ABSTAIN_REPLY = '{"answer": null, "not_present": true}'


@dataclass(frozen=True)
class Toy:
    corpora_root: Path
    questions_root: Path
    questions: list[Question]


def build_toy(root: Path) -> Toy:
    """Generate a 2-unit corpus, then sample a few questions per bin from its ground truth."""
    corpora_root, questions_root = root / "corpora", root / "questions"
    argv = ["synthetic", "--n-units", "2", "--budget", "3", "--seed", "0"]
    argv += ["--corpus-id", CORPUS_ID, "--no-neo4j", "--out", str(corpora_root / CORPUS_ID)]
    with contextlib.redirect_stdout(io.StringIO()):  # the CLI prints the IngestResult
        ingest_main(argv)
    artifacts = load_corpus_artifacts(CORPUS_ID, corpora_root / CORPUS_ID / "ingest.json")
    questions, report = build_question_set(artifacts, BinTargets(per_bin=1, unanswerable=2), seed=0)
    write_question_set(questions_root / CORPUS_ID, questions, report)
    return Toy(corpora_root, questions_root, questions)


def pin() -> ModelPin:
    return ModelPin(
        backend="openrouter",
        model_id="openai/gpt-5-mini",
        route_provider="openai",
        temperature=0.0,
        seed=1,
        max_output_tokens=64,
    )


def make_config(toy: Toy, **overrides: Any) -> RunConfig:
    """A complete, non-reported config for the toy corpus; `overrides` replace fields."""
    fields: dict[str, Any] = {
        "run_id": "toy",
        "experiment": "TOOLING",
        "reported": False,
        "corpora": [CORPUS_ID],
        "strategies": {"context_rag": {}},
        "answer_pin": pin(),
        "prompt_hashes": prompt_hashes(),
        "question_set_sha256": question_set_sha256([questions_path(toy.questions_root, CORPUS_ID)]),
        "context_wall": None,
        "git_commit": "0" * 40,
        "git_dirty": False,
        "created_at": datetime(2026, 10, 2),
        "repeats": 1,
        "allow_paid_calls": False,
    }
    fields.update(overrides)
    return RunConfig.model_validate(fields)


def abstaining_transport(**kwargs: Any) -> FakeTransport:
    return FakeTransport(default_reply=ScriptedReply(text=ABSTAIN_REPLY), **kwargs)


def seed_cache(toy: Toy, cache_path: Path, questions: list[Question]) -> None:
    """Pre-fill the cache with the abstaining reply for `questions`, as a finished call would."""
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    context = ContextRag(
        NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
    )
    reply = ChatResponse(
        text=ABSTAIN_REPLY,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0001,
        latency_s=0.0,
        provider_response_id="seeded",
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 10, 2),
    )
    with SqliteCache(cache_path, "live") as cache:
        for question in questions:
            request = render_final_answer_request(
                pin=pin(),
                context=context.retrieve(question.text).context or "",
                question_text=question.text,
                answer_type=question.answer_type,
            )
            cache.put(request, reply)
