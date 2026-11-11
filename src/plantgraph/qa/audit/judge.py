"""The blind judge: build its prompt from a `JudgeInput`, call the model, parse the reply.

"Blind" means the prompt is built from `JudgeInput` only, a type with no field for the scorer's
verdict. `tests/qa/audit/test_judge.py` proves two rows that differ only in the scorer's
verdict give byte-identical prompts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ChatMessage, ChatRequest, ChatResponse, ModelPin
from plantgraph.qa.audit.models import JudgeInput, JudgeReply
from plantgraph.qa.models import AnswerType, AnswerValue

TEMPLATE_PATH = Path(__file__).parent / "audit_judge.txt"

#: Slug used in PAID-04 (`docs/private/30-experiments/paid04`); not the system's model (GPT-6 Luna).
JUDGE_MODEL_ID = "anthropic/claude-sonnet-5.5"

#: Longest system reply shown; a runaway reply is cut, the cut is stated.
MAX_RAW_REPLY_CHARS = 4_000

_ANSWER_TYPE_HELP: dict[AnswerType, str] = {
    AnswerType.CLASS_NAME: "CLASS_NAME (the kind of a part, e.g. a pump)",
    AnswerType.UNIT_ID: "UNIT_ID (the number of a process unit)",
    AnswerType.TAG: "TAG (one printed tag)",
    AnswerType.TAG_SET: "TAG_SET (a set of printed tags, order irrelevant)",
    AnswerType.UNIT_SET: "UNIT_SET (a set of process unit numbers)",
    AnswerType.SHEET_SET: "SHEET_SET (a set of drawing sheet numbers)",
    AnswerType.TAG_PATH: "TAG_PATH (an ordered list of tags along a route)",
    AnswerType.COUNT: "COUNT (a whole number)",
    AnswerType.BOOLEAN: "BOOLEAN (yes or no)",
    AnswerType.FREE_TEXT: "FREE_TEXT (a sentence)",
}


def judge_pin() -> ModelPin:
    """The pinned judge: Sonnet 5.5, low reasoning effort, 2,048 output tokens (§5.3)."""
    return ModelPin(
        backend="openrouter",
        model_id=JUDGE_MODEL_ID,
        temperature=0.0,
        max_output_tokens=2_048,
        extra={"reasoning": {"effort": "low"}},
    )


def template_sha256() -> str:
    """Hash of the judge prompt file, for the pre-registration."""
    return hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()


def build_prompt(judge_input: JudgeInput) -> str:
    """Fill the template; every field comes from `JudgeInput`, nothing else is reachable."""
    values = {
        "<<QUESTION>>": judge_input.question_text,
        "<<ANSWER_TYPE>>": _ANSWER_TYPE_HELP[judge_input.answer_type],
        "<<RAW_REPLY>>": _raw_reply_text(judge_input.raw_reply),
        "<<REFERENCE>>": _reference_text(judge_input),
        "<<EXCERPT>>": judge_input.plant_excerpt,
    }
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    return text


def build_request(judge_input: JudgeInput) -> ChatRequest:
    """The chat request for one row, asking for a JSON object."""
    message = ChatMessage(role="user", content=build_prompt(judge_input))
    return ChatRequest(pin=judge_pin(), messages=[message], json_mode=True, purpose="judge")


def call_judge(
    client: ChatClient, judge_input: JudgeInput, *, run_id: str, question_id: str
) -> ChatResponse:
    """One judge call through the client and its cache.

    The reply is parsed separately (`parse_reply`) so a malformed reply still has its cost
    recorded by the caller.
    """
    return client.complete(
        build_request(judge_input), run_id=run_id, question_id=question_id, strategy="audit_judge"
    )


def parse_reply(text: str) -> JudgeReply:
    """Read the judge's verdict: the last JSON object of the reply that holds the three fields.

    The prompt asks for the object alone, but the pinned model often works the answer out in
    prose first and ends with the object (all 48 replies of the first pilot, 2026-11-11), so
    text around the object is skipped. The last object wins: it is the judge's final word.

    Raises:
        ValueError: no JSON object in the text is the one the prompt asked for.
    """
    for candidate in reversed(_json_objects(text)):
        try:
            return JudgeReply.model_validate(candidate)
        except ValidationError:
            continue
    raise ValueError(f"expected a judge reply with verdict/reference_ok/reason, got {text[:200]!r}")


def _json_objects(text: str) -> list[object]:
    """Every JSON object that starts at a `{` of the text, outermost only, in order."""
    decoder = json.JSONDecoder()
    found: list[object] = []
    start = text.find("{")
    while start != -1:
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            end = start + 1
        else:
            found.append(value)
        start = text.find("{", end)
    return found


def _raw_reply_text(raw_reply: str) -> str:
    if len(raw_reply) > MAX_RAW_REPLY_CHARS:
        return raw_reply[:MAX_RAW_REPLY_CHARS] + "\n[reply cut here: it was longer]"
    return raw_reply


def _reference_text(judge_input: JudgeInput) -> str:
    if not judge_input.answerable:
        return "none: the benchmark holds that the drawings do not contain an answer"
    return _value_text(judge_input.reference, "(none given)")


def _value_text(value: AnswerValue, when_missing: str) -> str:
    return when_missing if value is None else json.dumps(value)
