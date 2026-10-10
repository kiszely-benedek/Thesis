"""Reading one model reply as an action: a tool call or `done` (design §5.1, §5.2).

The protocol is plain JSON in JSON mode, not native tool calling, so the chat client and its
cache need no change and every model speaks it the same way (ADR-0034).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

#: A reply wrapped in a markdown fence despite JSON mode.
_FENCED = re.compile(r"```[A-Za-z]*\s*(.*?)```", re.DOTALL)


class ToolCall(BaseModel):
    """`{"call": {"tool": "...", "args": {...}}}`."""

    model_config = ConfigDict(frozen=True)

    tool: str
    args: dict[str, Any]
    #: `{"call": ..., "done": true}`: run the call, then stop if it succeeds.
    finish: bool = False


class Done(BaseModel):
    """`{"done": true}`: the model has gathered enough."""

    model_config = ConfigDict(frozen=True)


Action = ToolCall | Done


class InvalidAction(ValueError):
    """The reply is not an action; the message says what was expected and what was found."""


def parse_action(reply_text: str) -> Action:
    """Read a reply as a `ToolCall` (with `finish` when `done` rides along) or `Done`.

    Raises:
        InvalidAction: not a JSON object, or neither a call nor `done`.
    """
    payload = _load_object(reply_text)
    has_call = "call" in payload
    is_done = payload.get("done") is True
    if not has_call and not is_done:
        raise InvalidAction(
            f'expected {{"call": ...}}, {{"call": ..., "done": true}} or {{"done": true}}, '
            f"found keys {sorted(payload)}"
        )
    if not has_call:
        return Done()
    return _read_call(payload["call"], finish=is_done)


def _load_object(reply_text: str) -> dict[str, Any]:
    fenced = _FENCED.search(reply_text)
    text = (fenced.group(1) if fenced else reply_text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise InvalidAction(
            f"expected a JSON object, found text that is not JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise InvalidAction(f"expected a JSON object, found {type(payload).__name__}")
    return payload


def _read_call(call: Any, *, finish: bool) -> ToolCall:
    if not isinstance(call, dict) or not isinstance(call.get("tool"), str):
        raise InvalidAction(
            f'expected "call" to be {{"tool": <name>, "args": {{...}}}}, found {call!r}'
        )
    args = call.get("args", {})
    if not isinstance(args, dict):
        raise InvalidAction(f'expected "args" to be a JSON object, found {args!r}')
    return ToolCall(tool=call["tool"], args=args, finish=finish)
