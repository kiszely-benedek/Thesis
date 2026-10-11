"""Answer one repeat of the EX01 run: one client and cache, one strategy per arm that can run."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from plantgraph.llm.models import ProviderError
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.exp0001.ex01_arms import build_arm_strategy
from plantgraph.qa.exp0001.ex01_models import (
    CASCADE_ARM,
    Ex01AnswerRow,
    Ex01Question,
    Ex01RunConfig,
)
from plantgraph.qa.exp0001.ex01_rows import last_provider, provider_error_row, row_from_answer
from plantgraph.qa.exp0001.ex01_store import Ex01RunDir, RowKey
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.attempt import run_unscored, sender_for_run
from plantgraph.qa.harness.attempt_models import AttemptSettings, UnscoredAnswer
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME

#: The primer is on for every arm, as in EXP-0002 (ChatP&ID had none: a stated difference).
PRIMER = True


def spend_guard(
    cap_usd: float | None,
    allow_paid_calls: bool,
    cost_per_question_usd: float,
    rows: list[Ex01AnswerRow],
) -> SpendGuard:
    """A guard seeded with what earlier invocations spent (derived cascade rows are not spend)."""
    costs = [row.cost_usd or 0.0 for row in rows if row.arm != CASCADE_ARM]
    return SpendGuard(
        cap_usd if allow_paid_calls else None,
        recorded_usd=sum(costs),
        max_question_usd=max(costs, default=0.0),
        estimate_usd=cost_per_question_usd,
    )


class RepeatWorker:
    """Answers the pending (arm, question) pairs of one repeat, one at a time."""

    def __init__(
        self,
        config: Ex01RunConfig,
        repeat: int,
        out_dir: Path,
        allow_paid_calls: bool,
        view: NetworkxGraphView,
        source: CypherSource | None,
        http_client: httpx2.Client | None,
        guard: SpendGuard,
        done: set[RowKey],
    ) -> None:
        self._config, self._repeat, self._guard, self._done = config, repeat, guard, done
        run_dir = Ex01RunDir(out_dir)
        self._calls_path = run_dir.calls_path
        self._client, self._cache = build_chat_client(
            pin=next(iter(config.arms.values())).pin,  # only its backend matters here
            allow_paid_calls=allow_paid_calls,
            cache_path=run_dir.cache_path(repeat),
            calls_log_path=run_dir.calls_path,
            http_client=http_client,
        )
        self._client.on_late_response = guard.charge_late  # an abandoned call's money still counts
        self._strategies = self._build_strategies(view, source)
        #: Rows this worker has appended (kept up to date, so a spend-cap stop still counts them).
        self.written = 0

    def close(self) -> None:
        """Close this repeat's cache."""
        self._cache.close()

    def _build_strategies(
        self, view: NetworkxGraphView, source: CypherSource | None
    ) -> dict[str, Strategy]:
        send_for = sender_for_run(self._client, self._config.run_id)
        strategies: dict[str, Strategy] = {}
        for name, arm in self._config.arms.items():
            if arm.not_applicable is not None:
                continue
            cypher_source = source if arm.strategy in PROFILE_OF_NAME else None
            strategies[name] = build_arm_strategy(
                arm, view, send_for(arm.strategy), cypher_source, PRIMER
            )
        return strategies

    def answer_all(
        self, questions: list[Ex01Question], run_dir: Ex01RunDir, progress: Callable[[str], None]
    ) -> None:
        """Answer every pending (arm, question) of this repeat, counting rows in `written`.

        Raises:
            SpendCapReached: the next question could take the run past its cap.
        """
        for name, strategy in self._strategies.items():
            for question in questions:
                if (name, question.question_id, self._repeat) in self._done:
                    continue
                row = self._answer_one(name, strategy, question)
                run_dir.append_row(row)
                self.written += 1
                progress(
                    f"repeat {self._repeat} {name} {question.question_id}: {row.outcome.value}"
                )

    def _answer_one(self, name: str, strategy: Strategy, question: Ex01Question) -> Ex01AnswerRow:
        arm = self._config.arms[name]
        settings = AttemptSettings(self._config.run_id, arm.pin, None, PRIMER, arm.deadline_s)
        answer = self._try_twice(strategy, question, settings, arm.deadline_s)
        qid = question.question_id
        if isinstance(answer, ProviderError):
            return provider_error_row(answer, settings, qid=qid, arm=name, repeat=self._repeat)
        provider = last_provider(self._calls_path, qid, strategy.name)
        return row_from_answer(
            answer, settings, qid=qid, arm=name, repeat=self._repeat, provider=provider
        )

    def _try_twice(
        self,
        strategy: Strategy,
        question: Ex01Question,
        settings: AttemptSettings,
        deadline_s: float,
    ) -> UnscoredAnswer | ProviderError:
        """One retry after a provider error, as the harness does; the second error is recorded."""
        answer = self._try_once(strategy, question, settings, deadline_s)
        if isinstance(answer, ProviderError):
            answer = self._try_once(strategy, question, settings, deadline_s)
        return answer

    def _try_once(
        self,
        strategy: Strategy,
        question: Ex01Question,
        settings: AttemptSettings,
        deadline_s: float,
    ) -> UnscoredAnswer | ProviderError:
        reservation = self._guard.reserve()  # raises SpendCapReached when the cap could be passed
        meter = UsageMeter(self._guard, reservation=reservation, deadline_s=deadline_s)
        try:
            return run_unscored(strategy, question, settings, self._client, meter)
        finally:
            self._guard.release(reservation, meter.spent_usd)
