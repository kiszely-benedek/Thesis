"""Toy stored runs for the EXP-0001 report tests, written the way the harness writes a run.

A "size" is a corpus id (H1, H3 ...) with a questions file, an `ingest.json` holding its sheet
count, and run directories for the arms. Everything is offline; no model, no database.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.exp0001.report_models import QuestionScore
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.models import CorpusRecord, Outcome, QuestionResult, RunConfig

CYPHER = "cypher_rag_plant"
AGENT = "graph_agent_low_steps"
CONTEXT = "context_rag"
MAX_TOKENS = 1000


def pin(effort: str) -> ModelPin:
    return ModelPin(
        backend="openrouter",
        model_id="toy/model",
        max_output_tokens=MAX_TOKENS,
        extra={"reasoning": {"effort": effort}},
    )


def luna_pin(effort: str) -> ModelPin:
    """The sealed run's real pin (its hash matches the shipped `always_c_luna` / `agent` tiers)."""
    return ModelPin(
        backend="openrouter",
        model_id="openai/gpt-6-luna",
        route_provider="openai",
        temperature=None,
        seed=0,
        max_output_tokens=16384,
        extra={"reasoning": {"effort": effort}},
    )


def _tier(name: str, strategy: str, effort: str, accept: set[AcceptRule]) -> TierSpec:
    return TierSpec(
        name=name, strategy=strategy, pin_sha256=pin(effort).pin_hash(), accept=frozenset(accept)
    )


def policies() -> dict[str, CascadePolicy]:
    """Toy versions of the five arms' policies (the real ones differ only in the pin hashes)."""
    answered = {AcceptRule.ANSWERED}
    cypher = _tier(
        "cypher", CYPHER, "low", {AcceptRule.ANSWERED, AcceptRule.ROWS, AcceptRule.NOT_ABSTAINED}
    )
    agent = _tier("agent", AGENT, "high", answered)
    return {
        "ctx-high": CascadePolicy(
            name="always_ctx_high", tiers=(_tier("ctx-high", CONTEXT, "high", answered),)
        ),
        "ctx-low": CascadePolicy(
            name="always_ctx_low", tiers=(_tier("ctx-low", CONTEXT, "low", answered),)
        ),
        "cyp": CascadePolicy(name="always_c", tiers=(cypher,)),
        "ag": CascadePolicy(name="always_g", tiers=(agent,)),
        "cascade_v3": CascadePolicy(name="cascade_v3", tiers=(cypher, agent)),
    }


def write_questions(root: Path, corpus_id: str, families: dict[str, str]) -> None:
    """`<root>/<corpus>/questions.jsonl` with one question per (id -> family) entry."""
    lines = [
        json.dumps(
            {
                "question_id": qid,
                "corpus_id": corpus_id,
                "family": family,
                "template_id": family,
                "template_version": "1",
                "text": f"Question {qid}?",
                "answer_type": "BOOLEAN",
                "answerable": True,
                "reference": "yes",
                "generator_seed": 1,
            }
        )
        for qid, family in families.items()
    ]
    path = questions_path(root, corpus_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("".join(line + "\n" for line in lines).encode("utf-8"))


def write_ingest(corpora_root: Path, corpus_id: str, n_sheets: int, n_nodes: int) -> None:
    """The two `ingest.json` fields the report reads."""
    path = corpora_root / corpus_id / "ingest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"n_sheets": n_sheets, "n_nodes": n_nodes}
    path.write_text(json.dumps({"counts": counts}), encoding="utf-8")


def row(qid: str, strategy: str, correct: bool, **fields: Any) -> dict[str, Any]:
    """One answer row: ANSWERED with $0.001 and 1 s unless `fields` say otherwise."""
    base: dict[str, Any] = {
        "run_id": "r",
        "question_id": qid,
        "strategy": strategy,
        "repeat": 0,
        "outcome": Outcome.ANSWERED.value,
        "final_answer": {"answer": "yes", "not_present": False},
        "correct": correct,
        "f1": None,
        "prompt_tokens": 50,
        "completion_tokens": 10,
        "cost_usd": 0.001,
        "latency_s": 1.0,
        "context_chars": 150,
        "trace": {"retrieval": {"n_rows": 1}} if strategy == CYPHER else {},
    }
    base.update(fields)
    return QuestionResult.model_validate(base).model_dump(mode="json")


def write_run(
    runs_root: Path,
    questions_root: Path,
    corpus_id: str,
    run_id: str,
    strategy: str,
    answer_pin: ModelPin,
    rows: list[dict[str, Any]],
) -> Path:
    """Write run_config.json, corpora.json and answers.jsonl; returns the run directory."""
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    config = RunConfig(
        run_id=run_id,
        experiment="TOOLING",
        reported=False,
        corpora=[corpus_id],
        strategies={strategy: {}},
        answer_pin=answer_pin,
        prompt_hashes=prompt_hashes(),
        question_set_sha256=question_set_sha256([questions_path(questions_root, corpus_id)]),
        primer=True,
        git_commit="0" * 40,
        git_dirty=False,
        created_at=datetime(2026, 10, 11),
    )
    (run_dir / "run_config.json").write_text(config.model_dump_json(), encoding="utf-8")
    record = CorpusRecord(
        corpus_id=corpus_id,
        role="test",
        generator_config=GeneratorConfig(),
        split_config=SplitConfig(),
        n_sheets=1,
        n_store_nodes=1,
        n_connector_pairs_predicted=0,
        n_plant_nodes=1,
        n_plant_edges=0,
        source_graph_hash="g" * 64,
        stage_seconds={},
    )
    (run_dir / "corpora.json").write_text("[" + record.model_dump_json() + "]", encoding="utf-8")
    lines = "".join(json.dumps(r) + "\n" for r in rows)
    (run_dir / "answers.jsonl").write_bytes(lines.encode("utf-8"))
    return run_dir


def scores(
    correct: list[bool],
    families: list[str],
    cost: float = 0.001,
    latency: float = 1.0,
) -> list[QuestionScore]:
    """Synthetic per-question scores: question i has family `families[i % len]`."""
    return [
        QuestionScore(
            qid=f"q{i}",
            family=families[i % len(families)],
            correct=ok,
            correct_at_cutoff=ok,
            cost_usd=cost,
            latency_s=latency,
            outcome=Outcome.ANSWERED,
        )
        for i, ok in enumerate(correct)
    ]
