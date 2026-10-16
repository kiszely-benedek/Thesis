"""Reading the recorded model traffic: the Cypher query and rows, and each agent tool call.

The prompts are built by the frozen QA code, so the shapes read here are its shapes:
the database tier's context text (`cypher_rag.format_context`), the agent's conversation
(`agent/loop.py`) and the agent's gathered-results context (`agent/strategies.py`).
If a shape ever changes, the part is kept raw and flagged `parsed=False`, never dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from plantgraph.demo.app.evidence import items_in_text
from plantgraph.demo.app.trace_models import AgentStep, CypherStep
from plantgraph.qa.agent.actions import Done, InvalidAction, ToolCall, parse_action
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.strategies.cypher_rag import extract_query

#: The final-answer template puts the question right after the context.
_AFTER_CONTEXT = "\n\nQuestion:\n"
_CONTEXT_START = "Cypher query that was run:\n"
_ROWS_MARKER = "), one JSON object per line:\n"
_NO_ROWS = "(no rows)"
_CUT_OFF = "cut off"
#: Between two entries of the agent's gathered-results context.
_NEXT_CALL = "\n\nCall: "


@dataclass(frozen=True)
class JoinedCall:
    """One successful model call: its call-log facts and the request that was really sent."""

    purpose: str
    #: The strategy that made the call (the call log's name for the tier).
    tier: str
    #: The model's reply text.
    reply: str
    #: The request's messages as sent: `{"role": ..., "content": ...}`.
    messages: tuple[dict[str, Any], ...]

    def last_user_message(self) -> str:
        """The content of the last `user` message ("" if there is none)."""
        users = [str(m.get("content", "")) for m in self.messages if m.get("role") == "user"]
        return users[-1] if users else ""


def cypher_step(call: JoinedCall, final: JoinedCall | None) -> CypherStep:
    """The query of a `cypher` call and, from the answer call after it, the rows the model saw."""
    query = extract_query(call.reply)
    unread = CypherStep(tier=call.tier, query=query, context="", parsed=False)
    if final is None or final.purpose != "answer":
        return unread  # the query failed to run, so no answer call followed
    context = _context_text(final.last_user_message())
    if context is None:
        return unread.model_copy(update={"context": final.last_user_message()})
    step = CypherStep(tier=call.tier, query=query, context=context)
    return _with_rows(step)


def _context_text(prompt: str) -> str | None:
    """The part of the answer prompt between the context heading and the question."""
    start = prompt.find(_CONTEXT_START)
    if start < 0:
        return None
    end = prompt.find(_AFTER_CONTEXT, start)
    return prompt[start:] if end < 0 else prompt[start:end]


def _with_rows(step: CypherStep) -> CypherStep:
    """Read the header and JSON lines that follow the query in the context."""
    prefix = f"{_CONTEXT_START}{step.query}\n\nResult ("
    if not step.context.startswith(prefix) or _ROWS_MARKER not in step.context:
        return step.model_copy(update={"parsed": False})
    header, _, body = step.context[len(prefix) :].partition(_ROWS_MARKER)
    truncated = _CUT_OFF in header
    if body == _NO_ROWS:
        return step.model_copy(update={"truncated": truncated})
    rows = _json_rows(body)
    if rows is None:
        return step.model_copy(update={"truncated": truncated, "parsed": False})
    return step.model_copy(update={"rows": rows, "truncated": truncated})


def _json_rows(body: str) -> tuple[dict[str, Any], ...] | None:
    """Each line as a JSON object, or `None` if any line is not one."""
    rows: list[dict[str, Any]] = []
    for line in body.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            return None
        if not isinstance(row, dict):
            return None
        rows.append(row)
    return tuple(rows)


def agent_step(
    call: JoinedCall, index: int, later: JoinedCall | None, repeats: int, graph: ItemGraph
) -> AgentStep | None:
    """The tool call a reply made, with its observation; `None` for a plain `done` reply.

    Args:
        call: the `agent_step` call.
        index: its 1-based position in the run.
        later: the next call, whose request holds this call's observation.
        repeats: how many earlier replies of the run had exactly this text.
        graph: the plant, to name the items mentioned.
    """
    try:
        action = parse_action(call.reply)
    except InvalidAction:
        observation = _observation(call, repeats, later, None)
        return AgentStep(
            index=index,
            tier=call.tier,
            reply=call.reply,
            tool="",
            args={},
            observation=observation or "",
            items=(),
            parsed=False,
        )
    if isinstance(action, Done):
        return None
    observation = _observation(call, repeats, later, action)
    text = f"{json.dumps(action.args, sort_keys=True)}\n{observation or ''}"
    return AgentStep(
        index=index,
        tier=call.tier,
        reply=call.reply,
        tool=action.tool,
        args=action.args,
        observation=observation or "",
        items=items_in_text(text, graph),
        parsed=observation is not None,
    )


def _observation(
    call: JoinedCall, repeats: int, later: JoinedCall | None, action: ToolCall | None
) -> str | None:
    """What the tool returned, or `None` if it cannot be found in the next request."""
    if later is None:
        return None
    from_conversation = _from_conversation(later.messages, call.reply, repeats)
    if from_conversation is not None or action is None or later.purpose != "answer":
        return from_conversation
    return _from_final_context(later.last_user_message(), action)


def _from_conversation(
    messages: tuple[dict[str, Any], ...], reply: str, repeats: int
) -> str | None:
    """The `user` message after the reply's copy in a later request (the nth, if repeated)."""
    seen = 0
    for position, message in enumerate(messages[:-1]):
        if message.get("role") != "assistant" or message.get("content") != reply:
            continue
        if seen == repeats:
            return str(messages[position + 1].get("content", ""))
        seen += 1
    return None


def _from_final_context(prompt: str, action: ToolCall) -> str | None:
    """The result of the last call, from the gathered-results context of the answer prompt."""
    marker = f"Call: {action.tool}({json.dumps(action.args, sort_keys=True)})\n"
    start = prompt.find(marker)
    if start < 0:
        return None
    rest = prompt[start + len(marker) :]
    ends = [i for i in (rest.find(_NEXT_CALL), rest.find(_AFTER_CONTEXT)) if i >= 0]
    return rest[: min(ends)] if ends else rest
