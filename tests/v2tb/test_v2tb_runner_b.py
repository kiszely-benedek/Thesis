"""R6: the B runner against the frozen runner (design §10.6 (6)), and what it refuses.

Runner equivalence is checked the strict way. The frozen runner answers a toy corpus live (fake
transport) and fills a cache. The B runner then **replays from that same cache** with the primer
off: it stops at the first request that differs by one byte, and the rows it writes must equal the
frozen rows byte for byte, apart from the strategy name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx2
import pytest

from plantgraph.llm.models import CacheMiss
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import RunConfig
from plantgraph.qa.v2tb.runner_b import check_b_run, run_harness_b
from qa_harness_toy import ABSTAIN_REPLY, CORPUS_ID, Toy, build_toy, make_config

_PARAMS: dict[str, dict[str, Any]] = {
    "graph_agent_lines": {},
    "cypher_rag_lines": {"timeout_s": 5, "row_cap": 3},
}
_FIND = json.dumps({"call": {"tool": "find", "args": {"limit": 3}}})


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("runner-b-toy"), store_profile="plant_lines")


class _Transport:
    """Plays the model: an agent step calls `find` once then says done; a query call writes a
    fixed query; every final-answer prompt gets an abstention."""

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self._handle))

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        messages: list[dict[str, Any]] = json.loads(request.content)["messages"]
        if messages[0]["role"] == "system":
            done = any(m["role"] == "assistant" for m in messages)
            return _reply('{"done": true}' if done else _FIND)
        if "writing a database query" in messages[0]["content"]:
            return _reply("MATCH (n) RETURN n.tag")
        return _reply(ABSTAIN_REPLY)


def _reply(text: str) -> httpx2.Response:
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.01}
    choice = {"index": 0, "message": {"role": "assistant", "content": text}}
    choice["finish_reason"] = "stop"
    body = {"id": "gen-1", "object": "chat.completion", "created": 0, "model": "m"}
    return httpx2.Response(200, json={**body, "choices": [choice], "usage": usage})


class _Source:
    """A stand-in database: one row for every query."""

    def corpus_id(self) -> str:
        return CORPUS_ID

    def schema_text(self) -> str:
        return "SCHEMA"

    def label_names(self) -> frozenset[str]:
        return frozenset({"CorpusNode"})

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[{"tag": "X"}], truncated=False)

    def close(self) -> None:
        pass


def _config(toy: Toy, run_id: str, names: list[str], *, paid: bool, suffix: str) -> RunConfig:
    strategies = {f"{name}{suffix}": _PARAMS[name] for name in names}
    return make_config(
        toy, run_id=run_id, strategies=strategies, primer=False, allow_paid_calls=paid
    )


def _frozen(toy: Toy, root: Path, names: list[str], transport: _Transport) -> None:
    run_harness(
        config=_config(toy, "frozen", names, paid=True, suffix=""),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=root / "runs",
        cache_path=root / "frozen_cache.sqlite",
        http_client=transport.client(),
        progress=lambda _m: None,
        cypher_source_factory=lambda _plan: _Source(),  # type: ignore[arg-type,return-value]
    )


def _b(
    toy: Toy, root: Path, names: list[str], *, cache: str, transport: _Transport | None, run_id: str
) -> None:
    run_harness_b(
        config=_config(toy, run_id, names, paid=transport is not None, suffix="_b"),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=root / "runs",
        cache_path=root / cache,
        http_client=None if transport is None else transport.client(),
        progress=lambda _m: None,
        cypher_source_factory=lambda _plan: _Source(),  # type: ignore[arg-type,return-value]
        require_b=False,
    )


def _normalized(path: Path, names: list[str]) -> bytes:
    """The rows with the run id, the B strategy suffix and the cache flag made alike.

    A replay answers from the cache, so it marks every call `from_cache: true`; that flag, the run
    id and the `_b` suffix are the only things allowed to differ.
    """
    text = path.read_bytes().decode("utf-8")
    for name in names:
        text = text.replace(f'"{name}_b"', f'"{name}"')
    text = text.replace('"from_cache":true', '"from_cache":false')
    return re.sub(r'"run_id":"[^"]*"', '"run_id":"X"', text).encode("utf-8")


def _key_paths(path: Path) -> set[str]:
    """Every dotted key path that occurs in any line of a jsonl file (list items merged)."""
    found: set[str] = set()

    def walk(value: object, prefix: str) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                walk(inner, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, list):
            for inner in value:
                walk(inner, f"{prefix}[]")
        else:
            found.add(prefix)

    for line in path.read_text("utf-8").splitlines():
        walk(json.loads(line), "")
    return found


@pytest.mark.parametrize("names", [["graph_agent_lines"], ["cypher_rag_lines"]])
def test_replaying_the_frozen_cache_through_the_b_runner_gives_the_frozen_rows(
    toy: Toy, tmp_path: Path, names: list[str]
) -> None:
    _frozen(toy, tmp_path, names, _Transport())
    (tmp_path / "frozen_cache.sqlite").replace(tmp_path / "b_cache.sqlite")

    # replay only: no transport, so any request that differs from a frozen one is a cache miss
    _b(toy, tmp_path, names, cache="b_cache.sqlite", transport=None, run_id="replayed")

    frozen = _normalized(tmp_path / "runs/frozen/answers.jsonl", [])
    replayed = _normalized(tmp_path / "runs/replayed/answers.jsonl", names)
    assert replayed == frozen
    assert len(frozen.splitlines()) == len(toy.questions)


def test_the_b_runner_replay_misses_the_cache_when_the_primer_is_on(
    toy: Toy, tmp_path: Path
) -> None:
    """The check above can fail: with the primer on the B prompts differ, so the replay stops."""
    names = ["graph_agent_lines"]
    _frozen(toy, tmp_path, names, _Transport())
    (tmp_path / "frozen_cache.sqlite").replace(tmp_path / "b_cache.sqlite")
    config = _config(toy, "primed", names, paid=False, suffix="_b").model_copy(
        update={"primer": True}
    )

    with pytest.raises(CacheMiss):
        run_harness_b(
            config=config,
            corpus_roles={CORPUS_ID: "dev"},
            corpora_root=toy.corpora_root,
            questions_root=toy.questions_root,
            runs_root=tmp_path / "runs",
            cache_path=tmp_path / "b_cache.sqlite",
            progress=lambda _m: None,
            require_b=False,
        )


@pytest.mark.parametrize("names", [["graph_agent_lines"], ["cypher_rag_lines"]])
def test_the_b_runner_writes_the_same_call_answer_and_timing_fields_as_the_frozen_one(
    toy: Toy, tmp_path: Path, names: list[str]
) -> None:
    _frozen(toy, tmp_path, names, _Transport())
    _b(toy, tmp_path, names, cache="b_live.sqlite", transport=_Transport(), run_id="b_live")

    for file_name in ("calls.jsonl", "answers.jsonl", "timings.jsonl"):
        frozen = _key_paths(tmp_path / "runs/frozen" / file_name)
        b_run = _key_paths(tmp_path / "runs/b_live" / file_name)
        assert b_run == frozen, file_name
    # the fields the design names: tokens, cost, latency, provider id, retrieval trace
    answers = _key_paths(tmp_path / "runs/b_live/answers.jsonl")
    assert {"prompt_tokens", "completion_tokens", "cost_usd", "latency_s"} <= answers
    assert any(key.startswith("trace.retrieval.") for key in answers)
    calls = _key_paths(tmp_path / "runs/b_live/calls.jsonl")
    assert "response.provider_response_id" in calls and "response.cost_usd" in calls


def test_a_b_run_refuses_an_a_corpus_and_a_frozen_strategy_name(toy: Toy) -> None:
    a_corpus = make_config(toy, strategies={"graph_agent_lines_b": {}})
    with pytest.raises(ValueError, match="only B corpora"):
        check_b_run(a_corpus)

    b_corpus = a_corpus.model_copy(update={"corpora": [CORPUS_ID + "B"]})
    check_b_run(b_corpus)  # passes: a B corpus id and a B strategy
    frozen_name = b_corpus.model_copy(update={"strategies": {"graph_agent_lines": {}}})
    with pytest.raises(ValueError, match="only strategies in"):
        check_b_run(frozen_name)
