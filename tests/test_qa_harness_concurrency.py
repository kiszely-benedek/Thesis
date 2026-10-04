"""`--concurrency N` (ADR-0043): same bytes as N = 1, safe resume, a cap that holds, a safe cache.

Everything is offline. `allow_paid_calls=True` appears only together with an injected
`FakeTransport`, which answers from a script (after a scripted delay) and opens no socket.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import CacheMiss, ChatMessage, ChatRequest, ChatResponse
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.summary import RunSummary
from plantgraph.qa.models import Outcome, QuestionResult, RunConfig
from qa_harness_toy import (
    ABSTAIN_REPLY,
    CORPUS_ID,
    Toy,
    abstaining_transport,
    build_toy,
    make_config,
    pin,
    seed_cache,
)

_N_QUESTIONS = 12


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    """The toy corpus with its 5 questions stretched to 12 distinct ones (distinct prompts)."""
    small = build_toy(tmp_path_factory.mktemp("concurrency-toy"))
    return scale_questions(small, small.questions_root.parent / "scaled", _N_QUESTIONS)


def scale_questions(toy: Toy, questions_root: Path, count: int) -> Toy:
    """Copies of the toy's questions with new ids and texts, so each has its own prompt."""
    variants = [
        toy.questions[i % len(toy.questions)].model_copy(
            update={
                "question_id": f"variant-{i:03d}",
                "text": f"{toy.questions[i % len(toy.questions)].text} (variant {i})",
            }
        )
        for i in range(count)
    ]
    path = questions_path(questions_root, CORPUS_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("".join(q.model_dump_json() + "\n" for q in variants).encode("utf-8"))
    return Toy(toy.corpora_root, questions_root, variants)


def scrambled_latency(prompt: str) -> float:
    """0 to 0.03 s from the prompt text: neighbouring questions finish in a mixed-up order."""
    return (sum(map(ord, prompt)) % 4) * 0.01


def costing_transport(cost_usd: float) -> FakeTransport:
    reply = ScriptedReply(text=ABSTAIN_REPLY, cost_usd=cost_usd)
    return FakeTransport(default_reply=reply, latency_for_prompt=scrambled_latency)


def scrambled_transport() -> FakeTransport:
    return abstaining_transport(latency_for_prompt=scrambled_latency)


def _run(
    toy: Toy,
    config: RunConfig,
    root: Path,
    fake: FakeTransport,
    *,
    concurrency: int,
    cost_per_question_usd: float | None = 0.001,  # a paid run with N > 1 must give one
    runs_name: str = "runs",
    cache_name: str = "cache.sqlite",
) -> RunSummary:
    return run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=root / runs_name,
        cache_path=root / cache_name,
        http_client=fake.as_httpx_client(),
        cost_per_question_usd=cost_per_question_usd,
        concurrency=concurrency,
        progress=lambda _message: None,
    )


def _answers(root: Path, runs_name: str = "runs") -> bytes:
    return (root / runs_name / "toy" / "answers.jsonl").read_bytes()


def _rows(root: Path, runs_name: str = "runs") -> list[QuestionResult]:
    return RunDir(root / runs_name / "toy").read_rows()


def _without_wall_clock(root: Path) -> bytes:
    """The rows minus `latency_s`, the one field that measures the live call itself.

    Two live runs can never agree on it (it is the time the call took), so they are compared
    without it; a replay reads it back from the cache and is compared byte for byte.
    """
    rows = [row.model_copy(update={"latency_s": 0.0}) for row in _rows(root)]
    return "".join(row.model_dump_json() + "\n" for row in rows).encode("utf-8")


def _reference_answers(toy: Toy, root: Path) -> bytes:
    """The rows a plain sequential run writes; every concurrent run must match them."""
    _run(toy, make_config(toy, allow_paid_calls=True), root, scrambled_transport(), concurrency=1)
    return _without_wall_clock(root)


def test_four_workers_write_the_same_bytes_as_one(toy: Toy, tmp_path: Path) -> None:
    expected = _reference_answers(toy, tmp_path / "one")

    fake = scrambled_transport()
    _run(toy, make_config(toy, allow_paid_calls=True), tmp_path / "four", fake, concurrency=4)

    assert _without_wall_clock(tmp_path / "four") == expected
    assert len(fake.requests) == _N_QUESTIONS


def test_replay_with_four_workers_makes_no_request_and_is_identical(
    toy: Toy, tmp_path: Path
) -> None:
    _run(
        toy,
        make_config(toy, allow_paid_calls=True),
        tmp_path,
        scrambled_transport(),
        concurrency=4,
    )

    replay_fake = scrambled_transport()
    _run(toy, make_config(toy), tmp_path, replay_fake, concurrency=4, runs_name="replayed")

    assert _answers(tmp_path, "replayed") == _answers(tmp_path)
    assert replay_fake.requests == []


def test_resume_after_an_interruption_at_four_workers_has_no_gap_and_no_duplicate(
    toy: Toy, tmp_path: Path
) -> None:
    expected = _reference_answers(toy, tmp_path / "one")
    done = toy.questions[:3]
    seed_cache(toy, tmp_path / "cache.sqlite", done)

    # a replay with a partly filled cache stops at the first miss: the interruption
    with pytest.raises(CacheMiss):
        _run(toy, make_config(toy), tmp_path, scrambled_transport(), concurrency=4)
    assert [row.question_id for row in _rows(tmp_path)] == [q.question_id for q in done]

    resume_fake = scrambled_transport()
    _run(
        toy,
        make_config(toy, allow_paid_calls=True),
        tmp_path,
        resume_fake,
        concurrency=4,
    )

    assert _without_wall_clock(tmp_path) == expected  # same file as never having been interrupted
    assert len(resume_fake.requests) == _N_QUESTIONS - len(done)


def test_a_provider_error_is_retried_after_the_first_pass_whatever_the_pool_size(
    toy: Toy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.client.time.sleep", lambda _seconds: None)
    outcomes: dict[int, list[str]] = {}
    for workers in (1, 4):
        # the first request fails fatally; its item is asked again after the first pass
        fake = scrambled_transport()
        fake.fail_times, fake.fail_status = 1, 400
        root = tmp_path / f"workers-{workers}"
        _run(toy, make_config(toy, allow_paid_calls=True), root, fake, concurrency=workers)
        outcomes[workers] = [row.question_id for row in _rows(root)]

    assert outcomes[4] == outcomes[1]
    assert outcomes[1][-1] == "variant-000"  # the failed first item lands last, as before


def test_the_spend_cap_holds_with_calls_in_flight_and_a_resume_finishes_the_file(
    toy: Toy, tmp_path: Path
) -> None:
    cost, cap = 0.01, 0.035  # three items fit under the cap, a fourth would pass it
    fake = costing_transport(cost)
    capped = make_config(toy, allow_paid_calls=True, max_spend_usd=cap)

    summary = _run(toy, capped, tmp_path, fake, concurrency=4, cost_per_question_usd=cost)

    assert summary.stopped_by_spend_cap
    assert len(fake.requests) * cost <= cap  # no more calls were paid for than the cap allows
    written = [row.question_id for row in _rows(tmp_path)]
    assert written == [q.question_id for q in toy.questions[: len(written)]]  # a prefix

    resumed = make_config(toy, allow_paid_calls=True)  # a resume may raise the cap
    _run(toy, resumed, tmp_path, scrambled_transport(), concurrency=4)
    assert [r.outcome for r in _rows(tmp_path)] == [Outcome.ANSWERED] * _N_QUESTIONS
    assert len(_rows(tmp_path)) == _N_QUESTIONS


def test_paid_run_with_several_workers_needs_a_cost_estimate(toy: Toy, tmp_path: Path) -> None:
    fake = scrambled_transport()
    with pytest.raises(ValueError, match="--cost-per-question-usd"):
        _run(
            toy,
            make_config(toy, allow_paid_calls=True),
            tmp_path,
            fake,
            concurrency=4,
            cost_per_question_usd=None,
        )

    assert not (tmp_path / "runs").exists()  # nothing was frozen or written
    assert fake.requests == []


@pytest.mark.parametrize("concurrency", [0, 9])
def test_concurrency_outside_one_to_eight_is_refused(
    toy: Toy, tmp_path: Path, concurrency: int
) -> None:
    with pytest.raises(ValueError, match="--concurrency from 1 to 8"):
        _run(toy, make_config(toy), tmp_path, scrambled_transport(), concurrency=concurrency)


def test_the_sqlite_cache_is_safe_under_concurrent_writers(tmp_path: Path) -> None:
    n_threads, n_keys = 8, 25
    errors: list[BaseException] = []

    def hammer(thread_number: int) -> None:
        try:
            for key in range(n_keys):
                request = _request(f"t{thread_number}-k{key}")
                cache.put(request, _response(f"answer {thread_number}-{key}"))
                assert cache.get(request) is not None
        except BaseException as error:  # noqa: BLE001 - reported to the main thread below
            errors.append(error)

    with SqliteCache(tmp_path / "cache.sqlite", "live") as cache:
        threads = [threading.Thread(target=hammer, args=(n,)) for n in range(n_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        for thread_number in range(n_threads):
            stored = cache.get(_request(f"t{thread_number}-k{n_keys - 1}"))
            assert stored is not None
            assert stored.text == f"answer {thread_number}-{n_keys - 1}"


def test_two_threads_asking_the_same_prompt_pay_for_one_call(tmp_path: Path) -> None:
    fake = FakeTransport(
        default_reply=ScriptedReply(text="same"), latency_for_prompt=lambda _prompt: 0.1
    )
    client, cache = build_chat_client(
        pin=pin(),
        allow_paid_calls=True,
        cache_path=tmp_path / "cache.sqlite",
        calls_log_path=tmp_path / "calls.jsonl",
        http_client=fake.as_httpx_client(),
    )
    request = _request("shared prompt")
    responses: list[ChatResponse] = []

    def ask() -> None:
        responses.append(client.complete(request, run_id="r"))

    threads = [threading.Thread(target=ask) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    cache.close()

    assert len(fake.requests) == 1
    assert sorted(response.from_cache for response in responses) == [False, True]


def _request(text: str) -> ChatRequest:
    return ChatRequest(
        pin=pin(), messages=[ChatMessage(role="user", content=text)], purpose="answer"
    )


def _response(text: str) -> ChatResponse:
    return ChatResponse(
        text=text,
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0,
        latency_s=0.0,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 10, 3),
    )
