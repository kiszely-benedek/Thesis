"""The D4 prompt: the task, one sentence of general practice, and the pair card.

The prompt names no tag-variant operator and no synonym (design 5.4): the model must use general
knowledge of how plants label equipment. It is built from the card text alone, so it can never
carry a gold label. Prompt text, card format and pin are hashed into the pre-registration.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin

SYSTEM_PROMPT = (
    "You read engineering diagrams (P&IDs). The same physical piece of equipment can be drawn on "
    "several sheets, and its tag (the label printed next to it) may be written differently on "
    "each sheet. You are given two drawn occurrences, A and B. Decide whether they are the same "
    "physical item. "
    "Installed spares share a number and differ by a trailing letter. "
    'Answer with one JSON object and nothing else: {"same_item": true or false, '
    '"reason": "one short sentence"}.'
)


class Verdict(BaseModel):
    """The JSON object D4 asks the model for."""

    model_config = ConfigDict(frozen=True)

    same_item: StrictBool
    reason: str


def prompt_sha256() -> str:
    """Hash of the system prompt."""
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def build_request(pin: ModelPin, card: str) -> ChatRequest:
    """The request for one pair card: the system prompt, then the card as the user message."""
    return ChatRequest(
        pin=pin,
        messages=[
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=card),
        ],
        json_mode=True,
        purpose="judge",
    )


def parse_verdict(text: str) -> Verdict | None:
    """The verdict in `text`, or None when it is not exactly the requested JSON object."""
    try:
        return Verdict.model_validate_json(text.strip())
    except ValidationError:
        return None
