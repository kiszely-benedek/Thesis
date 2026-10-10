"""The live cascade (DA-T2): lazy tiers, the carried deadline, replay-only misses, the CLI.

Tiers use stub strategies and a scripted client whose recorded latency the test chooses, so a
test reads like a timetable. Only the cache-miss test uses the real replay client.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import ChatRequest, ChatResponse, ModelPin
from plantgraph.qa.cascade import live as live_module
from plantgraph.qa.cascade.cli import main
from plantgraph.qa.cascade.live import LiveCascade, LivePolicyRefused, LiveTier
from plantgraph.qa.cascade.live_ask import add_ask_arguments
from plantgraph.qa.cascade.live_build import OpenedCascade
from plantgraph.qa.cascade.live_models import FreeTextQuestion, LiveAnswer, NeedsPaidCall
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, Decision, TierSpec
from plantgraph.qa.cascade.policy import decide
from plantgraph.qa.harness.attempt_models import AttemptSettings
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.models import AnswerType, Outcome, RetrievalResult

YES = '{"answer": "yes", "not_present": false}'
GARBAGE = "no json here"
QUESTION = FreeTextQuestion.from_text("Is V-1 connected to P-2?", AnswerType.BOOLEAN)
CUTOFF_S = 120.0


def _pin(effort: str) -> ModelPin:
    return ModelPin(
        backend="openrouter",
        model_id="toy/model",
        max_output_tokens=100,
        extra={"reasoning": {"effort": effort}},
    )


def _policy(**fields: Any) -> CascadePolicy:
    first = TierSpec(
        name="t1",
        strategy="stub-cypher",
        pin_sha256=_pin("low").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED, AcceptRule.ROWS, AcceptRule.NOT_ABSTAINED}),
    )
    second = TierSpec(
        name="t2",
        strategy="stub-agent",
        pin_sha256=_pin("high").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )
    return CascadePolicy(name="toy", tiers=(first, second), **fields)


class StubStrategy:
    """Retrieval with no model call: a fixed context and, for a Cypher-like tier, a row count."""

    def __init__(self, name: str, n_rows: int | None) -> None:
        self.name = name
        self._n_rows = n_rows

    def retrieve(self, question_text: str) -> RetrievalResult:
        trace = {} if self._n_rows is None else {"n_rows": self._n_rows}
        return RetrievalResult(context="context", failure=None, trace=trace)


class ScriptedClient:
    """Stands in for `ChatClient`: replies with fixed text and a recorded latency of our choice."""

    def __init__(self, text: str, latency_s: float) -> None:
        self._text = text
        self._latency_s = latency_s
        self.timeouts: list[float | None] = []

    def complete(
        self,
        request: ChatRequest,
        *,
        run_id: str,
        question_id: str | None = None,
        strategy: str | None = None,
        timeout_s: float | None = None,
    ) -> ChatResponse:
        self.timeouts.append(timeout_s)
        return ChatResponse(
            text=self._text,
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            latency_s=self._latency_s,
            provider_response_id=None,
            finish_reason="stop",
            from_cache=False,
            created_at=datetime(2026, 10, 10),
        )


def _tier(spec: TierSpec, strategy: StubStrategy, client: Any, effort: str) -> LiveTier:
    settings = AttemptSettings("live-test", _pin(effort), None, False, None)
    return LiveTier(spec, strategy, settings, client)


def _cascade(
    t1: tuple[int, str, float], t2: tuple[str, float], *, policy: CascadePolicy | None = None
) -> tuple[LiveCascade, ScriptedClient, ScriptedClient]:
    """Tier 1 = (rows, reply, latency), tier 2 = (reply, latency)."""
    policy = policy or _policy()
    client1, client2 = ScriptedClient(t1[1], t1[2]), ScriptedClient(*t2)
    tiers = [
        _tier(policy.tiers[0], StubStrategy("stub-cypher", t1[0]), client1, "low"),
        _tier(policy.tiers[1], StubStrategy("stub-agent", None), client2, "high"),
    ]
    return LiveCascade("T1", policy, tiers, cutoff_s=CUTOFF_S), client1, client2


def _ask(cascade: LiveCascade) -> LiveAnswer:
    answer = cascade.ask(QUESTION)
    assert isinstance(answer, LiveAnswer)
    return answer


def test_an_accepted_tier_one_answer_never_calls_tier_two() -> None:
    cascade, _, client2 = _cascade((3, YES, 2.0), (YES, 9.0))

    answer = _ask(cascade)

    assert answer.answered_by == "t1" and answer.outcome is Outcome.ANSWERED
    assert [report.tier for report in answer.tiers] == ["t1"]
    assert answer.tiers[0].accepted and answer.tiers[0].n_rows == 3
    assert client2.timeouts == []


def test_zero_rows_escalates_and_tier_two_gets_the_cutoff_minus_tier_one_latency() -> None:
    cascade, client1, client2 = _cascade((0, YES, 7.0), (YES, 9.0))

    answer = _ask(cascade)

    assert answer.answered_by == "t2" and not answer.fell_back
    assert [report.accepted for report in answer.tiers] == [False, True]
    assert client1.timeouts == [pytest.approx(CUTOFF_S)]
    assert client2.timeouts == [pytest.approx(CUTOFF_S - 7.0, abs=0.5)]
    assert answer.latency_s == pytest.approx(16.0, abs=0.5)  # the tiers' latencies add up


def test_a_tier_two_parse_failure_falls_back_to_the_tier_one_answer() -> None:
    cascade, _, _ = _cascade((0, YES, 2.0), (GARBAGE, 3.0))

    answer = _ask(cascade)

    assert answer.fell_back and answer.answered_by == "t1"
    assert answer.outcome is Outcome.ANSWERED and answer.final_answer is not None
    assert answer.tiers[1].outcome is Outcome.PARSE_FAILURE


def test_latencies_summing_past_the_cutoff_make_the_answer_timed_out() -> None:
    cascade, _, _ = _cascade((0, YES, 70.0), (YES, 60.0))

    answer = _ask(cascade)

    assert answer.outcome is Outcome.TIMED_OUT
    assert answer.final_answer is None and answer.answered_by is None
    assert answer.latency_s > CUTOFF_S


def test_a_spent_cutoff_stops_before_tier_two_is_called() -> None:
    cascade, _, client2 = _cascade((0, YES, 125.0), (YES, 1.0))

    answer = _ask(cascade)

    assert answer.outcome is Outcome.TIMED_OUT and client2.timeouts == []
    assert [report.tier for report in answer.tiers] == ["t1"]


@pytest.mark.parametrize(
    ("tier_one", "tier_two"),
    [
        ((3, YES, 2.0), (YES, 4.0)),  # tier 1 accepted
        ((0, YES, 2.0), (YES, 4.0)),  # empty result, tier 2 accepted
        ((0, YES, 2.0), (GARBAGE, 4.0)),  # tier 2 fails, fallback
        ((2, '{"answer": null, "not_present": true}', 2.0), (YES, 4.0)),  # tier 1 abstains
    ],
)
def test_the_live_decision_is_the_offline_decide_on_the_same_signals(
    monkeypatch: pytest.MonkeyPatch,
    tier_one: tuple[int, str, float],
    tier_two: tuple[str, float],
) -> None:
    seen: list[tuple[Any, Decision]] = []

    def spy(policy: CascadePolicy, question_id: str, label: Any, signals: Any) -> Decision:
        decision = decide(policy, question_id, label, signals)
        seen.append((signals, decision))
        return decision

    monkeypatch.setattr(live_module, "decide", spy)
    cascade, _, _ = _cascade(tier_one, tier_two)

    answer = _ask(cascade)

    signals, decision = seen[0]
    again = decide(_policy(), QUESTION.question_id, None, signals)
    assert again == decision
    assert answer.answered_by == decision.answered_by
    assert answer.latency_s == decision.latency_s
    assert answer.cost_usd == pytest.approx(decision.cost_usd)
    assert tuple(r.tier for r in answer.tiers) == decision.tiers_tried


def test_a_replay_cache_miss_returns_needs_paid_call_and_sends_nothing(tmp_path: Path) -> None:
    transport = FakeTransport()
    client, cache = build_chat_client(
        pin=_pin("low"),
        allow_paid_calls=False,
        cache_path=tmp_path / "cache.sqlite",
        calls_log_path=tmp_path / "calls.jsonl",
        http_client=transport.as_httpx_client(),
    )
    policy = _policy()
    tiers = [
        _tier(policy.tiers[0], StubStrategy("stub-cypher", 1), client, "low"),
        _tier(policy.tiers[1], StubStrategy("stub-agent", None), ScriptedClient(YES, 1.0), "high"),
    ]

    result = LiveCascade("T1", policy, tiers).ask(QUESTION)
    cache.close()

    assert isinstance(result, NeedsPaidCall) and result.missing_tier == "t1"
    assert transport.requests == []


def test_a_pin_that_does_not_match_the_policy_is_refused() -> None:
    policy = _policy()
    wrong = _tier(policy.tiers[0], StubStrategy("stub-cypher", 1), ScriptedClient(YES, 1.0), "high")
    right = _tier(
        policy.tiers[1], StubStrategy("stub-agent", None), ScriptedClient(YES, 1.0), "high"
    )

    with pytest.raises(LivePolicyRefused, match="pin"):
        LiveCascade("T1", policy, [wrong, right])


def test_a_label_routing_policy_is_refused() -> None:
    routed = _policy(start_tier_by_label={"PATH": 1})
    tiers = [
        _tier(routed.tiers[0], StubStrategy("stub-cypher", 1), ScriptedClient(YES, 1.0), "low"),
        _tier(routed.tiers[1], StubStrategy("stub-agent", None), ScriptedClient(YES, 1.0), "high"),
    ]

    with pytest.raises(LivePolicyRefused, match="label"):
        LiveCascade("T1", routed, tiers)


def test_the_live_modules_import_no_gold_module() -> None:
    folder = Path(live_module.__file__).parent
    for name in ("live.py", "live_models.py", "live_build.py", "live_render.py"):
        tree = ast.parse((folder / name).read_text(encoding="utf-8"))
        imported = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ] + [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert [module for module in imported if "gold" in module] == [], name


def test_the_ask_command_prints_the_answer_and_the_tier_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cascade, _, _ = _cascade((0, YES, 2.0), (YES, 4.0))

    argv = ["ask", "--corpus", "T1", "--policy", "toy", "--run", "t1=x", "Is V-1 connected?"]
    main(argv, open_cascade=lambda _args: OpenedCascade(cascade, [], None))

    out = capsys.readouterr().out
    assert "answer: yes" in out and "answered by: t2" in out
    assert "t1" in out and "t2" in out and "accepted" in out


def test_the_ask_command_exits_2_on_a_cache_miss(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client, cache = build_chat_client(
        pin=_pin("low"),
        allow_paid_calls=False,
        cache_path=tmp_path / "cache.sqlite",
        calls_log_path=tmp_path / "calls.jsonl",
    )
    policy = _policy()
    tiers = [
        _tier(policy.tiers[0], StubStrategy("stub-cypher", 1), client, "low"),
        _tier(policy.tiers[1], StubStrategy("stub-agent", None), ScriptedClient(YES, 1.0), "high"),
    ]
    opened = OpenedCascade(LiveCascade("T1", policy, tiers), [cache], None)
    argv = ["ask", "--corpus", "T1", "--policy", "toy", "--run", "t1=x", "--replay-only"]
    argv.append("Is V-1 connected?")

    with pytest.raises(SystemExit) as exit_info:
        main(argv, open_cascade=lambda _args: opened)

    assert exit_info.value.code == 2
    assert "without --replay-only" in capsys.readouterr().err


def test_free_text_questions_get_a_stable_id() -> None:
    first = FreeTextQuestion.from_text("What is V-1?")
    assert first == FreeTextQuestion.from_text("What is V-1?")
    assert first.question_id != FreeTextQuestion.from_text("What is V-2?").question_id


def _ask_namespace(*extra: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_ask_arguments(parser)
    return parser.parse_args(["--corpus", "T1", "--policy", "toy", "--run", "t1=x", *extra])


def test_ask_allows_paid_calls_with_a_two_dollar_cap_by_default() -> None:
    args = _ask_namespace("question")

    assert args.replay_only is False and args.session_cap_usd == 2.0


def test_ask_replay_only_and_the_cap_flag_are_parsed() -> None:
    args = _ask_namespace("--replay-only", "--session-cap-usd", "0.5", "question")

    assert args.replay_only is True and args.session_cap_usd == 0.5
