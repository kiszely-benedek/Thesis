"""Toy stored runs for the cascade tests: four questions, a Cypher tier and a need tier.

Written to disk exactly the way the harness writes a run, so the join reads real file shapes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.models import CorpusRecord, Outcome, QuestionResult, RunConfig

CORPUS = "T1"
CYPHER = "cypher_rag_plant"
NEED = "hierarchical_need_rules_plant"
TEXTS = {
    "T1:q1": "Can process flow reach E-28-2 from E-10-1?",
    "T1:q2": "What type of item is TK-28-1?",
    "T1:q3": "Which source items ultimately feed V-29-3?",
    "T1:q4": "On which sheets is P-23-1 drawn?",
}
MAX_TOKENS = 100
DEFAULT_LABELS = {"T1:q1": "PATH", "T1:q2": "ITEM", "T1:q3": "UPSTREAM_ALL", "T1:q4": "ITEM"}


def pin(effort: str) -> ModelPin:
    return ModelPin(
        backend="openrouter",
        model_id="toy/model",
        max_output_tokens=MAX_TOKENS,
        extra={"reasoning": {"effort": effort}},
    )


def cypher_spec() -> TierSpec:
    return TierSpec(
        name="cypher-low",
        strategy=CYPHER,
        pin_sha256=pin("low").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED, AcceptRule.ROWS, AcceptRule.NOT_ABSTAINED}),
    )


def need_spec() -> TierSpec:
    return TierSpec(
        name="need-default",
        strategy=NEED,
        pin_sha256=pin("default").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )


def policy(**fields: Any) -> CascadePolicy:
    return CascadePolicy(name="toy", tiers=(cypher_spec(), need_spec()), **fields)


def write_questions(root: Path, texts: dict[str, str] | None = None) -> Path:
    """Write `<root>/T1/questions.jsonl`; returns `root`."""
    lines = [_question_line(qid, text) for qid, text in (texts or TEXTS).items()]
    path = questions_path(root, CORPUS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("".join(line + "\n" for line in lines).encode("utf-8"))
    return root


def _question_line(question_id: str, text: str) -> str:
    return json.dumps(
        {
            "question_id": question_id,
            "corpus_id": CORPUS,
            "family": "CONNECTED",
            "template_id": "CONNECTED",
            "template_version": "1",
            "text": text,
            "answer_type": "BOOLEAN",
            "answerable": True,
            "reference": "yes",
            "generator_seed": 1,
        }
    )


@dataclass
class ToyRun:
    """Which rows a toy run holds and the setup fields a test may corrupt."""

    run_id: str
    strategy: str
    effort: str
    rows: list[dict[str, Any]]
    source_graph_hash: str = "g" * 64
    primer: bool = True
    prompt_overrides: dict[str, str] | None = None
    repeats: int = 1


def row(question_id: str, strategy: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "r",
        "question_id": question_id,
        "strategy": strategy,
        "repeat": 0,
        "outcome": Outcome.ANSWERED.value,
        "final_answer": {"answer": "yes", "not_present": False},
        "correct": True,
        "f1": None,
        "prompt_tokens": 50,
        "completion_tokens": 10,
        "cost_usd": 0.001,
        "latency_s": 1.0,
        "context_chars": 100,
    }
    base.update(fields)
    return QuestionResult.model_validate(base).model_dump(mode="json")


def cypher_rows() -> list[dict[str, Any]]:
    """q1 accepted; q2 empty result; q3 retrieval error; q4 abstains."""
    usage = {"n_calls": 1, "prompt_tokens": 9, "completion_tokens": 9, "cost_usd": 0.002}
    abstain = {"answer": None, "not_present": True}
    return [
        row("T1:q1", CYPHER, trace={"retrieval": {"n_rows": 2}}, retrieval_usage=usage),
        row("T1:q2", CYPHER, trace={"retrieval": {"n_rows": 0}}, retrieval_usage=usage),
        row("T1:q3", CYPHER, outcome="RETRIEVAL_ERROR", final_answer=None, retrieval_usage=usage),
        row(
            "T1:q4",
            CYPHER,
            final_answer=abstain,
            trace={"retrieval": {"n_rows": 1}},
            retrieval_usage=usage,
        ),
    ]


def need_rows() -> list[dict[str, Any]]:
    """q3 is a parse failure; q4 hits the token cap while still ANSWERED."""
    rows = []
    for question_id, label in DEFAULT_LABELS.items():
        fields: dict[str, Any] = {"trace": {"retrieval": {"need_label": label}}}
        if question_id == "T1:q3":
            fields |= {"outcome": "PARSE_FAILURE", "final_answer": None}
        if question_id in ("T1:q3", "T1:q4"):
            fields["completion_tokens"] = MAX_TOKENS
        rows.append(row(question_id, NEED, **fields))
    return rows


def write_run(runs_root: Path, questions_root: Path, toy: ToyRun) -> Path:
    """Write run_config.json, corpora.json and answers.jsonl; returns the run directory."""
    run_dir = runs_root / toy.run_id
    run_dir.mkdir(parents=True)
    config = RunConfig(
        run_id=toy.run_id,
        experiment="TOOLING",
        reported=False,
        corpora=[CORPUS],
        strategies={toy.strategy: {}},
        answer_pin=pin(toy.effort),
        prompt_hashes=prompt_hashes() | (toy.prompt_overrides or {}),
        question_set_sha256=question_set_sha256([questions_path(questions_root, CORPUS)]),
        primer=toy.primer,
        git_commit="0" * 40,
        git_dirty=False,
        created_at=datetime(2026, 10, 4),
        repeats=toy.repeats,
    )
    (run_dir / "run_config.json").write_text(config.model_dump_json(), encoding="utf-8")
    record = CorpusRecord(
        corpus_id=CORPUS,
        role="dev",
        generator_config=GeneratorConfig(),
        split_config=SplitConfig(),
        n_sheets=1,
        n_store_nodes=1,
        n_connector_pairs_predicted=0,
        n_plant_nodes=1,
        n_plant_edges=0,
        source_graph_hash=toy.source_graph_hash,
        stage_seconds={},
    )
    (run_dir / "corpora.json").write_text("[" + record.model_dump_json() + "]", encoding="utf-8")
    lines = "".join(json.dumps(r) + "\n" for r in toy.rows)
    (run_dir / "answers.jsonl").write_bytes(lines.encode("utf-8"))
    return run_dir
