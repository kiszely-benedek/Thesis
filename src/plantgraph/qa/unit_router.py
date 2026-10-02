"""The router fallback: choose units by an LLM call when a question names no tag (design D5).

Hierarchical finds its starting points deterministically (`anchors.py`).
A question such as "which unit holds the most pumps?" names no tag, so there
is nothing to look up; only then is one model call made. It sees a *plant
map* (one line per unit: its id and the equipment tags drawn in it) and the
question, and returns unit ids. Every use is counted by the strategy's trace,
because the fallback rate is reported (`qa-system.md` §7).

The call uses the run's answer model: there is no second model (design §3.5).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from plantgraph.llm.models import ChatMessage, ChatRequest, ChatResponse, ModelPin
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.scoring import normalize_scalar

_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "unit_router.txt"
_MAP_PLACEHOLDER = "<<PLANT_MAP>>"
_QUESTION_PLACEHOLDER = "<<QUESTION>>"
#: A reply wrapped in a markdown fence despite the instruction not to.
_FENCED = re.compile(r"```[A-Za-z]*\s*(.*?)```", re.DOTALL)


class UnitChoice(BaseModel):
    """What the router chose: known unit ids, the unknown ids it also named, and the call's cost."""

    model_config = ConfigDict(frozen=True)

    units: tuple[str, ...]
    unknown_units: tuple[str, ...]
    call: dict[str, Any]


class UnitRouterError(ValueError):
    """The reply was not the JSON object the prompt asked for."""


def build_plant_map(view: GraphView) -> str:
    """One line per unit, `<unit id>: <tag>, <tag>, ...`, in unit-id order; empty without units."""
    tags_by_unit: dict[str, set[str]] = defaultdict(set)
    for item in view.items():
        if item.unit_id is not None and item.tag is not None:
            tags_by_unit[item.unit_id].add(item.tag)
    return "\n".join(
        f"{unit_id}: {', '.join(sorted(tags_by_unit[unit_id]))}" for unit_id in sorted(tags_by_unit)
    )


def parse_units(reply_text: str) -> list[str]:
    """The `units` list of the reply's JSON object, as strings.

    Raises:
        UnitRouterError: the reply holds no JSON object with a `units` list.
    """
    fenced = _FENCED.search(reply_text)
    text = (fenced.group(1) if fenced else reply_text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise UnitRouterError(
            f"expected a JSON object with 'units', found {text[:80]!r}"
        ) from error
    units = payload.get("units") if isinstance(payload, dict) else None
    if not isinstance(units, list):
        raise UnitRouterError(f"expected a JSON object with a 'units' list, found {text[:80]!r}")
    return [str(unit) for unit in units]


class UnitRouter:
    """Asks the LLM which units a tag-free question is about."""

    def __init__(self, view: GraphView, pin: ModelPin, send: SendChatRequest) -> None:
        self._view = view
        self._pin = pin
        self._send = send
        self._plant_map: str | None = None

    @property
    def has_units(self) -> bool:
        """False for a corpus with no `unit_id` (an EX01-shaped import): nothing to choose from."""
        return bool(self._map())

    def render_request(self, question_text: str) -> ChatRequest:
        """The one prompt of the fallback (`unit_router.txt`)."""
        rendered = (
            _TEMPLATE_PATH.read_text(encoding="utf-8")
            .replace(_MAP_PLACEHOLDER, self._map())
            .replace(_QUESTION_PLACEHOLDER, question_text)
        )
        return ChatRequest(
            pin=self._pin, messages=[ChatMessage(role="user", content=rendered)], purpose="route"
        )

    def choose(self, question_text: str) -> UnitChoice:
        """Make the call and keep the unit ids the plant has; `ContextOverflow` is the caller's."""
        response = self._send(self.render_request(question_text))
        named = parse_units(response.text)
        known = {normalize_scalar(unit_id): unit_id for unit_id in self._view.unit_ids()}
        named_keys = [normalize_scalar(unit) for unit in named]
        # `dict.fromkeys` drops repeats but keeps the order the model named them in
        units = tuple(dict.fromkeys(known[key] for key in named_keys if key in known))
        unknown = tuple(
            unit for unit, key in zip(named, named_keys, strict=True) if key not in known
        )
        return UnitChoice(units=units, unknown_units=unknown, call=_usage(response))

    def _map(self) -> str:
        if self._plant_map is None:
            self._plant_map = build_plant_map(self._view)  # the corpus is fixed: build once
        return self._plant_map


def _usage(response: ChatResponse) -> dict[str, Any]:
    """The router call's own cost and size, since only the final call reaches the result row."""
    return {
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "cost_usd": response.cost_usd,
        "latency_s": response.latency_s,
        "from_cache": response.from_cache,
    }
