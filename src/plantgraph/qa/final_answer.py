"""The shared final-answer step every retrieval strategy ends with (`qa-system.md` §7, §8).

ADR-0013 point 6 (fairness): CypherRAG returns database rows and ContextRAG
returns a serialized graph, so without one shared step at the end, answers
would differ by strategy rather than by retrieval. This module is that one
step: it renders the same prompt template (`prompts/final_answer.txt`) around
whatever `context` string a strategy produced, sends it through the fit
check (`fit.py`) and a caller-supplied sender, and turns the reply into an
`Outcome` and, when parsing succeeds, a `FinalAnswer`.

No network call and no LLM client live here. `run_final_step` takes a
`send` callable instead of talking to a provider itself, so it is tested
with a canned function standing in for the real client (`llm/client.py`,
QA-T2), which is not built yet.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from plantgraph.graph.schema import NodeClass
from plantgraph.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContextOverflow,
    ContextWall,
    ModelPin,
)
from plantgraph.qa.fit import check_fit, handle_overflow
from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome

_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "final_answer.txt"

#: Placeholders in `final_answer.txt`, replaced with plain `str.replace` (no
#: `str.format`) so a context string that itself contains JSON braces — as
#: CypherRAG's row dump does — is never mistaken for a template field.
_CONTEXT_PLACEHOLDER = "<<CONTEXT>>"
_QUESTION_PLACEHOLDER = "<<QUESTION>>"
_ANSWER_FORMAT_PLACEHOLDER = "<<ANSWER_FORMAT_INSTRUCTION>>"

#: One fixed sentence per `AnswerType`, telling the model the shape `answer`
#: must take. `CLASS_NAME` is not listed here: its instruction is generated
#: from `schema.NodeClass` (`_answer_format_instruction`) so the allowed
#: names can never drift out of step with the schema.
_FIXED_FORMAT_INSTRUCTIONS: dict[AnswerType, str] = {
    AnswerType.UNIT_ID: 'Answer with the unit identifier as a string, for example "12".',
    AnswerType.TAG: "Answer with a single tag, exactly as printed on the diagram.",
    AnswerType.TAG_SET: "Answer with a JSON list of tags, one per equipment item or valve.",
    AnswerType.UNIT_SET: "Answer with a JSON list of unit identifiers.",
    AnswerType.TAG_PATH: (
        "Answer with a JSON list of tags, in order from the start item to the end item. "
        "List equipment items and valves only, and omit off-page connectors."
    ),
    AnswerType.COUNT: "Answer with a single integer.",
    AnswerType.FREE_TEXT: "Answer in a short paragraph of plain text.",
}


def _answer_format_instruction(answer_type: AnswerType) -> str:
    """The fixed, per-`AnswerType` sentence telling the model how to shape `answer` (§8)."""
    if answer_type is AnswerType.CLASS_NAME:
        names = ", ".join(sorted(node_class.value for node_class in NodeClass))
        return f"Answer with one of these class names, exactly as written: {names}."
    return _FIXED_FORMAT_INSTRUCTIONS[answer_type]


def template_text() -> str:
    """The raw text of the shared final-answer template, read fresh on every call."""
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def template_sha256() -> str:
    """Sha256 of the template file's bytes, recorded in `RunConfig.prompt_hashes` (§3)."""
    return hashlib.sha256(_TEMPLATE_PATH.read_bytes()).hexdigest()


def render_final_answer_request(
    *, pin: ModelPin, context: str, question_text: str, answer_type: AnswerType
) -> ChatRequest:
    """Build the one shared final-answer request every strategy ends with (§8; ADR-0013 point 6).

    Only `context` differs between strategies: the instruction, the question
    and the answer-format rule all come from the same template and the same
    `answer_type`, so the JSON-output contract never depends on which
    strategy produced the context.
    """
    rendered = (
        template_text()
        .replace(_CONTEXT_PLACEHOLDER, context)
        .replace(_QUESTION_PLACEHOLDER, question_text)
        .replace(_ANSWER_FORMAT_PLACEHOLDER, _answer_format_instruction(answer_type))
    )
    return ChatRequest(
        pin=pin,
        messages=[ChatMessage(role="user", content=rendered)],
        json_mode=True,
        purpose="answer",
    )


class FinalAnswerParseError(Exception):
    """The model's reply could not be read as a `FinalAnswer` matching its `answer_type`."""


def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced `{...}` substring in `text`, from its first `{` (§8, step 2).

    Walks the text once, counting brace depth, but ignores braces written
    inside a JSON string literal — so a stray "}" inside an answer string
    does not end the object early. This is what lets a fenced code block or
    a sentence of prose around the JSON still be found.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None  # never closed: a truncated reply


def _parse_json_object(raw_text: str) -> dict[str, Any] | None:
    """Try strict JSON, then the first balanced object anywhere in `raw_text` (§8, steps 1-2)."""
    try:
        candidate: Any = json.loads(raw_text)
        if isinstance(candidate, dict):
            return candidate
    except json.JSONDecodeError:
        pass
    block = _extract_first_json_object(raw_text)
    if block is None:
        return None
    try:
        candidate = json.loads(block)
    except json.JSONDecodeError:
        return None
    return candidate if isinstance(candidate, dict) else None


def _validate_answer_shape(answer_type: AnswerType, final_answer: FinalAnswer) -> None:
    """Raise `ValueError` if `final_answer.answer` does not match `answer_type` (§8, step 3).

    An abstention (`not_present=True`) is exempt: the model is telling us it
    found nothing, so `answer` carries no shape requirement.
    """
    if final_answer.not_present:
        return
    answer = final_answer.answer
    scalar_types = (AnswerType.CLASS_NAME, AnswerType.TAG, AnswerType.UNIT_ID, AnswerType.FREE_TEXT)
    list_types = (AnswerType.TAG_SET, AnswerType.UNIT_SET, AnswerType.TAG_PATH)
    if answer_type in scalar_types:
        if not isinstance(answer, str):
            raise ValueError(f"{answer_type} needs a string answer, got {answer!r}")
        return
    if answer_type in list_types:
        if not isinstance(answer, list) or not all(isinstance(item, str) for item in answer):
            raise ValueError(f"{answer_type} needs a list of strings, got {answer!r}")
        return
    if answer_type is AnswerType.COUNT:
        _validate_count_shape(answer)
        return
    raise ValueError(f"final_answer.py has no shape rule for answer_type {answer_type!r}")


def _validate_count_shape(answer: object) -> None:
    """A `COUNT` answer must be an int or a numeric string (§8, step 3's example)."""
    if isinstance(answer, bool):  # bool is an int subclass in Python; not a count
        raise ValueError(f"COUNT needs an int or a numeric string, got {answer!r}")
    if isinstance(answer, int):
        return
    if isinstance(answer, str) and answer.strip().lstrip("-").isdigit():
        return
    raise ValueError(f"COUNT needs an int or a numeric string, got {answer!r}")


def parse_final_answer(raw_text: str, answer_type: AnswerType) -> FinalAnswer:
    """Parse a model's raw reply into a `FinalAnswer`, or raise `FinalAnswerParseError` (§8).

    No retry: an unparseable reply is `PARSE_FAILURE` (ADR-0013 point 3), not
    a call worth repeating.
    """
    payload = _parse_json_object(raw_text)
    if payload is None:
        raise FinalAnswerParseError(f"no JSON object found in model reply: {raw_text!r}")
    try:
        final_answer = FinalAnswer.model_validate(payload)
    except ValidationError as exc:
        raise FinalAnswerParseError(
            f"reply JSON does not match the FinalAnswer schema: {payload!r} ({exc})"
        ) from exc
    try:
        _validate_answer_shape(answer_type, final_answer)
    except ValueError as exc:
        raise FinalAnswerParseError(str(exc)) from exc
    return final_answer


def to_outcome(raw_text: str, answer_type: AnswerType) -> tuple[Outcome, FinalAnswer | None]:
    """Parse a raw model reply into the `Outcome` and `FinalAnswer` a `QuestionResult` needs.

    Never raises: a parse failure is `Outcome.PARSE_FAILURE`, scored data
    rather than a bug (ADR-0013 point 3).
    """
    try:
        return Outcome.ANSWERED, parse_final_answer(raw_text, answer_type)
    except FinalAnswerParseError:
        return Outcome.PARSE_FAILURE, None


#: The caller's "make this call" function. `run_final_step` never talks to a
#: provider itself; the real implementation is `llm.client.ChatClient` (not
#: built yet, QA-T2), and tests pass a canned stand-in instead.
SendChatRequest = Callable[[ChatRequest], ChatResponse]


class FinalStepResult(BaseModel):
    """Everything the shared final-answer step produces for one strategy's one question (§8)."""

    model_config = ConfigDict(frozen=True)

    outcome: Outcome
    #: Set only when `outcome` is `ANSWERED`.
    final_answer: FinalAnswer | None
    #: `None` when no call was made (`DID_NOT_FIT` from the pre-call path) or
    #: the call itself overflowed.
    response: ChatResponse | None
    trace: dict[str, Any]


def run_final_step(
    *,
    pin: ModelPin,
    context: str,
    question_text: str,
    answer_type: AnswerType,
    wall: ContextWall | None,
    send: SendChatRequest,
) -> FinalStepResult:
    """Run the one shared final-answer step every strategy ends with (§7, §8; ADR-0013 point 6).

    Renders the prompt, applies the fit check, and — only if the prompt
    passes it — calls `send`. A `ContextOverflow` raised by `send` is caught
    here and turned into `DID_NOT_FIT`, exactly like the pre-call rejection;
    every other exception `send` raises (for example `ProviderError`) is the
    caller's to handle, since it is not one of `fit.py`'s two `DID_NOT_FIT`
    paths.
    """
    request = render_final_answer_request(
        pin=pin, context=context, question_text=question_text, answer_type=answer_type
    )
    prompt_chars = len(request.messages[0].content)
    decision = check_fit(prompt_chars, wall)
    if not decision.should_call:
        if decision.outcome is None:
            raise RuntimeError(
                "fit.check_fit returned should_call=False without an outcome; "
                "this is a bug in plantgraph.qa.fit"
            )
        return FinalStepResult(
            outcome=decision.outcome, final_answer=None, response=None, trace=decision.trace
        )

    try:
        response = send(request)
    except ContextOverflow as error:
        decision = handle_overflow(prompt_chars, error)
        return FinalStepResult(
            outcome=Outcome.DID_NOT_FIT, final_answer=None, response=None, trace=decision.trace
        )

    outcome, final_answer = to_outcome(response.text, answer_type)
    trace = {**decision.trace, "prompt_chars": prompt_chars}
    if outcome is not Outcome.ANSWERED:
        trace["raw_reply"] = response.text
    return FinalStepResult(
        outcome=outcome, final_answer=final_answer, response=response, trace=trace
    )
