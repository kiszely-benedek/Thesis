"""D4: a chat model reads the pair card and says whether the two occurrences are one item.

Score is 1.0 for "same", 0.0 otherwise, and there is no threshold. A cache miss in cache-only mode
(`CacheMiss`) and a reached spend cap (`SpendCapReached`) propagate: the run stops, never guesses.
"""

from __future__ import annotations

from plantgraph.exp0004.d4_prompt import build_request, parse_verdict
from plantgraph.exp0004.d4_stats import PairCall
from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ModelPin
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.resolution.identity_candidates import CandidatePair
from plantgraph.resolution.identity_deciders import PairDecision


class ChatPairDecider:
    """A `PairDecider` backed by one pinned chat model; keeps a record of every call it made."""

    name = "d4"

    def __init__(self, client: ChatClient, pin: ModelPin, guard: SpendGuard, run_id: str) -> None:
        self._client = client
        self._pin = pin
        self._guard = guard
        self._run_id = run_id
        self.calls: list[PairCall] = []

    def decide(self, pair: CandidatePair) -> PairDecision:
        """Ask about the pair's card (and nothing else: no tags, ids or gold)."""
        call = self.ask(pair.card)
        accepted = call.same_item is True  # a parse failure is "not accepted"
        return PairDecision(score=1.0 if accepted else 0.0, accept=accepted)

    def ask(self, card: str) -> PairCall:
        """Send one card through the cache and the spend guard; record and return the call."""
        self._guard.check_before_call()  # stop before the call if the cap could be reached
        response = self._client.complete(
            build_request(self._pin, card), run_id=self._run_id, strategy="d4"
        )
        self._guard.add(response)  # cache hits cost 0 here
        verdict = parse_verdict(response.text)
        call = PairCall(
            card=card,
            answer_text=response.text,
            same_item=None if verdict is None else verdict.same_item,
            reason=None if verdict is None else verdict.reason,
            parse_ok=verdict is not None,
            from_cache=response.from_cache,
            cost_usd=response.cost_usd,
            latency_s=response.latency_s,
        )
        self.calls.append(call)
        return call
