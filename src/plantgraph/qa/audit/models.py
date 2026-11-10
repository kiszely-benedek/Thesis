"""Data shapes of the scorer audit: what is selected, what the judge sees, what it answered.

Two kinds of data are kept apart on purpose. `JudgeInput` is everything the judge may see; it
has no field for the scorer's verdict, so a prompt built from it cannot leak one. `AuditItem`
and `AuditRecord` carry the scorer's verdict for the report, and never reach the prompt.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.models import AnswerType, AnswerValue, Outcome, QuestionFamily

#: The selection tiers, in the registered budget order (review-fixes §5.3). The three `pilot_*`
#: strata are the gate-G2 pilot; the rest are the audit proper.
Stratum = Literal[
    "pilot_defect_valves",
    "pilot_defect_parse",
    "pilot_control",
    "wrong",
    "right_min",
    "contextrag_wrong",
    "right_extra",
]

#: The strata whose row is expected to be judged "correct" or "ambiguous_question" by a sound judge.
PILOT_DEFECT_STRATA: frozenset[str] = frozenset({"pilot_defect_valves", "pilot_defect_parse"})


class JudgeVerdict(str, Enum):
    """The judge's three answers about the system's answer."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    AMBIGUOUS_QUESTION = "ambiguous_question"


class JudgeReply(BaseModel):
    """The JSON object the judge is asked to return."""

    model_config = ConfigDict(frozen=True)

    verdict: JudgeVerdict
    #: Whether the benchmark's own reference answer looks right to the judge.
    reference_ok: bool
    reason: str


class SourceRow(BaseModel):
    """One stored answer row joined with its question: the audit's unit of selection."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    strategy: str
    question_id: str
    corpus_id: str
    family: QuestionFamily
    #: Plant size label parsed from the corpus id, e.g. "100" for `H100g21p1`.
    scale: str
    outcome: Outcome
    #: The deterministic scorer's verdict; never shown to the judge.
    scorer_correct: bool
    #: Canonical text of the parsed answer (or of the raw reply when nothing parsed): rows with
    #: the same question and key are one answer for the audit.
    answer_key: str


class AuditItem(BaseModel):
    """One row chosen for the audit or the pilot, with the reason it was chosen."""

    model_config = ConfigDict(frozen=True)

    stratum: Stratum
    row: SourceRow


class JudgeInput(BaseModel):
    """Everything the judge may see about one row. No scorer verdict, outcome or flag is here."""

    model_config = ConfigDict(frozen=True)

    question_text: str
    answer_type: AnswerType
    #: The system's reply text. A run that kept only the parsed answer shows it in the same JSON
    #: form the model was asked to write, so every row has a reply and none says how it was read.
    raw_reply: str
    #: The benchmark's reference answer (may be wrong); `None` for an unanswerable question.
    reference: AnswerValue
    answerable: bool
    plant_excerpt: str


class AuditRecord(BaseModel):
    """One judged row: the item, the judge's reply and what the call cost."""

    model_config = ConfigDict(frozen=True)

    item: AuditItem
    reply: JudgeReply
    prompt_chars: int
    #: Hash of the judge prompt template behind this verdict; a revised prompt judges again.
    template_sha256: str = ""
    prompt_tokens: int
    completion_tokens: int
    #: Cost of this call as billed; 0.0 when served from the cache.
    paid_usd: float = Field(ge=0.0)
