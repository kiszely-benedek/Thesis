"""Per-question accounting of every model call, so a question's cost is its total (design §10.1).

Retrieval strategies make their own model calls (CypherRAG's query, a router
fallback) through a sender the harness gives them. The meter sits behind that
sender: it learns which question is being answered, tallies the retrieval-side
calls into a `CallUsage`, and times every call so the rest of the wall time can
be reported as local compute.

With a question deadline it also keeps the question's **recorded** call time (the
`latency_s` stored with each response, cached or live), never the clock: a replay then
reaches the same budget decisions as the live run, and a timeout reproduces exactly.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from plantgraph.llm.models import (
    ChatResponse,
    QuestionDeadline,
    RequestTimedOut,
    reserved_for_final_s,
)
from plantgraph.qa.harness.spend_cap import Reservation, SpendGuard
from plantgraph.qa.models import CallUsage


class UsageMeter:
    """Tallies one question: `begin`, then `record` per call, then `end`.

    One meter per work item, so items running at once never share a tally.
    """

    def __init__(
        self,
        guard: SpendGuard,
        clock: Callable[[], float] = time.monotonic,
        reservation: Reservation | None = None,
        deadline_s: float | None = None,
    ) -> None:
        self.question_id: str | None = None
        #: Seconds spent inside model calls, retrieval-side and final, for the current question.
        self.seconds_in_calls = 0.0
        #: Cost of the current question's calls that missed the cache, final call included.
        self.spent_usd = 0.0
        self._guard = guard
        self._reservation = reservation  # this item's share of the cap, if it has one
        self._clock = clock
        self._responses: list[ChatResponse] = []
        self._deadline_s = deadline_s
        self._recorded_elapsed_s = 0.0
        self._n_abandoned = 0

    @property
    def recorded_elapsed_s(self) -> float:
        """Sum of the recorded latencies of this question's calls so far (timeouts included)."""
        return self._recorded_elapsed_s

    @property
    def remaining_s(self) -> float | None:
        """Seconds of the question's budget not yet spent, or `None` without a deadline."""
        if self._deadline_s is None:
            return None
        return self._deadline_s - self._recorded_elapsed_s

    def begin(self, question_id: str) -> None:
        """Start a question; retrieval-side calls made from now on are logged under its id."""
        self.question_id = question_id
        self.seconds_in_calls = 0.0
        self.spent_usd = 0.0
        self._responses = []
        self._recorded_elapsed_s = 0.0
        self._n_abandoned = 0

    def timed_call(
        self, call: Callable[[float | None], ChatResponse], *, is_final: bool
    ) -> ChatResponse:
        """Run one model call behind the deadline and the spend guard, then `record` it.

        `call` receives the time it may take (`None` without a deadline). A retrieval-side
        call inside `keeping_in_reserve` gets that much less, so the final call keeps it.

        Raises:
            QuestionDeadline: the budget is already spent; no call is started.
            RequestTimedOut: the call outlived its budget (counted before it is re-raised).
        """
        timeout_s = self._remaining_s(reserve_s=0.0 if is_final else reserved_for_final_s())
        self._guard.check_before_call(self._reservation)
        started = self._clock()
        try:
            response = call(timeout_s)
        except RequestTimedOut as timeout:
            self.seconds_in_calls += self._clock() - started
            self._recorded_elapsed_s += timeout.latency_s
            self._n_abandoned += 1
            raise
        self.record(response, self._clock() - started, is_final=is_final)
        return response

    def _remaining_s(self, reserve_s: float) -> float | None:
        """The budget left for the next call, minus `reserve_s`; raises when none is left."""
        if self._deadline_s is None:
            return None
        remaining = self._deadline_s - self._recorded_elapsed_s - reserve_s
        if remaining <= 0:
            raise QuestionDeadline(
                f"expected recorded call time under the {self._deadline_s:g} s deadline, "
                f"found {self._recorded_elapsed_s:g} s already spent"
            )
        return remaining

    def record(self, response: ChatResponse, seconds_in_call: float, *, is_final: bool) -> None:
        """Count a call's time and spend; only retrieval-side calls enter the `CallUsage`."""
        self.seconds_in_calls += seconds_in_call
        self._recorded_elapsed_s += response.latency_s
        self._guard.add(response)
        if not response.from_cache:
            self.spent_usd += response.cost_usd or 0.0
        if not is_final:
            self._responses.append(response)

    def end(self) -> CallUsage:
        """The retrieval-side calls of the question that was begun."""
        responses = self._responses
        missing = [r for r in responses if r.cost_usd is None]
        return CallUsage(
            n_calls=len(responses),
            prompt_tokens=sum(r.prompt_tokens for r in responses),
            completion_tokens=sum(r.completion_tokens for r in responses),
            cost_usd=None if missing else sum(r.cost_usd or 0.0 for r in responses),
            n_cost_missing=len(missing),
            llm_latency_s=sum(r.latency_s for r in responses),
            n_abandoned=self._n_abandoned,
            n_cached=sum(r.from_cache for r in responses),
            spent_usd=sum(r.cost_usd or 0.0 for r in responses if not r.from_cache),
        )


class TimingRow(BaseModel):
    """One line of `timings.jsonl`: the run-dependent numbers kept out of `answers.jsonl`."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    strategy: str
    repeat: int
    #: Wall time of retrieval and answering minus the time inside model calls.
    local_compute_s: float
    #: Cost of this question's calls that missed the cache, retrieval-side and final.
    spent_usd: float
    n_cached_retrieval_calls: int
