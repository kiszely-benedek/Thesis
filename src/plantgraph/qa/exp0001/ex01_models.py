"""The data types of the EX01 runner and its blind review (design `exp0001-single-sheet.md` §11).

EX01 is ChatP&ID's example drawing. Its five scored questions have free-text answers, so no program
can mark them; a person does, against a checklist written before any answer existed. These models
carry the answers, the checklist, the person's verdicts and the frozen record of the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.llm.models import ModelPin
from plantgraph.qa.models import AnswerType, Outcome

#: The arm derived offline from the two tier arms (never called): the thesis's system.
CASCADE_ARM = "cascade_v3"


@dataclass(frozen=True)
class Ex01Question:
    """One of ChatP&ID's questions as the strategies see it: an id, the text, a free-text answer."""

    question_id: str
    text: str
    answer_type: AnswerType = AnswerType.FREE_TEXT


class Ex01ChecklistItem(BaseModel):
    """What a correct answer to one EX01 question must contain (written before any answer)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    qid: str
    #: Equipment or valve tags that must all appear in the answer.
    required_tags: list[str]
    #: True when the tags must appear in the order listed (a flow path).
    ordered: bool
    #: Other wordings accepted for a required tag, e.g. {"P4711": ["inlet"]}.
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    #: Tags that must not be asserted as part of the answer (the reviewer judges the context).
    forbidden_tags: list[str] = Field(default_factory=list)
    #: Claims a program cannot find by tag; the reviewer checks each one.
    required_statements: list[str] = Field(default_factory=list)
    note: str = ""


class Ex01AnswerRow(BaseModel):
    """One answer of one arm to one EX01 question in one repeat: a line of `answers.jsonl`."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    qid: str
    #: `ctx-high`, `cyp`, ... or `cascade_v3` (derived, see `ex01_cascade.py`).
    arm: str
    #: 1-based; repeat n uses the cache file `cache_ex01_r{n}.sqlite`.
    repeat: int
    outcome: Outcome
    #: The free-text answer; `None` unless the outcome is ANSWERED.
    answer_text: str | None
    not_present: bool
    #: Every model call of the question, final and retrieval-side; `None` if one lacked a cost.
    cost_usd: float | None
    #: Recorded model-call latency (final plus retrieval-side); local compute is kept apart.
    latency_s: float
    #: Wall time outside model calls (database, serialization); added to `latency_s` for totals.
    local_compute_s: float = 0.0
    prompt_tokens: int
    completion_tokens: int
    #: Characters of the final prompt (ContextRAG: the whole serialized graph).
    context_chars: int
    #: The host that served the final call; `None` when unknown (e.g. a stored fake reply).
    provider: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)


class Ex01Verdict(BaseModel):
    """The reviewer's judgement of one blind answer, written to `ex01_verdicts.json`."""

    model_config = ConfigDict(frozen=True)

    blind_id: str
    qid: str
    verdict: Literal["correct", "wrong"]
    reason: str
    reviewer: str


class Ex01ArmRecord(BaseModel):
    """One arm as frozen in `run_config.json`: what it runs and under which pin."""

    model_config = ConfigDict(frozen=True)

    strategy: str
    params: dict[str, Any]
    pin: ModelPin
    pin_sha256: str
    #: Call-time budget per question in seconds (120 for the tiers, 300 for ContextRAG).
    deadline_s: float
    #: Why the arm cannot run on EX01 without touching frozen code; `None` when it can.
    not_applicable: str | None = None


class Ex01RunConfig(BaseModel):
    """The EX01 run's frozen record, written once before the first call."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    experiment: str
    created_at: datetime
    git_commit: str
    git_dirty: bool
    corpus_id: str
    ingest_sha256: str
    arms: dict[str, Ex01ArmRecord]
    repeats: int = Field(ge=1)
    primer: bool
    prompt_hashes: dict[str, str]
    question_file: str
    question_file_sha256: str
    qids: list[str]
    cascade_policy: str
    cascade_policy_sha256: str
    #: This invocation's money settings: a resume may change them (they are not measured).
    allow_paid_calls: bool
    cap_usd: float | None


#: Run-config fields a resume may change: when and where it started, and its money settings.
VOLATILE_CONFIG_FIELDS = {"created_at", "git_commit", "git_dirty", "allow_paid_calls", "cap_usd"}


class TagHits(BaseModel):
    """What the automatic tag check found in one answer (advisory; a person decides)."""

    model_config = ConfigDict(frozen=True)

    found: list[str]
    missing: list[str]
    #: Forbidden tags that appear anywhere in the answer; the reviewer checks the context.
    forbidden_present: list[str]
    #: Whether the found tags come in the checklist order; `None` when order does not matter.
    order_ok: bool | None


class BlindKeyEntry(BaseModel):
    """The secret behind one blind id: which arm and repeat wrote it, and the tag check."""

    model_config = ConfigDict(frozen=True)

    blind_id: str
    qid: str
    arm: str
    repeat: int
    #: True when the row has no answer text (a timeout, an error); it is counted wrong unseen.
    no_answer: bool
    tag_hits: TagHits | None
