"""The hard spend cap of a paid run: stop before money could pass `--max-spend-usd`.

Only money actually spent counts. A response served from the cache costs 0 here,
even though its recorded `cost_usd` is what the call cost when first made.
"""

from __future__ import annotations

from plantgraph.llm.models import ChatResponse


class SpendCapReached(Exception):
    """The next model call or question could take the run's cost to its cap."""


class SpendGuard:
    """Tracks a run's cumulative spend and refuses calls that could exceed `cap_usd`.

    Args:
        cap_usd: the hard cap; `None` disables the guard (replay runs spend nothing).
        recorded_usd: cost already recorded in `answers.jsonl` by earlier invocations.
        max_question_usd: the dearest question recorded on disk so far.
        estimate_usd: the user's `--cost-per-question-usd`, used if it is larger.
    """

    def __init__(
        self,
        cap_usd: float | None,
        *,
        recorded_usd: float = 0.0,
        max_question_usd: float = 0.0,
        estimate_usd: float | None = None,
    ) -> None:
        self.cap_usd = cap_usd
        self._spent_usd = recorded_usd
        self._max_question_usd = max_question_usd
        self._estimate_usd = estimate_usd or 0.0
        self._max_call_usd = 0.0  # dearest single call made in this invocation

    @property
    def spent_usd(self) -> float:
        """Recorded cost of earlier invocations plus what this one has spent."""
        return self._spent_usd

    def add(self, response: ChatResponse) -> None:
        """Count a finished call; a cache hit costs nothing."""
        if response.from_cache:
            return
        cost = response.cost_usd or 0.0
        self._spent_usd += cost
        self._max_call_usd = max(self._max_call_usd, cost)

    def end_question(self, spent_usd: float) -> None:
        """Remember what the question really spent (0 if cached), for the next projection."""
        self._max_question_usd = max(self._max_question_usd, spent_usd)

    def check_before_question(self) -> None:
        """Raise if one more question of the dearest size seen could pass the cap."""
        expected = max(self._max_question_usd, self._estimate_usd)
        self._check(expected, "the next question")

    def check_before_call(self) -> None:
        """Raise if one more call of the dearest size seen could pass the cap."""
        self._check(self._max_call_usd, "the next call")

    def _check(self, expected_usd: float, what: str) -> None:
        if self.cap_usd is None:
            return
        if self._spent_usd + expected_usd >= self.cap_usd:
            raise SpendCapReached(
                f"{what} (expected up to {expected_usd:.6f} USD) could reach or pass the run's "
                f"cap of {self.cap_usd:.6f} USD; {self._spent_usd:.6f} USD spent so far"
            )
