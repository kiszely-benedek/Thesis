"""Build the route of one ask from the recorded exchanges and the call-log lines of that ask.

Two sources meet here. The recorded exchanges hold what the model was sent and answered; the
call log holds cost, latency and cache flags. They are joined by the reply's `id`, which the
call log keeps as `provider_response_id`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence

from plantgraph.demo.app.progress import lost_time
from plantgraph.demo.app.trace_models import AgentStep, AskTrace, CypherStep, TraceCall
from plantgraph.demo.app.trace_parse import JoinedCall, agent_step, cypher_step
from plantgraph.demo.app.trace_recorder import Exchange
from plantgraph.llm.models import CallRecord
from plantgraph.qa.plant_api.item_graph import ItemGraph


def build_trace(
    exchanges: Sequence[Exchange], log_lines: Sequence[CallRecord], item_graph: ItemGraph
) -> AskTrace:
    """The trace of one ask.

    Attempts still running are left out. A reply that arrived after its call was abandoned
    (`late_after_timeout`) is left out of the steps, though its line stays in `calls` because
    it was billed.
    """
    finished = [exchange for exchange in exchanges if not exchange.running]
    joined, unlogged = _join(finished, log_lines)
    cypher, agent = _steps(joined, item_graph)
    lost = lost_time(exchanges)
    return AskTrace(
        cypher=cypher,
        agent=agent,
        calls=tuple(_trace_call(line) for line in log_lines),
        unlogged_attempts=unlogged,
        failed_attempts=lost.failed_attempts,
        lost_s=lost.lost_s,
    )


def _join(
    exchanges: Sequence[Exchange], log_lines: Sequence[CallRecord]
) -> tuple[list[JoinedCall], int]:
    """The normal calls with their requests, in log order, and the count of unlogged attempts."""
    waiting: dict[str, deque[Exchange]] = defaultdict(deque)
    for exchange in exchanges:
        reply_id = _reply_id(exchange)
        if reply_id is not None:
            waiting[reply_id].append(exchange)
    joined: list[JoinedCall] = []
    for line in log_lines:
        claimed = _take(waiting, line)
        if claimed is not None and line.error_kind is None and line.response is not None:
            joined.append(_joined_call(line, line.response.text, claimed))
    unlogged = sum(len(left) for left in waiting.values()) + sum(
        1 for exchange in exchanges if _reply_id(exchange) is None
    )
    return joined, unlogged


def _reply_id(exchange: Exchange) -> str | None:
    if exchange.response_json is None:
        return None
    reply_id = exchange.response_json.get("id")
    return reply_id if isinstance(reply_id, str) else None


def _take(waiting: dict[str, deque[Exchange]], line: CallRecord) -> Exchange | None:
    """The oldest unclaimed exchange with this line's reply id (a fake model may reuse one id)."""
    if line.response is None or line.response.provider_response_id is None:
        return None
    queue = waiting.get(line.response.provider_response_id)
    return queue.popleft() if queue else None


def _joined_call(line: CallRecord, reply: str, exchange: Exchange) -> JoinedCall:
    messages = exchange.request_json.get("messages", [])
    return JoinedCall(
        purpose=line.purpose,
        tier=line.strategy or "",
        reply=reply,
        messages=tuple(m for m in messages if isinstance(m, dict)),
    )


def _steps(
    joined: Sequence[JoinedCall], item_graph: ItemGraph
) -> tuple[tuple[CypherStep, ...], tuple[AgentStep, ...]]:
    cypher: list[CypherStep] = []
    agent: list[AgentStep] = []
    run_replies: list[str] = []  # replies of the agent run in progress, for repeated replies
    for position, call in enumerate(joined):
        later = joined[position + 1] if position + 1 < len(joined) else None
        if call.purpose != "agent_step":
            run_replies.clear()
        if call.purpose == "cypher":
            cypher.append(cypher_step(call, later))
        if call.purpose == "agent_step":
            repeats = run_replies.count(call.reply)
            run_replies.append(call.reply)
            step = agent_step(call, len(run_replies), later, repeats, item_graph)
            if step is not None:
                agent.append(step)
    return tuple(cypher), tuple(agent)


def _trace_call(line: CallRecord) -> TraceCall:
    response = line.response
    return TraceCall(
        purpose=line.purpose,
        strategy=line.strategy or "",
        latency_s=0.0 if response is None else response.latency_s,
        cost_usd=0.0 if response is None or response.cost_usd is None else response.cost_usd,
        from_cache=response is not None and response.from_cache,
        error_kind=line.error_kind,
    )
