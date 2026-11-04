"""D4, the chat-model decider of EXP-0004 (X-T6): prompt, parse, cap, cache-only mode, key hygiene.

Every test uses the fake transport (`llm/fake_transport.py`): no test can reach the network, and a
test that must make no request asserts `len(transport.requests) == 0`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from plantgraph.exp0004 import commands, d4_cli
from plantgraph.exp0004.__main__ import main
from plantgraph.exp0004.corpus import CorpusSpec
from plantgraph.exp0004.d4_commands import PilotSummary, decide_d4, open100, pilot, sample_indices
from plantgraph.exp0004.d4_decider import ChatPairDecider
from plantgraph.exp0004.d4_prompt import SYSTEM_PROMPT, build_request, parse_verdict
from plantgraph.exp0004.d4_session import DEFAULT_PIN_PATH, LlmOptions, open_decider
from plantgraph.exp0004.d4_stats import PairCall, summarize
from plantgraph.exp0004.deciders import DECIDER_IDS, DeciderRun, make_decider
from plantgraph.exp0004.storage import decision_path
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply, message_hash
from plantgraph.llm.models import CacheMiss, ModelPin, ProviderError
from plantgraph.qa.harness.spend_cap import SpendCapReached
from plantgraph.resolution.identity_candidates import CandidatePair, ContentKey
from plantgraph.resolution.identity_deciders import PairDecision

REPO = Path(__file__).parent.parent
SAME = '{"same_item": true, "reason": "same pump, spelled twice"}'
DIFFERENT = '{"same_item": false, "reason": "a spare"}'
CARD_YES = 'Occurrence A: tag "P-1A"\nOccurrence B: tag "P1A"'
CARD_NO = 'Occurrence A: tag "P-1A"\nOccurrence B: tag "P-1B"'
CARD_BAD = 'Occurrence A: tag "K-2"\nOccurrence B: tag "K2"'


def _pin() -> ModelPin:
    return ModelPin.model_validate_json((REPO / DEFAULT_PIN_PATH).read_text(encoding="utf-8"))


def _reply(card: str, text: str) -> tuple[str, ScriptedReply]:
    key = message_hash(build_request(_pin(), card).messages)
    return key, ScriptedReply(text=text, cost_usd=0.0001)


def _scripted(transport_text: dict[str, str]) -> FakeTransport:
    return FakeTransport(
        replies_by_message_hash=dict(_reply(card, text) for card, text in transport_text.items())
    )


def _options(tmp_path: Path, transport: FakeTransport, **flags: object) -> LlmOptions:
    return LlmOptions(
        pin_path=REPO / DEFAULT_PIN_PATH,
        cache_path=tmp_path / "exp0004.sqlite",
        http_client=transport.as_httpx_client(),
        **flags,  # type: ignore[arg-type]
    )


def _paid(tmp_path: Path, transport: FakeTransport, cap: float = 1.0) -> LlmOptions:
    return _options(tmp_path, transport, allow_paid_calls=True, max_spend_usd=cap)


# --- prompt and parse -------------------------------------------------------------------------


def test_prompt_has_the_one_sentence_and_no_operator_or_synonym() -> None:
    assert "Installed spares share a number and differ by a trailing letter." in SYSTEM_PROMPT
    lowered = SYSTEM_PROMPT.lower()
    for word in ("synonym", "separator", "prefix", "drop", "padding", "zero", "HX", "PU"):
        assert word.lower() not in lowered


def test_request_holds_the_card_text_and_nothing_else() -> None:
    request = build_request(_pin(), CARD_YES)
    assert [m.role for m in request.messages] == ["system", "user"]
    assert request.messages[1].content == CARD_YES
    assert request.json_mode


@pytest.mark.parametrize(
    "text",
    ["", "yes", "{}", '{"same_item": "true", "reason": "x"}', '{"same_item": true}', "[true]"],
)
def test_anything_but_the_requested_object_is_a_parse_failure(text: str) -> None:
    assert parse_verdict(text) is None


def test_the_requested_object_parses() -> None:
    verdict = parse_verdict(f"  {SAME}\n")
    assert verdict is not None and verdict.same_item and "pump" in verdict.reason


# --- the decider ------------------------------------------------------------------------------


def test_accept_reject_and_parse_failure(tmp_path: Path) -> None:
    transport = _scripted({CARD_YES: SAME, CARD_NO: DIFFERENT, CARD_BAD: "I think so."})
    with open_decider(_paid(tmp_path, transport), tmp_path / "calls.jsonl", "t") as (decider, pin):
        calls = [decider.ask(card) for card in (CARD_YES, CARD_NO, CARD_BAD)]
        stats = summarize(decider.calls, pin.pin_hash(), "hash")
    assert [call.same_item for call in calls] == [True, False, None]
    assert [call.parse_ok for call in calls] == [True, True, False]
    assert stats.n_parse_failures == 1 and stats.parse_failure_rate == pytest.approx(1 / 3)
    assert stats.cost_usd_spent == pytest.approx(0.0003)
    assert len(transport.requests) == 3


def test_decide_scores_one_or_zero_and_a_parse_failure_is_not_accepted(tmp_path: Path) -> None:
    transport = _scripted({CARD_YES: SAME, CARD_NO: DIFFERENT, CARD_BAD: "nonsense"})
    with open_decider(_paid(tmp_path, transport), tmp_path / "c.jsonl", "t") as (decider, _):
        decisions = [_decide_card(decider, card) for card in (CARD_YES, CARD_NO, CARD_BAD)]
    assert [(d.score, d.accept) for d in decisions] == [(1.0, True), (0.0, False), (0.0, False)]


def _decide_card(decider: ChatPairDecider, card: str) -> PairDecision:
    pair = CandidatePair(
        first=ContentKey("S1", "P-1A", "Pump"),
        second=ContentKey("S2", "P1A", "Pump"),
        blocking_key=("Pump", "11"),
        card=card,
    )
    return decider.decide(pair)


def test_latency_percentiles_are_nearest_rank() -> None:
    calls = [_call(latency) for latency in (1.0, 2.0, 3.0, 4.0, 10.0)]
    stats = summarize(calls, "pin", "prompt")
    assert (stats.latency_p50_s, stats.latency_p95_s) == (3.0, 10.0)
    assert summarize([], "pin", "prompt").latency_p50_s is None


def _call(latency_s: float) -> PairCall:
    return PairCall(
        card="c",
        answer_text="a",
        same_item=True,
        reason="r",
        parse_ok=True,
        from_cache=False,
        cost_usd=0.001,
        latency_s=latency_s,
    )


# --- cache-only mode, cap, key hygiene --------------------------------------------------------


def test_without_the_flag_a_miss_stops_with_zero_requests(tmp_path: Path) -> None:
    transport = _scripted({CARD_YES: SAME})
    with open_decider(_options(tmp_path, transport), tmp_path / "c.jsonl", "t") as (decider, _):
        with pytest.raises(CacheMiss):
            decider.ask(CARD_YES)
    assert len(transport.requests) == 0


def test_a_filled_cache_replays_without_the_flag(tmp_path: Path) -> None:
    transport = _scripted({CARD_YES: SAME})
    with open_decider(_paid(tmp_path, transport), tmp_path / "c.jsonl", "t") as (decider, _):
        decider.ask(CARD_YES)
    again = _scripted({CARD_YES: SAME})
    with open_decider(_options(tmp_path, again), tmp_path / "c.jsonl", "t") as (decider, _):
        call = decider.ask(CARD_YES)
    assert call.from_cache and len(again.requests) == 0


def test_the_flag_needs_a_positive_cap(tmp_path: Path) -> None:
    transport = _scripted({})
    for cap in (None, 0.0):
        options = _options(tmp_path, transport, allow_paid_calls=True, max_spend_usd=cap)
        with pytest.raises(ValueError, match="max-spend-usd"):
            with open_decider(options, tmp_path / "c.jsonl", "t"):
                pass
    assert len(transport.requests) == 0


def test_the_cap_stops_before_the_call_that_could_pass_it(tmp_path: Path) -> None:
    # every reply costs 0.01; after the first, a second could reach the 0.015 cap
    transport = FakeTransport(default_reply=ScriptedReply(text=SAME, cost_usd=0.01))
    with open_decider(_paid(tmp_path, transport, cap=0.015), tmp_path / "c.jsonl", "t") as (d, _):
        d.ask(CARD_YES)
        with pytest.raises(SpendCapReached):
            d.ask(CARD_NO)
    assert len(transport.requests) == 1


def test_the_api_key_never_reaches_an_error_or_the_calls_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "sk-or-test-secret-0123456789"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    transport = FakeTransport(fail_times=99, fail_status=401, echo_authorization_header=True)
    log = tmp_path / "calls.jsonl"
    with open_decider(_paid(tmp_path, transport), log, "t") as (decider, _):
        with pytest.raises(ProviderError) as error:
            decider.ask(CARD_YES)
    assert secret not in str(error.value)
    assert secret not in log.read_text(encoding="utf-8")


def test_without_the_flag_the_key_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-must-not-be-used")
    transport = FakeTransport()
    with open_decider(_options(tmp_path, transport), tmp_path / "c.jsonl", "t") as (decider, _):
        with pytest.raises(CacheMiss):
            decider.ask(CARD_YES)
    assert len(transport.requests) == 0


# --- pilot, decide, OPEN100 on a small corpus -------------------------------------------------


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("corpus") / "dev"
    spec = CorpusSpec(
        corpus_id="D10g2d100Vf",
        target_sheets=10,
        seed=1,
        duplication_rate=1.0,
        families=("format",),
    )
    commands.build(spec, directory)
    return directory


def _copy(built: Path, tmp_path: Path) -> Path:
    """A fresh corpus directory per test (a measurement is never overwritten)."""
    target = tmp_path / "dir"
    target.mkdir()
    for name in ("corpus.json", "pairs.json"):
        (target / name).write_text((built / name).read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_sample_is_deterministic_sorted_and_checked() -> None:
    assert sample_indices(50, 5) == sample_indices(50, 5)
    assert sample_indices(50, 5) == sorted(sample_indices(50, 5))
    assert len(set(sample_indices(50, 20))) == 20
    with pytest.raises(ValueError, match="sample"):
        sample_indices(3, 4)


def test_pilot_reports_the_parse_failure_rate(built: Path, tmp_path: Path) -> None:
    directory = _copy(built, tmp_path)
    transport = FakeTransport(default_reply=ScriptedReply(text="not json"))
    summary = pilot(directory, 3, _paid(tmp_path, transport))
    assert summary.stats.n_calls == 3 and summary.stats.n_parse_failures == 3
    assert summary.parse_failures_over_limit
    stored = json.loads((directory / "pilot" / "summary.json").read_text(encoding="utf-8"))
    assert PilotSummary.model_validate(stored).stats.parse_failure_rate == 1.0
    assert len(json.loads((directory / "pilot" / "calls.json").read_text("utf-8"))["calls"]) == 3


def test_pilot_without_the_flag_stops_at_the_first_miss(built: Path, tmp_path: Path) -> None:
    directory = _copy(built, tmp_path)
    transport = FakeTransport()
    with pytest.raises(CacheMiss):
        pilot(directory, 3, _options(tmp_path, transport))
    assert len(transport.requests) == 0


def test_decide_d4_writes_a_decision_that_score_accepts(built: Path, tmp_path: Path) -> None:
    directory = _copy(built, tmp_path)
    transport = FakeTransport(default_reply=ScriptedReply(text=SAME, cost_usd=0.0002))
    run = decide_d4(directory, _paid(tmp_path, transport))
    assert run.decider == "d4" and run.threshold is None
    assert run.llm is not None and run.llm.n_calls == len(run.said_same)
    stored = DeciderRun.model_validate_json(
        decision_path(directory, "d4").read_text(encoding="utf-8")
    )
    assert stored.llm == run.llm
    score = commands.score(directory, n_resamples=20)
    assert [d.decider for d in score.deciders] == ["d4"]
    assert score.deciders[0].llm == run.llm


def test_open100_writes_text_only_answers(tmp_path: Path) -> None:
    transport = FakeTransport(default_reply=ScriptedReply(text=DIFFERENT))
    answers = open100(tmp_path / "open100.json", _paid(tmp_path, transport))
    assert len(answers) == 4 and all("class not given" in a.card for a in answers)
    assert len(json.loads((tmp_path / "open100.json").read_text(encoding="utf-8"))) == 4


# --- command line -----------------------------------------------------------------------------


def test_cli_refuses_the_flag_without_a_cap(tmp_path: Path) -> None:
    argv = ["open100", "--out", str(tmp_path / "o.json"), "--allow-paid-calls"]
    with pytest.raises(SystemExit, match="max-spend-usd"):
        main([*argv, "--cache-path", str(tmp_path / "x.sqlite")])


def test_cli_without_the_flag_is_cache_only(tmp_path: Path) -> None:
    # no fake is injected here: the refusing transport of the harness would raise on any request
    argv = [
        "open100",
        "--out",
        str(tmp_path / "o.json"),
        "--cache-path",
        str(tmp_path / "x.sqlite"),
    ]
    with pytest.raises(SystemExit, match="No cached response"):
        main(argv)


def test_d4_is_a_known_decider_but_not_built_by_make_decider() -> None:
    assert "d4" in DECIDER_IDS
    with pytest.raises(ValueError, match="d4"):
        make_decider("d4", None)
    assert d4_cli.is_llm_command(argparse.Namespace(command="decide", decider="d4"))
    assert not d4_cli.is_llm_command(argparse.Namespace(command="decide", decider="d1"))
