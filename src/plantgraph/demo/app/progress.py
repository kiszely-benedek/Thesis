"""Live progress and lost time of an ask, read from the recorded attempts.

An attempt is one HTTP request to the model provider. The recorder keeps every attempt from the
moment it is sent (`trace_recorder.py`), so a poll can say what the ask is doing right now, and how
much time provider errors have cost so far.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import Sequence
from typing import Any

from plantgraph.demo.app.progress_models import (
    EventState,
    LiveProgress,
    LostTime,
    Phase,
    ProgressEvent,
)
from plantgraph.demo.app.trace_parse import JoinedCall, find_observation
from plantgraph.demo.app.trace_recorder import Exchange, TraceWindow
from plantgraph.llm.models import CallRecord
from plantgraph.qa.agent.actions import InvalidAction, ToolCall, parse_action
from plantgraph.qa.strategies.cypher_rag import extract_query

#: The first words of each frozen prompt (`qa/prompts/*.txt`); a test keeps them in step.
CYPHER_PROMPT_START = "You are writing a database query about one plant's"
ANSWER_PROMPT_START = "You are answering a question about one plant's"
AGENT_PROMPT_START = "You gather evidence about one plant's"
_LOGGED_PHASES: dict[str, Phase] = {
    "cypher": "cypher",
    "answer": "answer",
    "agent_step": "agent_step",
}
_DETAIL_CHARS = 200


def live_progress(window: TraceWindow) -> LiveProgress:
    """The progress of the ask that `window` marks, as of now."""
    return build_progress(
        window.exchanges(), window.log_lines(), window.recorder.now_s(), window.mark_s
    )


def build_progress(
    exchanges: Sequence[Exchange], log_lines: Sequence[CallRecord], now_s: float, mark_s: float
) -> LiveProgress:
    """One event per attempt.

    Args:
        exchanges: the ask's attempts, in the order they were sent.
        log_lines: the call-log lines written so far (only finished, successful calls have one).
        now_s: the recorder's clock now, to time the attempts that are still running.
        mark_s: the recorder's clock when the ask began.
    """
    phases = _phases(exchanges, log_lines)
    attempts = _attempt_numbers(exchanges)
    actions = _action_numbers(exchanges, phases)
    events = [
        _event(exchange, phases[position], now_s, mark_s).model_copy(
            update={"attempt": attempts[position], "action": actions[position]}
        )
        for position, exchange in enumerate(exchanges)
    ]
    texts = [_with_text(event, p, exchanges, phases) for p, event in enumerate(events)]
    return LiveProgress(events=tuple(texts))


def lost_time(exchanges: Sequence[Exchange]) -> LostTime:
    """Failed attempts and the seconds they cost: their duration plus the wait before the retry."""
    failed = [(position, ex) for position, ex in enumerate(exchanges) if ex.failed]
    lost = sum(ex.elapsed_s + _wait_before_retry(position, exchanges) for position, ex in failed)
    return LostTime(failed_attempts=len(failed), lost_s=lost)


def _wait_before_retry(position: int, exchanges: Sequence[Exchange]) -> float:
    """Seconds between a failed attempt's end and the next attempt, if that is its retry."""
    failed = exchanges[position]
    if position + 1 >= len(exchanges):
        return 0.0
    retry = exchanges[position + 1]
    if retry.request_json != failed.request_json:  # a different request: not a retry
        return 0.0
    return max(0.0, retry.started_s - (failed.started_s + failed.elapsed_s))


# ---- phase ----------------------------------------------------------------------------------


def _phases(exchanges: Sequence[Exchange], log_lines: Sequence[CallRecord]) -> list[Phase]:
    """Per attempt: its call-log line's purpose, else the prompt's marker, else unknown."""
    waiting: dict[str, deque[CallRecord]] = defaultdict(deque)
    for logged_call in log_lines:
        response = logged_call.response
        if response is not None and response.provider_response_id is not None:
            waiting[response.provider_response_id].append(logged_call)
    phases: list[Phase] = []
    for exchange in exchanges:
        line = _claim(waiting, exchange)
        logged = None if line is None else _LOGGED_PHASES.get(line.purpose)
        phases.append(logged or phase_from_prompt(exchange.request_json))
    return phases


def _claim(waiting: dict[str, deque[CallRecord]], exchange: Exchange) -> CallRecord | None:
    """The oldest unclaimed log line with this attempt's reply id (a fake model may reuse an id)."""
    reply_id = (exchange.response_json or {}).get("id")
    queue = waiting.get(reply_id) if isinstance(reply_id, str) else None
    return queue.popleft() if queue else None


def phase_from_prompt(request_json: dict[str, Any]) -> Phase:
    """The phase named by the first message of the request, or `unknown`."""
    messages = request_json.get("messages")
    first = messages[0] if isinstance(messages, list) and messages else None
    text = str(first.get("content", "")) if isinstance(first, dict) else ""
    if text.startswith(CYPHER_PROMPT_START):
        return "cypher"
    if text.startswith(ANSWER_PROMPT_START):
        return "answer"
    if text.startswith(AGENT_PROMPT_START):
        return "agent_step"
    return "unknown"


# ---- one event ------------------------------------------------------------------------------


def _event(exchange: Exchange, phase: Phase, now_s: float, mark_s: float) -> ProgressEvent:
    state: EventState = "running" if exchange.running else "failed" if exchange.failed else "done"
    elapsed = now_s - exchange.started_s if exchange.running else exchange.elapsed_s
    replied_with_error = exchange.failed and exchange.status is not None
    return ProgressEvent(
        phase=phase,
        state=state,
        started_s=max(0.0, exchange.started_s - mark_s),
        elapsed_s=max(0.0, elapsed),
        attempt=1,
        http_status=exchange.status if replied_with_error else None,
        error=None if replied_with_error else exchange.error,
    )


def _attempt_numbers(exchanges: Sequence[Exchange]) -> list[int]:
    """Count up while the same request is sent again right after a failure of it."""
    numbers: list[int] = []
    for position, exchange in enumerate(exchanges):
        previous = exchanges[position - 1] if position > 0 else None
        is_retry = (
            previous is not None
            and previous.failed
            and previous.request_json == exchange.request_json
        )
        numbers.append(numbers[-1] + 1 if is_retry else 1)
    return numbers


def _action_numbers(exchanges: Sequence[Exchange], phases: Sequence[Phase]) -> list[int | None]:
    """The agent action each attempt works on: finished steps so far, plus one while not done."""
    numbers: list[int | None] = []
    finished = 0
    for exchange, phase in zip(exchanges, phases, strict=True):
        if phase != "agent_step":
            numbers.append(None)
            continue
        done = not exchange.failed and not exchange.running
        finished += done
        numbers.append(finished if done else finished + 1)
    return numbers


# ---- the text of a finished event ----------------------------------------------------------


def _with_text(
    event: ProgressEvent, position: int, exchanges: Sequence[Exchange], phases: Sequence[Phase]
) -> ProgressEvent:
    """Add the query or the tool call to a finished event."""
    if event.state != "done":
        return event
    reply = _reply_text(exchanges[position])
    if event.phase == "cypher":
        return event.model_copy(update={"summary": extract_query(reply)})
    if event.phase == "agent_step":
        return _with_tool_call(event, position, exchanges, phases, reply)
    return event


def _with_tool_call(
    event: ProgressEvent,
    position: int,
    exchanges: Sequence[Exchange],
    phases: Sequence[Phase],
    reply: str,
) -> ProgressEvent:
    try:
        action = parse_action(reply)
    except InvalidAction:
        return event  # the page shows the step without a summary
    if not isinstance(action, ToolCall):
        return event
    observation = _observation_of(action, position, exchanges, phases, reply)
    return event.model_copy(
        update={"summary": _call_text(action), "detail": _first_line(observation)}
    )


def _call_text(action: ToolCall) -> str:
    """`find(tag="E-30-3")`: the tool and its arguments the way a person would type them."""
    args = ", ".join(f"{name}={json.dumps(value)}" for name, value in action.args.items())
    return f"{action.tool}({args})"


def _observation_of(
    action: ToolCall,
    position: int,
    exchanges: Sequence[Exchange],
    phases: Sequence[Phase],
    reply: str,
) -> str | None:
    """What the tool returned, if the request after this one already shows it."""
    if position + 1 >= len(exchanges):
        return None
    this = _joined(exchanges[position], phases[position], reply)
    # the next request holds the observation even while it is still waiting for its own reply
    later = _joined(exchanges[position + 1], phases[position + 1], "")
    return find_observation(this, _repeats(position, exchanges, phases), later, action)


def _repeats(position: int, exchanges: Sequence[Exchange], phases: Sequence[Phase]) -> int:
    """How many earlier steps of the same agent run had exactly this reply."""
    reply = _reply_text(exchanges[position])
    count = 0
    for earlier in range(position - 1, -1, -1):
        if phases[earlier] != "agent_step":
            break
        count += _reply_text(exchanges[earlier]) == reply
    return count


def _joined(exchange: Exchange, phase: Phase, reply: str) -> JoinedCall:
    messages = exchange.request_json.get("messages", [])
    return JoinedCall(
        purpose=phase,
        tier="",
        reply=reply,
        messages=tuple(m for m in messages if isinstance(m, dict)),
    )


def _reply_text(exchange: Exchange) -> str:
    """The model's reply text, or "" when the attempt has none."""
    choices = (exchange.response_json or {}).get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else ""


def _first_line(text: str | None) -> str | None:
    lines = (text or "").strip().splitlines()
    return lines[0][:_DETAIL_CHARS] if lines else None
