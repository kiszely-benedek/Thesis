"""CypherRAG: an LLM writes one database query, its rows are the context (`qa-system.md` §7).

ChatP&ID's second strategy (Algorithm 4). The question and the schema text go
to the model, which writes a single Cypher query (Neo4j's graph query
language); the query runs read-only and its rows, with the query itself, become
the context for the shared final-answer step. One attempt only: a query that
fails ends the question as `RETRIEVAL_ERROR` and no final call is made (D7).

The LLM sees `question_text` and the schema text, nothing else, so the
fairness rule "retrieval sees only the question" holds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from plantgraph.llm.models import ChatMessage, ChatRequest, ChatResponse, ContextOverflow, ModelPin
from plantgraph.qa.cypher import CypherExecutionError, CypherResult, CypherSource, WriteClauseError
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.models import Outcome, RetrievalResult

_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "prompts" / "cypher_query.txt"
_SCHEMA_PLACEHOLDER = "<<SCHEMA>>"
_QUESTION_PLACEHOLDER = "<<QUESTION>>"

#: A reply wrapped in a markdown fence despite the instruction not to.
_FENCED = re.compile(r"```[A-Za-z]*\s*(.*?)```", re.DOTALL)


def render_cypher_request(*, pin: ModelPin, schema_text: str, question_text: str) -> ChatRequest:
    """The one prompt that asks the LLM for a Cypher query (`cypher_query.txt`)."""
    rendered = (
        _TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace(_SCHEMA_PLACEHOLDER, schema_text)
        .replace(_QUESTION_PLACEHOLDER, question_text)
    )
    return ChatRequest(
        pin=pin, messages=[ChatMessage(role="user", content=rendered)], purpose="cypher"
    )


def extract_query(reply_text: str) -> str:
    """The query text of a reply: inside a fence if it has one, without a trailing `;`."""
    fenced = _FENCED.search(reply_text)
    text = fenced.group(1) if fenced else reply_text
    return text.strip().rstrip(";").strip()


def format_context(query: str, result: CypherResult, row_cap: int) -> str:
    """The query and its rows as JSON lines — the context the final step sees."""
    header = f"{len(result.rows)} row(s)"
    if result.truncated:
        header += f"; the result was cut off at the first {row_cap} rows"
    lines = [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in result.rows]
    body = "\n".join(lines) if lines else "(no rows)"
    return (
        f"Cypher query that was run:\n{query}\n\n"
        f"Result ({header}), one JSON object per line:\n{body}"
    )


class CypherRag:
    """Asks the LLM for one Cypher query, runs it, and returns the rows as context."""

    name = "cypher_rag"

    def __init__(
        self,
        source: CypherSource,
        pin: ModelPin,
        send: SendChatRequest,
        *,
        timeout_s: float,
        row_cap: int,
    ) -> None:
        self._source = source
        self._pin = pin
        self._send = send
        self._timeout_s = timeout_s
        self._row_cap = row_cap

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Write, run and format one query; a failed query is `RETRIEVAL_ERROR`, not a raise.

        A `ProviderError` or `CacheMiss` from the LLM call is not caught: those are
        the harness's to handle, as for every other call.
        """
        request = render_cypher_request(
            pin=self._pin, schema_text=self._source.schema_text(), question_text=question_text
        )
        try:
            response = self._send(request)
        except ContextOverflow as error:
            return _failure({"cypher_error": f"the query-writing prompt overflowed: {error}"})
        query = extract_query(response.text)
        trace: dict[str, Any] = {"cypher": query, "cypher_call": _usage(response)}
        if not query:
            return _failure({**trace, "cypher_error": "the model's reply held no query"})
        try:
            result = self._source.run_cypher(query, self._timeout_s, self._row_cap)
        except (WriteClauseError, CypherExecutionError) as error:
            return _failure({**trace, "cypher_error": str(error)})
        context = format_context(query, result, self._row_cap)
        trace.update(
            n_rows=len(result.rows), truncated=result.truncated, empty_result=not result.rows
        )
        return RetrievalResult(context=context, failure=None, trace=trace)


def _failure(trace: dict[str, Any]) -> RetrievalResult:
    return RetrievalResult(context=None, failure=Outcome.RETRIEVAL_ERROR, trace=trace)


def _usage(response: ChatResponse) -> dict[str, Any]:
    """The query-writing call's own cost and size, since only the final call reaches the row."""
    return {
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "cost_usd": response.cost_usd,
        "latency_s": response.latency_s,
        "from_cache": response.from_cache,
    }
