"""Shared fixtures for the EXP-0001 tests: a tiny corpus called EX01, pins, inputs, a fake model.

Everything is offline. The corpus comes from the real ingest CLI with `--no-neo4j`; the database is
a stub; model replies come from the fake transport.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import httpx2

from plantgraph.ingest.__main__ import main as ingest_main
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.exp0001.ex01_runner import Ex01Settings, Ex01Summary, run_ex01
from plantgraph.store.neo4j_plan import LoadPlan

QIDS = ["CP11", "CP12", "CP13", "CP14", "CP15"]
FINAL_REPLY = '{"answer": "P4711 then H1007 then HV4750.01 then T4750", "not_present": false}'


def _pin(effort: str | None, model: str = "openai/gpt-6-luna") -> dict[str, Any]:
    extra = {"reasoning": {"effort": effort}} if effort else {}
    return {
        "backend": "openrouter",
        "model_id": model,
        "route_provider": "openai",
        "temperature": None,
        "seed": 0,
        "max_output_tokens": 16384,
        "extra": extra,
    }


def write_inputs(inputs_dir: Path, agent_params: dict[str, Any] | None = None) -> None:
    """The pin and parameter files the arms read, with the sealed run's contents."""
    inputs_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "pin_agent_luna_final_high.json": _pin("high"),
        "pin_cypher_luna_low.json": _pin("low"),
        "pin_ctx_gpt5mini.json": _pin(None, "openai/gpt-5-mini"),
        "params_cypher_plant.json": {"cypher_rag_plant": {"timeout_s": 30, "row_cap": 200}},
        "params_agent_low.json": {"graph_agent_low_steps": agent_params or {"max_steps": 40}},
    }
    for name, content in files.items():
        (inputs_dir / name).write_text(json.dumps(content), encoding="utf-8")


def write_questions(path: Path) -> None:
    """ChatP&ID-shaped rows: five scored, one out of scope (it must never be asked)."""
    rows = [_qa_row(qid, "scored", f"Question {qid}?") for qid in QIDS]
    rows.append(_qa_row("CP01", "out_of_scope_datasheet", "What is the length?"))
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _qa_row(qid: str, scope: str, question: str) -> dict[str, Any]:
    return {
        "qid": qid,
        "task_type": "Path Exploration",
        "question": question,
        "reference_answer": "ref",
        "source": "test",
        "source_page": 28,
        "last_page": 28,
        "scope": scope,
        "scope_reason": "test",
        "transcribed_by": "test",
    }


def build_corpus(corpora_root: Path) -> None:
    """A small generated corpus under the id EX01, stored with the plant profile."""
    argv = ["synthetic", "--n-units", "1", "--budget", "3", "--seed", "0", "--corpus-id", "EX01"]
    argv += ["--no-neo4j", "--store-profile", "plant", "--out", str(corpora_root / "EX01")]
    with contextlib.redirect_stdout(io.StringIO()):
        ingest_main(argv)


class StubCypherSource:
    """A database that answers every query with one row."""

    def corpus_id(self) -> str:
        return "EX01"

    def schema_text(self) -> str:
        return "schema"

    def label_names(self) -> frozenset[str]:
        return frozenset()

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[{"tag": "T4750"}], truncated=False)

    def close(self) -> None:
        """Nothing to release."""


def stub_factory(_plan: LoadPlan) -> StubCypherSource:
    return StubCypherSource()


def fake_client(cost_usd: float = 0.001) -> tuple[httpx2.Client, FakeTransport]:
    """An HTTP client whose reply depends on the prompt: a query, an agent step or an answer."""
    fake = FakeTransport()

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content.decode("utf-8"))
        text = " ".join(message.get("content", "") for message in body["messages"])
        fake.requests.append(request)
        reply = ScriptedReply(text=_reply_for(text), cost_usd=cost_usd)
        return fake._success_response(reply, model=body.get("model", "fake"))

    return httpx2.Client(transport=httpx2.MockTransport(handler)), fake


def _reply_for(prompt: str) -> str:
    if "writing a database query" in prompt:
        return "MATCH (n) RETURN n.tag AS tag LIMIT 5"
    if '"not_present":' in prompt:
        return FINAL_REPLY
    return '{"done": true}'


def make_settings(root: Path, **overrides: Any) -> Ex01Settings:
    """Settings over a fresh toy corpus, inputs and question file under `root`."""
    build_corpus(root / "corpora")
    write_inputs(root / "inputs")
    write_questions(root / "qa.jsonl")
    fields: dict[str, Any] = {
        "out_dir": root / "out",
        "inputs_dir": root / "inputs",
        "corpora_root": root / "corpora",
        "qa_path": root / "qa.jsonl",
        "arms": ["ctx-high", "ctx-low", "ctx-gpt5mini", "cyp", "ag"],
        "repeats": 2,
        "cap_usd": 5.0,
        "allow_paid_calls": True,
        "cost_per_question_usd": 0.01,
    }
    fields.update(overrides)
    return Ex01Settings(**fields)


def run(settings: Ex01Settings, client: httpx2.Client | None = None) -> Ex01Summary:
    """`run_ex01` with the stub database and silent progress."""
    return run_ex01(
        settings, http_client=client, progress=lambda _m: None, cypher_source_factory=stub_factory
    )
