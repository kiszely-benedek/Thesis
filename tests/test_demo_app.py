"""The demo server (DA-T4) over a toy plant: real strategies, fake model transport, no Neo4j.

The toy corpus is the harness toy; its database tier cannot be served by the toy store, so
every cascade runs without it (`context_rag` answers). Every ask is live, through a scripted
transport: nothing is paid and no cache is read.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from demo_run_toy import row, write_run
from plantgraph.demo.app import __main__ as app_main
from plantgraph.demo.app.config import DemoConfig, DemoCorpus, load_demo_config
from plantgraph.demo.app.server import HOST, create_app
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.demo.drawing.models import DrawingIndex, DrawingReport
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.models import Question
from qa_harness_toy import ABSTAIN_REPLY, CORPUS_ID, Toy, build_toy, pin

PDF_BYTES = b"%PDF-1.4\n% toy drawing set\n%%EOF\n"
EXAMPLE_CONFIG = Path("src/plantgraph/demo/app/demo_config.example.json")


@dataclass(frozen=True)
class Env:
    config: DemoConfig
    toy: Toy
    #: An unanswerable question (the scripted abstain reply is the right answer to it).
    unanswerable: Question
    #: An answerable question (the abstain reply is wrong for it).
    answerable: Question


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("demo-app-toy"))


def _policy() -> CascadePolicy:
    cypher = TierSpec(
        name="cypher-low",
        strategy="cypher_rag_plant",
        pin_sha256=pin().pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED, AcceptRule.ROWS}),
    )
    answer = TierSpec(
        name="answer",
        strategy="context_rag",
        pin_sha256=pin().pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )
    return CascadePolicy(name="toy-live", tiers=(cypher, answer))


def _write_drawings(toy: Toy, directory: Path) -> None:
    """A stand-in PDF and the sidecar index the export would write (one page per sheet)."""
    artifacts = load_corpus_artifacts(CORPUS_ID, toy.corpora_root / CORPUS_ID / "ingest.json")
    pages = {sheet.sheet_id: number for number, sheet in enumerate(artifacts.localized_sheets, 1)}
    report = DrawingReport(
        pages=len(pages), symbols=0, lines=0, flags=0, flags_linked=0, dangling_flags=0,
        overlaps=0, foreign_crossings=0, min_scale=1.0, layout_s=0.0, render_s=0.0,
    )  # fmt: skip
    index = DrawingIndex(corpus_id=CORPUS_ID, pdf_sha256="0" * 64, pages=pages, report=report)
    directory.mkdir(parents=True)
    (directory / "drawings.pdf").write_bytes(PDF_BYTES)
    (directory / "drawings.index.json").write_text(index.model_dump_json(), encoding="utf-8")


@pytest.fixture
def env(toy: Toy, tmp_path: Path) -> Env:
    unanswerable = next(q for q in toy.questions if not q.answerable)
    answerable = next(q for q in toy.questions if q.answerable)
    rows = [row(q.question_id, "cypher_rag_plant", 0.0002) for q in toy.questions]
    rows += [row(q.question_id, "context_rag", 0.001, answer="T-1") for q in toy.questions]
    run = write_run(tmp_path, "tier-run", CORPUS_ID, rows, pin=pin())
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(_policy().model_dump_json(), encoding="utf-8")
    _write_drawings(toy, tmp_path / "drawings")
    corpus = DemoCorpus(
        corpus_id=CORPUS_ID,
        ingest_json=toy.corpora_root / CORPUS_ID / "ingest.json",
        drawings_dir=tmp_path / "drawings",
        questions_jsonl=toy.questions_root / CORPUS_ID / "questions.jsonl",
        recorded_runs=(run,),
        tier_runs={"cypher-low": run, "answer": run},
    )
    config = DemoConfig(
        corpora=(corpus,),
        policy=str(policy_file),
        calls_log_path=tmp_path / "calls.jsonl",
    )
    return Env(config, toy, unanswerable, answerable)


Client = Callable[..., TestClient]


def scripted_transport() -> FakeTransport:
    """A fake model that abstains, at a cost of $0.0003 per call."""
    return FakeTransport(default_reply=ScriptedReply(text=ABSTAIN_REPLY, cost_usd=0.0003))


@pytest.fixture
def make_client(env: Env) -> Iterator[Client]:
    """`make_client(cap=, transport=, load=)` -> a client over a fresh app state."""
    states: list[AppState] = []

    def build(
        cap: float | None = None,
        transport: FakeTransport | None = None,
        load: bool = True,
    ) -> TestClient:
        state = build_app_state(
            env.config,
            session_cap_usd=cap,
            http_client=(transport or scripted_transport()).as_httpx_client(),
            held_corpora_probe=lambda: ("D1000",),  # no real Neo4j in tests
        )
        states.append(state)
        if load:
            state.load_all()
        return TestClient(create_app(state))

    yield build
    for state in states:  # delete each open cascade's temporary cache file
        state.close()


def _wait_for_end(client: TestClient, job_id: str, seconds: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get(f"/api/jobs/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} was still running after {seconds} s")


def _ask(client: TestClient, env: Env, question: Question, **fields: Any) -> Any:
    body = {
        "corpus_id": CORPUS_ID,
        "example_id": question.question_id,
        "text": question.text,
        **fields,
    }
    return client.post("/api/ask", json=body)


# --- status, files ---------------------------------------------------------------------------


def test_status_lists_the_corpus_and_the_tiers_that_can_answer(make_client: Client) -> None:
    status = make_client().get("/api/status").json()

    (corpus,) = status["corpora"]
    assert corpus["corpus_id"] == CORPUS_ID and corpus["state"] == "ready"
    assert corpus["pdf_present"] is True and corpus["n_benchmark_questions"] > 0
    # the toy store cannot serve the database tier: the cascade runs tier 2 only
    assert corpus["tier1_store"] is False and corpus["tiers"] == ["answer"]
    assert corpus["error_code"] is None
    assert status["policy_tiers"] == ["cypher-low", "answer"]
    assert status["spend"]["session_cap_usd"] == 2.0


def test_a_corpus_that_is_not_loaded_yet_is_waiting_and_cannot_be_asked(
    make_client: Client, env: Env
) -> None:
    client = make_client(load=False)

    assert client.get("/api/status").json()["corpora"][0]["state"] == "waiting"
    assert _ask(client, env, env.unanswerable).status_code == 409
    assert (
        client.get("/corpora/" + CORPUS_ID + "/drawings.pdf").status_code == 200
    )  # served at once


def test_the_pdf_is_served_inline(make_client: Client) -> None:
    response = make_client().get(f"/corpora/{CORPUS_ID}/drawings.pdf")

    assert response.status_code == 200 and response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")


def test_unknown_corpus_has_no_pdf_and_no_index(make_client: Client) -> None:
    client = make_client()

    assert client.get("/corpora/NOPE/drawings.pdf").status_code == 404
    assert client.get("/api/corpora/NOPE/index").status_code == 404


def test_the_page_index_maps_sheets_to_pages(make_client: Client) -> None:
    body = make_client().get(f"/api/corpora/{CORPUS_ID}/index").json()

    assert body["corpus_id"] == CORPUS_ID
    assert sorted(body["pages"].values()) == list(range(1, len(body["pages"]) + 1))


# --- benchmark questions ---------------------------------------------------------------------


def test_the_question_list_carries_no_gold(make_client: Client, env: Env) -> None:
    listed = make_client().get(f"/api/corpora/{CORPUS_ID}/questions").json()

    assert len(listed) == len(env.toy.questions)
    for entry in listed:
        assert set(entry) == {"question_id", "family", "topic", "text"}


def test_the_question_detail_carries_reference_gold_pages_k_and_recorded_rows(
    make_client: Client, env: Env
) -> None:
    question = next(q for q in env.toy.questions if q.answerable and q.evidence_sheets)

    body = make_client().get(f"/api/corpora/{CORPUS_ID}/questions/{question.question_id}").json()

    assert body["reference"] == question.reference and body["k"] == question.k
    assert {link["sheet_id"] for link in body["gold_sheets"]} == set(question.evidence_sheets)
    assert all(link["page"] >= 1 for link in body["gold_sheets"])
    assert {r["strategy"] for r in body["recorded"]} == {"cypher_rag_plant", "context_rag"}
    assert body["correct"] is None


def test_an_unknown_benchmark_question_is_404(make_client: Client) -> None:
    client = make_client()

    assert client.get(f"/api/corpora/{CORPUS_ID}/questions/nope").status_code == 404


# --- asking ----------------------------------------------------------------------------------


def test_a_benchmark_question_is_answered_live_and_scored_correct(
    make_client: Client, env: Env
) -> None:
    transport = scripted_transport()
    client = make_client(transport=transport)

    job_id = _ask(client, env, env.unanswerable).json()["job_id"]
    body = _wait_for_end(client, job_id)

    assert body["state"] == "done"
    live = body["result"]["live"]
    assert live["answered_by"] == "answer" and live["from_cache"] is False
    assert live["evaluated_policy"] is False  # tier 1 was left out
    assert body["result"]["benchmark"]["correct"] is True
    assert body["result"]["cache_hit_detected"] is False
    assert body["clear_s"] is not None and len(transport.requests) == 1


def test_a_typed_question_is_done_without_benchmark_facts(make_client: Client, env: Env) -> None:
    client = make_client()
    request = {"corpus_id": CORPUS_ID, "text": env.unanswerable.text}  # no example_id: free text

    job_id = client.post("/api/ask", json=request).json()["job_id"]
    body = _wait_for_end(client, job_id)

    assert body["state"] == "done" and body["result"]["benchmark"] is None


def test_a_question_is_counted_against_the_session_cap(make_client: Client, env: Env) -> None:
    client = make_client(cap=10.0)

    body = _wait_for_end(client, _ask(client, env, env.answerable).json()["job_id"])

    assert body["state"] == "done"
    assert body["spend"]["session_spent_usd"] == pytest.approx(0.0003)
    assert body["spend"]["session_cap_usd"] == 10.0


def test_a_question_over_the_session_cap_is_refused_before_any_call(
    make_client: Client, env: Env
) -> None:
    transport = FakeTransport()
    client = make_client(cap=0.001, transport=transport)  # reservation is 0.0018

    body = _wait_for_end(client, _ask(client, env, env.answerable).json()["job_id"])

    assert body["state"] == "refused" and "cap" in body["message"]
    assert transport.requests == []


def test_a_second_ask_while_one_runs_is_409_then_accepted_after(
    make_client: Client, env: Env
) -> None:
    slow = FakeTransport(
        default_reply=ScriptedReply(text=ABSTAIN_REPLY), latency_for_prompt=lambda _prompt: 0.6
    )
    client = make_client(cap=10.0, transport=slow)

    first = _ask(client, env, env.answerable)
    second = _ask(client, env, env.unanswerable)

    assert first.status_code == 200 and second.status_code == 409
    assert _wait_for_end(client, first.json()["job_id"])["state"] == "done"
    third = _ask(client, env, env.unanswerable)
    assert third.status_code == 200
    _wait_for_end(client, third.json()["job_id"])  # do not tear the state down mid-ask


def test_bad_requests_are_rejected(make_client: Client, env: Env) -> None:
    client = make_client()

    assert client.post("/api/ask", json={"corpus_id": CORPUS_ID, "text": "  "}).status_code == 422
    assert client.post("/api/ask", json={"corpus_id": "NOPE", "text": "x"}).status_code == 404
    unknown = {"corpus_id": CORPUS_ID, "example_id": "nope"}
    assert client.post("/api/ask", json=unknown).status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404


# --- start-up --------------------------------------------------------------------------------


def test_the_server_binds_to_loopback_only(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: dict[str, Any] = {}
    monkeypatch.setattr(app_main.uvicorn, "run", lambda app, **kwargs: started.update(kwargs))
    config_file = tmp_path / "demo_config.json"
    config_file.write_text(env.config.model_dump_json(), encoding="utf-8")

    app_main.main(["--config", str(config_file), "--port", "8123"])

    assert HOST == "127.0.0.1"
    assert started == {"host": "127.0.0.1", "port": 8123}


def test_the_session_cap_option_reaches_the_app_state_and_there_is_no_replay_only(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_main.uvicorn, "run", lambda app, **kwargs: None)
    seen: list[float | None] = []
    real_build = app_main.build_app_state

    def spy(config: Any, **kwargs: Any) -> AppState:
        seen.append(kwargs["session_cap_usd"])
        return real_build(config, **kwargs)

    monkeypatch.setattr(app_main, "build_app_state", spy)
    config_file = tmp_path / "demo_config.json"
    config_file.write_text(env.config.model_dump_json(), encoding="utf-8")

    app_main.main(["--config", str(config_file)])
    app_main.main(["--config", str(config_file), "--session-cap-usd", "0.5"])
    with pytest.raises(SystemExit):  # the switch is gone: argparse rejects it
        app_main.main(["--config", str(config_file), "--replay-only"])

    assert seen == [None, 0.5]


def test_the_example_config_is_valid_and_names_one_run_per_tier() -> None:
    config = load_demo_config(EXAMPLE_CONFIG)

    assert [c.corpus_id for c in config.corpora] == ["D100", "D1000"]
    for corpus in config.corpora:
        assert set(corpus.tier_runs) == {"cypher-luna", "agent-luna"}
    assert json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))["policy"] == "cascade_v3"
