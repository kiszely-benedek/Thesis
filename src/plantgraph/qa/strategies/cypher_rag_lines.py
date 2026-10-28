"""`cypher_rag_lines`: CypherRAG for the tuned V2T system (ADR-0061, `qa-tuning-v2.md` QT-4).

Same idea as `CypherRag` (an LLM writes one Cypher query, its rows are the context), with four
additions, all kept out of `CypherRag` so F1's strategy stays untouched:

1. A prompt with query-shape rules (`cypher_query_v2t.txt`) over the `plant_lines` graph.
2. **One repair round.** A query that fails with a syntax, timeout, memory or write-clause error
   is sent back to the model once, with the database's message and a fixed hint.
3. A free **tag existence check**: which tags the question names exist (`tag_check.py`).
4. Every execution goes through `GuardedCypherSource`, a client-side wall-clock limit, because
   the server once ignored its own timeout (`cypher_guard.py`).

The model sees only `question_text` and the schema text: retrieval sees only the question.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.llm.models import ChatMessage, ChatRequest, ChatResponse, ContextOverflow, ModelPin
from plantgraph.qa.cypher import CypherExecutionError, CypherResult, CypherSource, WriteClauseError
from plantgraph.qa.cypher_guard import HANG_GRACE_S, CypherHung, GuardedCypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.models import Outcome, RetrievalResult
from plantgraph.qa.primer import fill_primer_slot
from plantgraph.qa.strategies.cypher_rag import LINES_NAME, extract_query, format_context
from plantgraph.qa.tag_check import (
    TAG_CHECK_TIMEOUT_S,
    format_tag_note,
    split_found_missing,
    tag_like_words,
    tag_lookup_query,
)

_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
_QUERY_TEMPLATE = _PROMPTS / "cypher_query_v2t.txt"
_REPAIR_TEMPLATE = _PROMPTS / "cypher_repair_v2t.txt"

#: How a query ended badly. `hung` (the server ignored its timeout), `overflow` (prompt too long)
#: and `empty` (no query in the reply) are not repaired: more of the same would not help.
FailureKind = Literal["syntax", "timeout", "memory", "write", "hung", "overflow", "empty"]
_REPAIRABLE: frozenset[FailureKind] = frozenset({"syntax", "timeout", "memory", "write"})

#: How much of the database's message goes back to the model.
_ERROR_CHARS = 400

#: One fixed hint per repairable failure class (the design's "fixed hint per error class").
_HINTS: dict[str, str] = {
    "syntax": "Fix the syntax error. Write the query only, with no text or extra token around it.",
    "timeout": (
        "The query did not finish in {timeout_s:g} s. Rewrite it so that it does not enumerate "
        "paths: follow the query shape rules above (DISTINCT end items, shortestPath, EXISTS)."
    ),
    "memory": (
        "The query needed more memory than the database allows. Rewrite it so that it does not "
        "enumerate paths and returns only the tags: follow the query shape rules above."
    ),
    "write": "The query contained a write clause, which is not allowed. Write a read-only query.",
}


class CypherAttempt(BaseModel):
    """One query-writing call and what running its query did."""

    model_config = ConfigDict(frozen=True)

    query: str
    #: Cost and size of the writing call (`None` when the call overflowed the context).
    call: dict[str, Any] | None
    result: CypherResult | None = None
    error: str = ""
    failure: FailureKind | None = None

    @property
    def repairable(self) -> bool:
        """True when a failed attempt is worth one more round."""
        return self.failure in _REPAIRABLE


def classify_failure(error: Exception) -> FailureKind:
    """The failure class of a refused or aborted query, from the exception and its message."""
    if isinstance(error, WriteClauseError):
        return "write"
    if isinstance(error, CypherHung):
        return "hung"
    message = str(error)
    if "TransactionTimedOut" in message:
        return "timeout"
    if "MemoryPool" in message or "OutOfMemory" in message:
        return "memory"
    return "syntax"  # any other refusal is, in practice, a malformed query


def render_query_prompt(*, schema_text: str, question_text: str, primer: bool = False) -> str:
    """The first query-writing prompt (`cypher_query_v2t.txt`)."""
    template = fill_primer_slot(_QUERY_TEMPLATE.read_text(encoding="utf-8"), primer=primer)
    return template.replace("<<SCHEMA>>", schema_text).replace("<<QUESTION>>", question_text)


def render_repair_prompt(prompt: str, failed: CypherAttempt, *, timeout_s: float) -> str:
    """The repair prompt: the first prompt, the failed query, the database's message and a hint."""
    if failed.failure not in _REPAIRABLE:
        raise ValueError(
            f"expected a repairable failure {sorted(_REPAIRABLE)}, found {failed.failure}"
        )
    hint = _HINTS[str(failed.failure)].format(timeout_s=timeout_s)
    return (
        _REPAIR_TEMPLATE.read_text(encoding="utf-8")
        .replace("<<QUERY>>", failed.query)
        .replace("<<ERROR>>", failed.error[:_ERROR_CHARS])
        .replace("<<HINT>>", hint)
        .replace("<<PROMPT>>", prompt)  # last: the prompt holds the question, which is free text
    )


class CypherRagLines:
    """Writes, runs and (once) repairs a Cypher query over the `plant_lines` store."""

    name = LINES_NAME
    profile = "plant_lines"

    def __init__(
        self,
        source: CypherSource,
        pin: ModelPin,
        send: SendChatRequest,
        *,
        timeout_s: float,
        row_cap: int,
        primer: bool = False,
        hang_grace_s: float = HANG_GRACE_S,
    ) -> None:
        self._source = GuardedCypherSource(source, hang_grace_s=hang_grace_s)
        self._pin = pin
        self._send = send
        self._timeout_s = timeout_s
        self._row_cap = row_cap
        self._primer = primer

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Check tags, write a query, repair it once if it failed; a failure is returned.

        A `ProviderError` or `CacheMiss` from the LLM call is not caught: those are the
        harness's to handle, as for every other call.
        """
        tag_note, tag_trace = self._check_tags(question_text)
        prompt = render_query_prompt(
            schema_text=self._source.schema_text(),
            question_text=question_text,
            primer=self._primer,
        )
        attempts = [self._attempt(prompt)]
        if attempts[0].repairable:
            repair = render_repair_prompt(prompt, attempts[0], timeout_s=self._timeout_s)
            attempts.append(self._attempt(repair))
        trace = {**_trace_of(attempts), **tag_trace}
        last = attempts[-1]
        if last.result is None:
            return RetrievalResult(
                context=None,
                failure=Outcome.RETRIEVAL_ERROR,
                trace={**trace, "cypher_error": last.error},
            )
        body = format_context(last.query, last.result, self._row_cap, self._source.label_names())
        context = f"{tag_note}\n\n{body}" if tag_note else body
        trace.update(
            n_rows=len(last.result.rows),
            truncated=last.result.truncated,
            empty_result=not last.result.rows,
        )
        return RetrievalResult(context=context, failure=None, trace=trace)

    def _attempt(self, prompt: str) -> CypherAttempt:
        """One writing call, then (if it produced a query) one guarded execution."""
        request = ChatRequest(
            pin=self._pin, messages=[ChatMessage(role="user", content=prompt)], purpose="cypher"
        )
        try:
            response = self._send(request)
        except ContextOverflow as error:
            message = f"the query-writing prompt overflowed: {error}"
            return CypherAttempt(query="", call=None, error=message, failure="overflow")
        query, call = extract_query(response.text), _usage(response)
        if not query:
            return CypherAttempt(
                query="", call=call, error="the model's reply held no query", failure="empty"
            )
        try:
            result = self._source.run_cypher(query, self._timeout_s, self._row_cap)
        except (WriteClauseError, CypherExecutionError) as error:
            return CypherAttempt(
                query=query, call=call, error=str(error), failure=classify_failure(error)
            )
        return CypherAttempt(query=query, call=call, result=result)

    def _check_tags(self, question_text: str) -> tuple[str, dict[str, Any]]:
        """The note for the context and its trace; a failed lookup is recorded, not hidden."""
        tags = tag_like_words(question_text)
        if not tags:
            return "", {}
        try:
            result = self._source.run_cypher(
                tag_lookup_query(tags), TAG_CHECK_TIMEOUT_S, self._row_cap
            )
        except (WriteClauseError, CypherExecutionError) as error:
            return "", {"tag_check_error": str(error)}
        found, missing = split_found_missing(tags, result.rows)
        return format_tag_note(found, missing), {"tags_found": found, "tags_missing": missing}


def _trace_of(attempts: list[CypherAttempt]) -> dict[str, Any]:
    """The trace: the last query and the summed calls (as `CypherRag`), plus every attempt."""
    last = attempts[-1]
    return {
        "cypher": last.query,
        "cypher_call": _summed_calls([a.call for a in attempts if a.call is not None]),
        "repaired": len(attempts) > 1,
        "attempts": [
            {"cypher": a.query, "cypher_call": a.call, "error": a.error, "failure": a.failure}
            for a in attempts
        ],
    }


def _summed_calls(calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Total cost, tokens and latency of the writing calls (so a repair is not lost)."""
    if not calls:
        return None
    return {
        "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
        "completion_tokens": sum(c["completion_tokens"] for c in calls),
        "cost_usd": _summed_cost([c["cost_usd"] for c in calls]),
        "latency_s": sum(c["latency_s"] for c in calls),
        "from_cache": all(c["from_cache"] for c in calls),
    }


def _summed_cost(costs: list[float | None]) -> float | None:
    """The total of the known costs; `None` when no call reported one."""
    known = [cost for cost in costs if cost is not None]
    return sum(known) if known else None


def _usage(response: ChatResponse) -> dict[str, Any]:
    return {
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "cost_usd": response.cost_usd,
        "latency_s": response.latency_s,
        "from_cache": response.from_cache,
    }
