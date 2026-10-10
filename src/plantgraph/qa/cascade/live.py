"""Answer one question through a cascade policy, tier by tier, without scoring it.

The decisions are the offline report's own: `walk_question` names the next tier to run and
`decide` settles the result, so a live question gets the tier, latency and cost the report
would give the same signals. The cascade's cutoff C is carried across the tiers: a tier gets
C minus the latency the earlier tiers already used. This module reads no gold.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import CacheMiss, ModelPin, ProviderError
from plantgraph.qa.cascade.accept import walk_question
from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall, TierReport
from plantgraph.qa.cascade.models import CascadePolicy, Decision, Signals, TierSpec
from plantgraph.qa.cascade.policy import decide
from plantgraph.qa.cascade.signals import extract_signals
from plantgraph.qa.harness.attempt import run_unscored
from plantgraph.qa.harness.attempt_models import AttemptSettings, UnscoredAnswer
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import Outcome
from plantgraph.qa.strategies.base import AskedQuestion, Strategy

#: A provider error is asked again once, as the harness does, before it counts as an outcome.
_PROVIDER_ATTEMPTS = 2


class LivePolicyRefused(ValueError):
    """The policy or a tier cannot be run live; the message says which and why."""


@dataclass(frozen=True)
class LiveTier:
    """One tier ready to run: its spec, its strategy, its answer settings and its client."""

    spec: TierSpec
    strategy: Strategy
    settings: AttemptSettings
    client: ChatClient


@dataclass(frozen=True)
class _TierRun:
    """A tier that ran: its answer and the signals the policy reads from it."""

    tier: LiveTier
    answer: UnscoredAnswer
    signals: Signals


class LiveCascade:
    """Runs a policy over one corpus. Strategies are built once and reused across questions."""

    def __init__(
        self,
        corpus_id: str,
        policy: CascadePolicy,
        tiers: Sequence[LiveTier],
        *,
        cutoff_s: float = DEFAULT_CUTOFF_S,
        guard: SpendGuard | None = None,
        notice: str | None = None,
    ) -> None:
        """`notice` marks a derived policy: why a tier of the evaluated policy is missing.

        Raises:
            LivePolicyRefused: label routing, tiers that do not match the policy, or a pin
                whose hash differs from the policy's `pin_sha256`.
        """
        check_runnable(policy, tiers)
        self._corpus_id = corpus_id
        self._policy = policy
        self._tiers = {tier.spec.name: tier for tier in tiers}
        self._cutoff_s = cutoff_s
        self._guard = guard or SpendGuard(None)
        self._notice = notice

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        """Run tiers until the policy settles the question or the cutoff is spent.

        Returns `NeedsPaidCall` when a model call is not in the cache and the clients may not
        pay: nothing is sent. Raises `SpendCapReached` when the guard's cap would be passed.
        """
        runs: list[_TierRun] = []
        signals: dict[str, dict[str, Signals]] = {}
        used_s = 0.0
        while True:
            walk = walk_question(self._policy, asked.question_id, None, signals)
            if walk.missing_tier is None:
                break
            remaining_s = self._cutoff_s - used_s
            if remaining_s <= 0:
                return self._assemble(asked, runs, decision=None, accepted=None)
            try:
                run = self._run_tier(self._tiers[walk.missing_tier], asked, remaining_s)
            except CacheMiss as miss:
                return NeedsPaidCall(missing_tier=walk.missing_tier, reason=str(miss))
            runs.append(run)
            signals[run.tier.spec.name] = {asked.question_id: run.signals}
            used_s += run.signals.latency_s
        decision = decide(self._policy, asked.question_id, None, signals)
        return self._assemble(asked, runs, decision, accepted=walk.accepted)

    def _run_tier(self, tier: LiveTier, asked: AskedQuestion, remaining_s: float) -> _TierRun:
        # a fresh meter per tier: its deadline is what is left of C, counted in recorded time
        meter = UsageMeter(self._guard, deadline_s=remaining_s)
        settings = replace(tier.settings, question_deadline_s=remaining_s)
        answer = _answer_with_retry(tier, asked, settings, meter)
        # `correct=False` is a placeholder: signals never read it, and nothing here is scored
        row = answer.as_row(settings, asked.question_id, 0, correct=False, f1=None)
        signals = extract_signals(
            row, tier.spec.name, settings.answer_pin, None, answer.local_compute_s
        )
        return _TierRun(tier, answer, signals)

    def _assemble(
        self,
        asked: AskedQuestion,
        runs: list[_TierRun],
        decision: Decision | None,
        accepted: str | None,
    ) -> LiveAnswer:
        """Fold the tier runs and the decision into the answer the caller shows."""
        latency_s = sum(run.signals.latency_s for run in runs)
        # no decision means the cutoff was spent; the report scores a late answer TIMED_OUT too
        late = decision is None or latency_s > self._cutoff_s
        answered_by = None if decision is None or late else decision.answered_by
        winner = next((r for r in runs if r.tier.spec.name == answered_by), None)
        reports = tuple(_tier_report(run, accepted) for run in runs)
        return LiveAnswer(
            question_text=asked.text,
            corpus_id=self._corpus_id,
            answer_type=asked.answer_type,
            policy=self._policy.name,
            evaluated_policy=self._notice is None,
            notice=self._notice,
            outcome=Outcome.TIMED_OUT if late else _outcome(winner, runs),
            final_answer=winner.answer.final_answer if winner else None,
            answered_by=answered_by,
            fell_back=answered_by is not None and accepted is None,
            tiers=reports,
            latency_s=latency_s,
            wall_s=sum(r.wall_s for r in reports),
            cost_usd=sum(r.cost_usd for r in reports),
            spent_usd=sum(r.spent_usd for r in reports),
            from_cache=all(r.n_cached == r.n_calls for r in reports),
            trace_sheets=_trace_sheets(winner),
        )


def refuse_label_routing(policy: CascadePolicy) -> None:
    """Raise `LivePolicyRefused` for a policy that routes tiers by need label."""
    if policy.start_tier_by_label or policy.last_tier_by_label:
        raise LivePolicyRefused(
            "expected a policy without label routing (a free-text question has no need "
            f"label), found start/last_tier_by_label in {policy.name!r}"
        )


def check_pin(spec: TierSpec, pin: ModelPin) -> None:
    """Raise `LivePolicyRefused` unless `pin` is the one the policy names for the tier."""
    found = pin.pin_hash()
    if found != spec.pin_sha256:
        raise LivePolicyRefused(
            f"expected tier {spec.name!r} to run under pin {spec.pin_sha256}, "
            f"found a pin hashing to {found}"
        )


def check_runnable(policy: CascadePolicy, tiers: Sequence[LiveTier]) -> None:
    """Refuse label routing, tiers that differ from the policy's, and any pin mismatch."""
    refuse_label_routing(policy)
    names = [tier.spec.name for tier in tiers]
    expected = [spec.name for spec in policy.tiers]
    if names != expected:
        raise LivePolicyRefused(f"expected tiers {expected} for {policy.name!r}, found {names}")
    for tier in tiers:
        check_pin(tier.spec, tier.settings.answer_pin)


def _answer_with_retry(
    tier: LiveTier, asked: AskedQuestion, settings: AttemptSettings, meter: UsageMeter
) -> UnscoredAnswer:
    """A provider error is retried once; one that survives becomes a `PROVIDER_ERROR` answer."""
    started = time.monotonic()
    error: ProviderError | None = None
    for _ in range(_PROVIDER_ATTEMPTS):
        result = run_unscored(tier.strategy, asked, settings, tier.client, meter)
        if not isinstance(result, ProviderError):
            return result
        error = result
    return _provider_error_answer(tier.strategy.name, error, time.monotonic() - started)


def _provider_error_answer(
    strategy_name: str, error: ProviderError | None, wall_s: float
) -> UnscoredAnswer:
    # cost 0.0, not None: the signals refuse a missing cost, and no answer was billed
    return UnscoredAnswer(
        strategy=strategy_name,
        outcome=Outcome.PROVIDER_ERROR,
        final_answer=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=0.0,
        latency_s=0.0,
        context_chars=0,
        trace={"provider_error": str(error)},
        retrieval_usage=None,
        wall_s=wall_s,
        local_compute_s=0.0,
        spent_usd=0.0,
        final_call_cached=None,
    )


def _outcome(winner: _TierRun | None, runs: Sequence[_TierRun]) -> Outcome:
    """The answering tier's outcome; with no answer, the last tier's (why the last try failed)."""
    return (winner or runs[-1]).answer.outcome


def _tier_report(run: _TierRun, accepted: str | None) -> TierReport:
    answer, usage = run.answer, run.answer.retrieval_usage
    final_calls = 0 if answer.final_call_cached is None else 1
    retrieval = answer.trace.get("retrieval")
    agent = retrieval if isinstance(retrieval, dict) else {}
    n_steps, stop_reason = agent.get("n_steps"), agent.get("stop_reason")
    return TierReport(
        tier=run.tier.spec.name,
        strategy=run.tier.spec.strategy,
        model_id=run.tier.settings.answer_pin.model_id,
        outcome=answer.outcome,
        accepted=run.tier.spec.name == accepted,
        latency_s=run.signals.latency_s,
        wall_s=answer.wall_s,
        cost_usd=run.signals.cost_usd,
        spent_usd=answer.spent_usd,
        n_calls=(usage.n_calls if usage else 0) + final_calls,
        n_cached=(usage.n_cached if usage else 0) + int(bool(answer.final_call_cached)),
        n_steps=n_steps if isinstance(n_steps, int) else None,
        stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        n_rows=run.signals.n_rows,
    )


def _trace_sheets(winner: _TierRun | None) -> tuple[str, ...]:
    """The sheets the answering tier says it read (`trace.retrieval.routed_sheets`)."""
    if winner is None:
        return ()
    retrieval = winner.answer.trace.get("retrieval")
    sheets = retrieval.get("routed_sheets") if isinstance(retrieval, dict) else None
    return tuple(str(s) for s in sheets) if isinstance(sheets, list) else ()
