"""Toy V2T tier runs for the cascade_v4 tests: real Luna pins and V2T params over `cascade_toy`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cascade_toy import CORPUS, ToyRun, row, write_questions, write_run
from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.checks import LoadedRun, load_run
from plantgraph.qa.cascade.join import TierSource
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.tune_select import V4
from plantgraph.qa.models import RunConfig

CYPHER_V2T = "cypher_rag_lines"
AGENT_V2T = "graph_agent_lines"
_INPUTS = Path(__file__).resolve().parents[1] / "data/runs/exp0007/inputs"


def pin(file_name: str) -> ModelPin:
    return ModelPin.model_validate_json((_INPUTS / file_name).read_text(encoding="utf-8"))


def write_tier(
    tmp_path: Path,
    run_id: str,
    strategy: str,
    pin_file: str,
    rows: list[dict[str, Any]],
    *,
    timeout_s: float = 30.0,
    deadline_s: float | None = None,
    template_hash: str | None = None,
) -> Path:
    """A toy run rewritten to look like a V2T tier: real Luna pin, V2T params, optional deadline."""
    questions_root = write_questions(tmp_path / "questions")
    run_dir = write_run(tmp_path / "runs", questions_root, ToyRun(run_id, strategy, "low", rows))
    path = run_dir / "run_config.json"
    config = RunConfig.model_validate_json(path.read_text(encoding="utf-8"))
    hashes = dict(config.prompt_hashes)
    if template_hash is not None:
        hashes["final_answer_v2t.txt"] = template_hash
    params = {strategy: {"timeout_s": timeout_s, "row_cap": 1000} if strategy == CYPHER_V2T else {}}
    updated = config.model_copy(
        update={
            "answer_pin": pin(pin_file),
            "strategies": params,
            "question_deadline_s": deadline_s,
            "prompt_hashes": hashes,
        }
    )
    path.write_text(updated.model_dump_json(), encoding="utf-8")
    return run_dir


def loaded_tier(tmp_path: Path, tier_index: int, **options: Any) -> LoadedRun:
    policy = load_policies(V2T_POLICIES_DIR)[V4]
    if tier_index == 0:
        rows, pin_file = cypher_rows(), "pin_cypher_luna_low.json"
    else:
        rows, pin_file = agent_rows(), "pin_agent_luna_final_high.json"
    tier = policy.tiers[tier_index]
    run_dir = write_tier(tmp_path, f"r{tier_index}", tier.strategy, pin_file, rows, **options)
    return load_run(tier, run_dir, tmp_path / "questions", CORPUS)


USAGE = {"n_calls": 1, "prompt_tokens": 9, "completion_tokens": 9, "cost_usd": 0.002}


def cypher_rows() -> list[dict[str, Any]]:
    """q1 accepted; q2 correct but cut at the row cap; q3 retrieval error; q4 abstains."""
    abstain = {"answer": None, "not_present": True}
    ok = {"retrieval": {"n_rows": 2, "truncated": False}}
    cut = {"retrieval": {"n_rows": 1000, "truncated": True}}
    s = CYPHER_V2T
    return [
        row("T1:q1", s, trace=ok, retrieval_usage=USAGE),
        row("T1:q2", s, trace=cut, retrieval_usage=USAGE),
        row(
            "T1:q3",
            s,
            outcome="RETRIEVAL_ERROR",
            final_answer=None,
            correct=False,
            retrieval_usage=USAGE,
        ),
        row("T1:q4", s, final_answer=abstain, correct=False, trace=ok, retrieval_usage=USAGE),
    ]


def agent_rows() -> list[dict[str, Any]]:
    """The agent is wrong on q1 and q3, and takes 130 s on q4."""
    s = AGENT_V2T
    return [
        row("T1:q1", s, correct=False),
        row("T1:q2", s),
        row("T1:q3", s, correct=False),
        row("T1:q4", s, latency_s=130.0),
    ]


def tier_sources(tmp_path: Path, *, timeout_s: float) -> dict[str, TierSource]:
    cypher = write_tier(
        tmp_path, "c", CYPHER_V2T, "pin_cypher_luna_low.json", cypher_rows(), timeout_s=timeout_s
    )
    agent = write_tier(tmp_path, "a", AGENT_V2T, "pin_agent_luna_final_high.json", agent_rows())
    return {"cypher-v2t": TierSource(cypher), "agent-v2t": TierSource(agent)}
