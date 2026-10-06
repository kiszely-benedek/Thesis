"""Both agents through the whole harness, offline: cost totals, call log, spend cap, replay.

`allow_paid_calls=True` appears only with an injected transport that answers from a script and
opens no socket; no test passes the CLI flag.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.summary import RunSummary
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.models import QuestionResult
from qa_harness_toy import ABSTAIN_REPLY, CORPUS_ID, Toy, build_toy, make_config

_CALL_COST = 0.01
_FIND = json.dumps({"call": {"tool": "find", "args": {"limit": 3}}})


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("agent-toy"))


class _AgentTransport:
    """Plays the model: an agent step is told apart by its system message.

    `graph_agent` (no seed map in its first message) calls `find` once and then says done; the
    `hier_agent` says done at once, on its seed. Every final-answer prompt gets an abstention.
    """

    def __init__(self) -> None:
        self.n_agent_steps = 0
        self.n_final_calls = 0

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self._handle))

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        messages: list[dict[str, Any]] = json.loads(request.content)["messages"]
        if messages[0]["role"] != "system":
            self.n_final_calls += 1
            return _reply(ABSTAIN_REPLY)
        self.n_agent_steps += 1
        seeded = "Seed map" in messages[1]["content"]
        already_called = any(m["role"] == "assistant" for m in messages)
        return _reply('{"done": true}' if seeded or already_called else _FIND)


def _reply(text: str) -> httpx2.Response:
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": _CALL_COST}
    choice = {
        "index": 0,
        "message": {"role": "assistant", "content": text},
        "finish_reason": "stop",
    }
    return httpx2.Response(
        200, json={"id": "x", "object": "chat.completion", "created": 0, "model": "m",
                   "choices": [choice], "usage": usage}
    )  # fmt: skip


def _run(toy: Toy, tmp_path: Path, transport: _AgentTransport, **overrides: object) -> RunSummary:
    defaults: dict[str, Any] = {
        "strategies": {"graph_agent": {}, "hier_agent": {}},
        "allow_paid_calls": True,
        "primer": True,
    }
    return run_harness(
        config=make_config(toy, **{**defaults, **overrides}),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=transport.client(),
        progress=lambda _message: None,
    )


def _rows(tmp_path: Path, run_id: str = "toy") -> list[QuestionResult]:
    path = tmp_path / "runs" / run_id / "answers.jsonl"
    return [
        QuestionResult.model_validate_json(line) for line in path.read_text("utf-8").splitlines()
    ]


def test_every_agent_call_counts_in_the_question_total_and_is_logged_with_its_question(
    toy: Toy, tmp_path: Path
) -> None:
    transport = _AgentTransport()

    summary = _run(toy, tmp_path, transport)

    rows = _rows(tmp_path)
    n_questions = len(toy.questions)
    assert len(rows) == 2 * n_questions and summary.stopped_by_spend_cap is False
    for row in rows:
        assert row.retrieval_usage is not None
        expected_agent_calls = 2 if row.strategy == "graph_agent" else 1  # hier stops on its seed
        assert row.retrieval_usage.n_calls == expected_agent_calls
        assert row.total_cost_usd == pytest.approx((expected_agent_calls + 1) * _CALL_COST)
        assert row.trace["retrieval"]["stop_reason"] == "done"
        assert row.trace["retrieval"]["n_steps"] == expected_agent_calls
    assert transport.n_agent_steps == 3 * n_questions
    assert transport.n_final_calls == 2 * n_questions
    assert summary.mean_total_cost_usd["graph_agent"] == pytest.approx(3 * _CALL_COST)
    assert summary.mean_total_cost_usd["hier_agent"] == pytest.approx(2 * _CALL_COST)
    calls = [
        json.loads(line) for line in (tmp_path / "runs/toy/calls.jsonl").read_text().splitlines()
    ]
    steps = [c for c in calls if c["purpose"] == "agent_step"]
    assert len(steps) == transport.n_agent_steps
    assert all(c["question_id"] is not None and c["strategy"] in _AGENTS for c in steps)


_AGENTS = {"graph_agent", "hier_agent"}


def test_the_routing_metrics_read_the_agents_trace(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, _AgentTransport())

    graph_rows = [row for row in _rows(tmp_path) if row.strategy == "graph_agent"]

    traces = [row.trace for row in graph_rows]
    assert all(
        "routed_sheets" in t["retrieval"] and "serialized_keys" in t["retrieval"] for t in traces
    )
    answerable = [
        t for row, t in zip(graph_rows, traces, strict=True) if row.trace["retrieval"]["n_steps"]
    ]
    assert any("relaxed_routing_hit" in t for t in answerable)  # the harness could score routing


def test_the_spend_cap_stops_inside_an_agents_question_without_passing_it(
    toy: Toy, tmp_path: Path
) -> None:
    cap = 1.5 * _CALL_COST  # one graph_agent question needs three calls

    transport = _AgentTransport()

    summary = _run(toy, tmp_path, transport, strategies={"graph_agent": {}}, max_spend_usd=cap)

    assert summary.stopped_by_spend_cap
    # the first call fits, the second could pass the cap, so the question was left unanswered
    assert transport.n_agent_steps == 1 and transport.n_final_calls == 0
    assert transport.n_agent_steps * _CALL_COST <= cap


def test_a_replay_serves_every_agent_call_from_the_cache_and_keeps_the_totals(
    toy: Toy, tmp_path: Path
) -> None:
    _run(toy, tmp_path, _AgentTransport())
    live = _rows(tmp_path)

    # no transport is given, so a replay that tried to call the model would be refused
    run_harness(
        config=make_config(
            toy, run_id="replay", strategies={"graph_agent": {}, "hier_agent": {}}, primer=True
        ),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        progress=lambda _message: None,
    )

    replayed = _rows(tmp_path, "replay")
    assert len(replayed) == len(live)
    for before, after in zip(live, replayed, strict=True):
        assert after.retrieval_usage == before.retrieval_usage  # the cache keeps the first cost
        assert after.outcome == before.outcome
        assert (
            after.trace["retrieval"]["serialized_keys"]
            == (before.trace["retrieval"]["serialized_keys"])
        )
    timings_path = tmp_path / "runs" / "replay" / "timings.jsonl"
    timings = [
        TimingRow.model_validate_json(line) for line in timings_path.read_text().splitlines()
    ]
    assert all(t.spent_usd == 0.0 for t in timings)  # nothing was spent again
