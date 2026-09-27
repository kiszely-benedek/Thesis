"""Programmatic scoring of a strategy's answer against the computed reference (ADR-0013, §9, §11).

No network call, no database read and no LLM judge is used here — every
function is plain Python over the `Question` and `FinalAnswer` models, which
is what lets a run be re-scored later from `answers.jsonl` alone (ADR-0013's
"cheap, deterministic, and scales to thousands").

**What "correct" means, by answer type** (`qa-system.md` §9, "Scoring"):

- `CLASS_NAME`, `TAG`, `UNIT_ID`: exact match after normalization.
- `COUNT`: integer equality; a numeric string counts the same as an int.
- `TAG_SET`, `UNIT_SET`: correct only for an **exact set match** — the
  precision/recall/F1 numbers are a *lenient* secondary view, reported
  alongside but never substituted for `correct`.
- `TAG_PATH`: correct if the path (after off-page connectors are stripped
  out, since the model was told to omit them) starts and ends at the right
  tags and every step is a real ground-truth edge — any such path counts,
  not only the one reference route.
- Abstention (`FinalAnswer.not_present`): correct exactly when it agrees with
  `Question.answerable` — set on an answerable question, this is a **false
  abstention**, always wrong regardless of what `answer` says.
- Every outcome other than `Outcome.ANSWERED` (a did-not-fit, a parse
  failure, a retrieval or provider error) is wrong by definition, with no
  lenient score: there is no answer to compare.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.models import AnswerType, AnswerValue, FinalAnswer, Outcome, Question

#: One or more whitespace characters, collapsed to a single space by `normalize_scalar`.
_WHITESPACE_RE = re.compile(r"\s+")

#: A leading "UNIT" or "U" label in front of a unit number, e.g. "UNIT 12", "UNIT12", "U12".
#: The lookahead requires a digit right after, so a unit actually named "U" or
#: "Unicorn" is left alone — only a number-prefixing label is a label, not a name.
_UNIT_PREFIX_RE = re.compile(r"^(?:UNIT|U)\s*(?=\d)")


def normalize_scalar(value: str) -> str:
    """Fold case and whitespace so `"  p-101 "` and `"P-101"` compare equal.

    Uppercases, strips leading/trailing whitespace, and collapses any run of
    internal whitespace to a single space.
    """
    return _WHITESPACE_RE.sub(" ", value.strip()).upper()


def normalize_unit_id(value: str) -> str:
    """`normalize_scalar`, plus stripping a leading "UNIT"/"U" label.

    A model may answer "unit 12", "UNIT12" or "U 12" where the ground truth
    is just "12"; all normalize to the same string.
    """
    return _UNIT_PREFIX_RE.sub("", normalize_scalar(value))


def score_scalar(reference: str, answer: str) -> bool:
    """Exact match after `normalize_scalar` — used for `CLASS_NAME` and `TAG`."""
    return normalize_scalar(reference) == normalize_scalar(answer)


def score_unit_id(reference: str, answer: str) -> bool:
    """Exact match after `normalize_unit_id` — used for `UNIT_ID`."""
    return normalize_unit_id(reference) == normalize_unit_id(answer)


def score_count(reference: int, answer: int | str) -> bool:
    """Integer equality for `COUNT`; a numeric string is accepted as itself (`qa-system.md` §9).

    A non-numeric string is a wrong answer, not an error: by the time
    scoring runs, `final_answer.py` has already rejected anything that could
    not be read as a count at all (`PARSE_FAILURE`), so anything reaching
    here is data, not a bug.
    """
    if isinstance(answer, int):
        return reference == answer
    try:
        return reference == int(answer.strip())
    except ValueError:
        return False


class SetScore(BaseModel):
    """Precision, recall, F1 and exact-match for a `TAG_SET` / `UNIT_SET` answer."""

    model_config = ConfigDict(frozen=True)

    precision: float
    recall: float
    f1: float
    #: True only for an exact set match — the strict variant `qa-system.md` §9 requires.
    correct: bool


def score_set(
    reference: Iterable[str],
    answer: Iterable[str],
    *,
    normalize: Literal["scalar", "unit_id"] = "scalar",
) -> SetScore:
    """Score a set-valued answer against its reference (`qa-system.md` §9).

    Both sides are normalized and de-duplicated before comparison, so
    duplicate or differently-cased entries never change the result. Two
    empty sets are a perfect match (there is nothing to find and nothing
    spurious was added); an empty reference with a non-empty answer is
    always wrong, since every entry in the answer is then spurious.

    Args:
        reference: the ground-truth tags.
        answer: the model's tags.
        normalize: `"scalar"` for a `TAG_SET` (equipment and valve tags),
            `"unit_id"` for a `UNIT_SET`, so a `UNIT`/`U` label does not
            cause a spurious mismatch.
    """
    fold = normalize_unit_id if normalize == "unit_id" else normalize_scalar
    reference_set = {fold(tag) for tag in reference}
    answer_set = {fold(tag) for tag in answer}

    if not reference_set and not answer_set:
        return SetScore(precision=1.0, recall=1.0, f1=1.0, correct=True)

    true_positives = len(reference_set & answer_set)
    precision = true_positives / len(answer_set) if answer_set else 0.0
    recall = true_positives / len(reference_set) if reference_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return SetScore(precision=precision, recall=recall, f1=f1, correct=reference_set == answer_set)


class PathScore(BaseModel):
    """Validity and lenient F1 for a `TAG_PATH` answer (`qa-system.md` §9)."""

    model_config = ConfigDict(frozen=True)

    #: True iff the path starts at the reference's first tag, ends at its
    #: last, and every consecutive pair is a ground-truth edge. Any path
    #: meeting that bar counts — not only the one reference route.
    correct: bool
    #: Set F1 of the (connector-stripped) answer path against the reference
    #: path's tags, reported as the lenient view even when `correct` is False.
    f1: float


def score_path(
    reference_path: Sequence[str],
    answer_path: Sequence[str],
    *,
    connector_tags: Iterable[str],
    valid_edges: Iterable[tuple[str, str]],
) -> PathScore:
    """Score a `TAG_PATH` answer against the reference path (`qa-system.md` §9).

    Off-page connectors are drawing artefacts, not equipment or valves — the
    final-step prompt tells the model to omit them (§8) — so any connector
    tag in the answer is stripped before either check, rather than treated
    as a wrong or a missing tag by itself. Any *other* tag not on a
    `valid_edges` pair between two real items makes the path invalid.

    Args:
        reference_path: the ground-truth tag sequence, first tag to last.
        answer_path: the model's tag sequence, in the order it named them.
        connector_tags: every off-page connector tag on this corpus, so they
            can be told apart from a genuinely wrong equipment tag.
        valid_edges: the ground-truth graph's `(from_tag, to_tag)` flow edges
            (`send_to`), the only edges a valid path may step across.
    """
    connectors = {normalize_scalar(tag) for tag in connector_tags}
    cleaned_answer = [
        tag for tag in (normalize_scalar(t) for t in answer_path) if tag not in connectors
    ]
    reference = [normalize_scalar(tag) for tag in reference_path]
    edges = {(normalize_scalar(a), normalize_scalar(b)) for a, b in valid_edges}

    correct = _is_valid_ordered_path(cleaned_answer, reference, edges)
    f1 = score_set(reference, cleaned_answer).f1
    return PathScore(correct=correct, f1=f1)


def _is_valid_ordered_path(
    path: list[str], reference: list[str], edges: set[tuple[str, str]]
) -> bool:
    """A cleaned answer path is valid iff it runs A -> ... -> B over real edges only."""
    if not path or not reference:
        return False
    if path[0] != reference[0] or path[-1] != reference[-1]:
        return False
    # strict=False: path[1:] is one shorter than path by construction (pairwise steps).
    return all(
        (step_from, step_to) in edges for step_from, step_to in zip(path, path[1:], strict=False)
    )


def score_abstention(*, answerable: bool, not_present: bool) -> bool:
    """Whether a model's `not_present` flag was the right call (`qa-system.md` §9, §11).

    For an **unanswerable** question this is the whole score: correct iff
    `not_present` is True. For an **answerable** one, `not_present=True` is
    always wrong — a **false abstention** — regardless of the `answer`
    field, because the plant graph does have the information the model
    claimed was missing. This function judges only the abstention flag;
    callers still run a type-specific scorer when the question is answerable
    and the model did not abstain.
    """
    return not_present if not answerable else not not_present


class ScoredAnswer(BaseModel):
    """The two fields `QuestionResult` needs: whether the answer was right, and its lenient F1."""

    model_config = ConfigDict(frozen=True)

    correct: bool
    #: `None` for scalar answer types (`CLASS_NAME`, `UNIT_ID`, `TAG`, `COUNT`)
    #: and for every non-`ANSWERED` outcome; set only where a set/path
    #: overlap score is meaningful.
    f1: float | None


def score_answer(
    question: Question,
    outcome: Outcome,
    final_answer: FinalAnswer | None,
    *,
    connector_tags: Iterable[str] = (),
    valid_edges: Iterable[tuple[str, str]] = (),
) -> ScoredAnswer:
    """Score one strategy's answer to one question end to end (`qa-system.md` §9, §11).

    Every outcome other than `ANSWERED` — `DID_NOT_FIT`, `PARSE_FAILURE`,
    `RETRIEVAL_ERROR`, `PROVIDER_ERROR` — scores wrong with no lenient F1:
    there is no parsed answer to compare (ADR-0013 point 3). `connector_tags`
    and `valid_edges` matter only for `TAG_PATH` questions and are otherwise
    ignored.

    Raises:
        ValueError: `outcome` is `ANSWERED` but `final_answer` is `None`
            (a contract the caller must uphold), or `question.answer_type`
            is `FREE_TEXT` (EXP-0001's rubric-judged answers are scored by
            `judge.py`, never here).
    """
    if outcome is not Outcome.ANSWERED:
        return ScoredAnswer(correct=False, f1=None)
    if final_answer is None:
        raise ValueError(
            f"outcome is ANSWERED but final_answer is None for question {question.question_id!r}"
        )

    abstained_correctly = score_abstention(
        answerable=question.answerable, not_present=final_answer.not_present
    )
    if not question.answerable:
        return ScoredAnswer(correct=abstained_correctly, f1=None)
    if final_answer.not_present:
        return ScoredAnswer(correct=False, f1=None)  # a false abstention: always wrong

    return _score_present_answer(
        question, final_answer.answer, connector_tags=connector_tags, valid_edges=valid_edges
    )


def _score_present_answer(
    question: Question,
    answer: AnswerValue,
    *,
    connector_tags: Iterable[str],
    valid_edges: Iterable[tuple[str, str]],
) -> ScoredAnswer:
    """Dispatch an answerable, non-abstaining answer to its answer-type-specific scorer."""
    answer_type = question.answer_type
    reference = question.reference

    if answer_type in (AnswerType.CLASS_NAME, AnswerType.TAG):
        return ScoredAnswer(correct=score_scalar(_as_str(reference), _as_str(answer)), f1=None)
    if answer_type is AnswerType.UNIT_ID:
        return ScoredAnswer(correct=score_unit_id(_as_str(reference), _as_str(answer)), f1=None)
    if answer_type is AnswerType.COUNT:
        return ScoredAnswer(correct=score_count(_as_int(reference), _as_count(answer)), f1=None)
    if answer_type in (AnswerType.TAG_SET, AnswerType.UNIT_SET):
        normalize: Literal["scalar", "unit_id"] = (
            "unit_id" if answer_type is AnswerType.UNIT_SET else "scalar"
        )
        set_score = score_set(_as_str_list(reference), _as_str_list(answer), normalize=normalize)
        return ScoredAnswer(correct=set_score.correct, f1=set_score.f1)
    if answer_type is AnswerType.TAG_PATH:
        path_score = score_path(
            _as_str_list(reference),
            _as_str_list(answer),
            connector_tags=connector_tags,
            valid_edges=valid_edges,
        )
        return ScoredAnswer(correct=path_score.correct, f1=path_score.f1)
    raise ValueError(
        f"scoring.py has no rule for answer_type {answer_type!r}: FREE_TEXT is judged by "
        "judge.py's rubric, not scored programmatically"
    )


def _as_str(value: AnswerValue) -> str:
    """Read a scalar (`CLASS_NAME`/`TAG`/`UNIT_ID`) reference or answer as a string."""
    if not isinstance(value, str):
        raise ValueError(f"expected a string answer, got {value!r}")
    return value


def _as_int(value: AnswerValue) -> int:
    """Read a `COUNT` reference, which the question generator always writes as an int."""
    if not isinstance(value, int):
        raise ValueError(f"expected an int reference for a COUNT question, got {value!r}")
    return value


def _as_count(value: AnswerValue) -> int | str:
    """Read a `COUNT` answer, which the model may write as an int or a numeric string."""
    if isinstance(value, int | str):
        return value
    raise ValueError(f"expected an int or a numeric string COUNT answer, got {value!r}")


def _as_str_list(value: AnswerValue) -> list[str]:
    """Read a `TAG_SET`/`UNIT_SET`/`TAG_PATH` reference or answer as a list of tags."""
    if not isinstance(value, list):
        raise ValueError(f"expected a list of tags, got {value!r}")
    return value
