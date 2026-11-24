"""The V2T-B final-answer step: the `VALVE_SET` and `POSITION` answer rules, and their parsing.

The frozen step knows neither type. Everything else is handed to it unchanged, so a B run asks and
parses a `TAG_SET` question exactly as V2T-A2 does.

A `VALVE_SET` item is a tag, `{"tag": ...}`, or a descriptor object (`descriptor.py`). The frozen
`FinalAnswer` holds only strings, so each descriptor is stored as its sorted-key JSON string
(`encode_descriptor`), and the scorer reads it back.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin
from plantgraph.qa.final_answer import (
    _ANSWER_FORMAT_PLACEHOLDER,
    _CONTEXT_PLACEHOLDER,
    _QUESTION_PLACEHOLDER,
    FinalAnswerParseError,
    _answer_format_instruction,
    _parse_json_object,
    parse_final_answer,
    template_text,
)
from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome
from plantgraph.qa.v2tb.descriptor import descriptor_from_object, encode_descriptor
from plantgraph.qa.v2tb.primer_b import fill_primer_slot_b
from plantgraph.qa.v2tb.scoring_b import normalize_position
from plantgraph.qa.v2tb.visible import POSITION_CODES

B_ANSWER_TYPES = (AnswerType.VALVE_SET, AnswerType.POSITION)

#: Draft wording (design 5); the three tuning rounds may reword it.
_FORMAT_INSTRUCTIONS = {
    AnswerType.VALVE_SET: (
        "Answer with a JSON list, one entry per valve. Name a valve that prints a tag by that tag, "
        'for example "GTV-1203". Name a valve that prints no tag by an object with exactly the '
        'keys "class" (its valve class), "line_number" (the line number of its pipe), "next_to" '
        '(the tag of the nearest tagged item on that line) and "side" ("upstream" if the valve '
        'lies upstream of that item along the flow, otherwise "downstream"), for example '
        '{"class": "GateValve", "line_number": "6-P-1203-A1A", "next_to": "FV-1203", '
        '"side": "upstream"}.'
    ),
    AnswerType.POSITION: (
        f"Answer with one position code, exactly one of {', '.join(POSITION_CODES)}."
    ),
}


def answer_format_instruction_b(
    answer_type: AnswerType, class_names: Collection[str] | None = None
) -> str:
    """How the model must shape `answer`: B's sentence for B's types, else the frozen one."""
    if answer_type in _FORMAT_INSTRUCTIONS:
        return _FORMAT_INSTRUCTIONS[answer_type]
    return _answer_format_instruction(answer_type, class_names)


def render_final_answer_request_b(
    *,
    pin: ModelPin,
    context: str,
    question_text: str,
    answer_type: AnswerType,
    primer: bool = False,
    class_names: Collection[str] | None = None,
    template_path: Path | None = None,
) -> ChatRequest:
    """The frozen request, built with the B primer and the B answer-format sentence."""
    template = template_text() if template_path is None else template_path.read_text("utf-8")
    rendered = (
        fill_primer_slot_b(template, primer=primer)
        .replace(_CONTEXT_PLACEHOLDER, context)
        .replace(_QUESTION_PLACEHOLDER, question_text)
        .replace(_ANSWER_FORMAT_PLACEHOLDER, answer_format_instruction_b(answer_type, class_names))
    )
    return ChatRequest(
        pin=pin,
        messages=[ChatMessage(role="user", content=rendered)],
        json_mode=True,
        purpose="answer",
    )


def parse_final_answer_b(raw_text: str, answer_type: AnswerType) -> FinalAnswer:
    """Parse a reply; `VALVE_SET` and `POSITION` here, every other type by the frozen parser.

    Raises:
        FinalAnswerParseError: the reply is not JSON, or its answer does not fit the type.
    """
    if answer_type not in B_ANSWER_TYPES:
        return parse_final_answer(raw_text, answer_type)
    payload = _parse_json_object(raw_text)
    if payload is None:
        raise FinalAnswerParseError(f"no JSON object found in model reply: {raw_text!r}")
    not_present = payload.get("not_present") is True
    answer = None if not_present else _read_answer(payload.get("answer"), answer_type)
    try:
        return FinalAnswer(answer=answer, not_present=not_present)
    except ValidationError as error:
        raise FinalAnswerParseError(
            f"reply does not match the FinalAnswer schema: {error}"
        ) from error


def to_outcome_b(raw_text: str, answer_type: AnswerType) -> tuple[Outcome, FinalAnswer | None]:
    """`parse_final_answer_b` as an outcome; a parse failure is data, never an exception."""
    try:
        return Outcome.ANSWERED, parse_final_answer_b(raw_text, answer_type)
    except FinalAnswerParseError:
        return Outcome.PARSE_FAILURE, None


def _read_answer(answer: object, answer_type: AnswerType) -> str | list[str]:
    if answer_type is AnswerType.POSITION:
        return _read_position(answer)
    if not isinstance(answer, list):
        raise FinalAnswerParseError(f"VALVE_SET needs a list of items, got {answer!r}")
    return [_read_item(item) for item in answer]


def _read_position(answer: object) -> str:
    code = normalize_position(answer) if isinstance(answer, str) else None
    if code is None:
        raise FinalAnswerParseError(f"POSITION needs one of {POSITION_CODES}, got {answer!r}")
    return code


def _read_item(item: object) -> str:
    """A tag stays; `{"tag": ...}` becomes the tag; a descriptor object becomes its string."""
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        raise FinalAnswerParseError(f"a VALVE_SET item is a tag or an object, got {item!r}")
    if set(item) == {"tag"} and isinstance(item["tag"], str):
        return item["tag"]
    return _descriptor_string(item)


def _descriptor_string(item: dict[str, Any]) -> str:
    try:
        return encode_descriptor(descriptor_from_object(item))
    except ValueError as error:
        raise FinalAnswerParseError(str(error)) from error
