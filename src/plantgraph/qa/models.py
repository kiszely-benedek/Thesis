"""The Q&A data model: questions, answers, outcomes and run records (design `qa-system.md` §4).

A few terms this module leans on, for a reader who knows Python but not the
process-engineering domain:

- **tag**: the short identifier printed next to a piece of equipment or a
  valve on a P&ID (a *piping and instrumentation diagram*, the engineering
  drawing this whole project is about) — for example `"P-101"` for a pump.
  It is the closest thing the drawing has to a variable name.
- **unit**: a named group of equipment that is operated together, such as
  one distillation train. A `unit_id` is the identifier of that group.
- **off-page connector**: a small symbol drawn where a pipe or a signal line
  leaves one drawing sheet and continues on another. It is a drawing
  artefact, not a piece of plant equipment, so a strategy that answers with
  one has misread the diagram.
- **k** (`Question.k`): the number of off-page connectors that stand between
  the evidence for a question's answer, i.e. how many sheets the answer has
  to be pieced together across. `k = 0` means everything needed is on one
  sheet.

Every question in this module carries its own reference answer, computed in
plain Python from the ground-truth plant graph (ADR-0013) — never read back
from the system under test. That is what lets `scoring.py` grade an answer
without a judge, a network call or a database.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.llm.models import ContextWall, ModelPin

#: A value an answer or a reference can take. `list[str]` covers both a
#: `TAG_SET`/`UNIT_SET` (an unordered collection) and a `TAG_PATH` (an
#: ordered one, since a Python list keeps insertion order — no separate
#: "path" container is needed).
AnswerValue = str | int | list[str] | None


class QuestionFamily(str, Enum):
    """One question template family (design `qa-system.md` §9).

    Each family reads a fixed, small slice of the ground-truth plant graph —
    never an equipment attribute (ADR-0021, ADR-0018 A1): only `tag`,
    `node_class`, `unit_id` and the graph's topology.
    """

    LOOKUP_TYPE = "LOOKUP_TYPE"
    LOOKUP_UNIT = "LOOKUP_UNIT"
    NEIGHBOURS_DOWNSTREAM = "NEIGHBOURS_DOWNSTREAM"
    LOOP_ACTUATED_VALVE = "LOOP_ACTUATED_VALVE"
    LOOP_MEASURED_EQUIPMENT = "LOOP_MEASURED_EQUIPMENT"
    FLOW_PATH = "FLOW_PATH"
    UPSTREAM_ISOLATION = "UPSTREAM_ISOLATION"
    CROSS_UNIT = "CROSS_UNIT"
    COUNT_IN_UNIT = "COUNT_IN_UNIT"
    UNANSWERABLE_TAG = "UNANSWERABLE_TAG"
    NO_PATH = "NO_PATH"
    SHEETS_OF_TAG = "SHEETS_OF_TAG"


class AnswerType(str, Enum):
    """The shape a `Question`'s reference answer and a `FinalAnswer.answer` must take.

    `FREE_TEXT` is EXP-0001 only, scored by `judge.py`, never by
    `scoring.py` (`qa-system.md` §8, §10): a rubric judge, not an exact or
    set comparison, decides whether free text is right.
    """

    CLASS_NAME = "CLASS_NAME"
    UNIT_ID = "UNIT_ID"
    TAG = "TAG"
    TAG_SET = "TAG_SET"
    UNIT_SET = "UNIT_SET"
    TAG_PATH = "TAG_PATH"
    COUNT = "COUNT"
    FREE_TEXT = "FREE_TEXT"


class Question(BaseModel):
    """One generated question, its reference answer, and the gold evidence behind it.

    The `evidence_*` fields and `k` are gold: computed by the question
    generator from the ground-truth graph so the harness can report accuracy
    by cross-sheet difficulty. A retrieval strategy is given only
    `Question.text` and must never read any other field on this model
    (`qa-system.md` §7, "the fairness rules").
    """

    model_config = ConfigDict(frozen=True)

    # Identity
    question_id: str
    corpus_id: str
    family: QuestionFamily
    template_id: str
    template_version: str
    text: str
    answer_type: AnswerType

    # Reference answer
    #: False for `UNANSWERABLE_TAG` and `NO_PATH`: the correct behaviour is
    #: to abstain, so there is no reference value to compute.
    answerable: bool
    reference: AnswerValue

    # Gold evidence, read by the harness only — never by a strategy
    evidence_tags: list[str] = Field(default_factory=list)
    evidence_sheets: list[str] = Field(default_factory=list)
    #: Off-page connectors crossed by the evidence; `None` for an
    #: unanswerable question, where there is no evidence to cross anything.
    k: int | None = None
    anchors: list[str] = Field(default_factory=list)
    generator_seed: int


class FinalAnswer(BaseModel):
    """The parsed JSON `{"answer": ..., "not_present": bool}` every strategy ends with (§8)."""

    model_config = ConfigDict(frozen=True)

    answer: AnswerValue
    not_present: bool


class Outcome(str, Enum):
    """What happened to one strategy call on one question (`qa-system.md` §4, §8).

    Only `ANSWERED` carries a scoreable `FinalAnswer`. Every other value is
    scored wrong in end-to-end accuracy (§11); `PARSE_FAILURE` in particular
    is its own outcome, not folded into a wrong answer, so its rate can be
    reported on its own (ADR-0013 point 3).
    """

    ANSWERED = "ANSWERED"
    #: The final prompt did not fit the model's measured context wall
    #: (`fit.py`); no call was made, or the call itself overflowed.
    DID_NOT_FIT = "DID_NOT_FIT"
    #: The final step's JSON could not be parsed or did not match
    #: `answer_type`, with no retry (§8, point 4).
    PARSE_FAILURE = "PARSE_FAILURE"
    #: Retrieval itself failed before the final step was reached (for
    #: example CypherRAG's query raised a syntax error).
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    #: The provider kept erroring after the transport-level retries; excluded
    #: from accuracy rather than scored wrong (`qa-system.md` §11, harness).
    PROVIDER_ERROR = "PROVIDER_ERROR"


class RetrievalResult(BaseModel):
    """What a strategy's retrieval step produced, before the shared final-answer step runs."""

    model_config = ConfigDict(frozen=True)

    #: `None` when retrieval itself failed or was skipped; see `failure`.
    context: str | None
    failure: Outcome | None
    #: Free-form bookkeeping for the report: routed sheets, Cypher text, row
    #: count, truncation, anchors — whatever that strategy wants to explain.
    trace: dict[str, Any] = Field(default_factory=dict)


class QuestionResult(BaseModel):
    """One scored row of a run's `answers.jsonl`: one strategy's answer to one question, once."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    question_id: str
    strategy: str
    #: Which attempt this is, for strategies run more than once (§12 step 6,
    #: "repeats"). 0 for a single-repeat run.
    repeat: int
    outcome: Outcome
    #: `None` unless `outcome` is `ANSWERED`.
    final_answer: FinalAnswer | None
    #: Programmatic scoring result (`scoring.score_answer`); `False` for
    #: every non-`ANSWERED` outcome.
    correct: bool
    #: The lenient set/path overlap score; `None` for scalar answer types and
    #: for every non-`ANSWERED` outcome (`scoring.py`).
    f1: float | None
    prompt_tokens: int
    completion_tokens: int
    #: `None` when the provider's `usage` block did not report a cost.
    cost_usd: float | None
    latency_s: float
    #: Length of the final prompt actually sent (or attempted), for the
    #: did-not-fit and context-wall analysis.
    context_chars: int
    trace: dict[str, Any] = Field(default_factory=dict)


class CorpusRecord(BaseModel):
    """The size, configuration and pipeline timing of one corpus (design `qa-system.md` §4, R6).

    Two node counts are kept apart because they count different graphs
    (`qa-system.md` §2.1): the **store** count is the occurrence graph loaded
    into Neo4j, which also holds off-page-connector stub nodes; the **plant**
    count is the ground-truth graph the question generator reads, which has
    none. Reporting only one of them would silently mix the two.
    """

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    role: str = Field(pattern=r"^(dev|test)$")
    generator_config: GeneratorConfig
    split_config: SplitConfig
    n_sheets: int
    #: Occurrence-graph node count as loaded into Neo4j (`IngestCounts.n_nodes`).
    n_store_nodes: int
    n_connector_pairs_predicted: int
    #: Ground-truth plant graph node/edge counts (`CorpusArtifacts.plant`), never the store's.
    n_plant_nodes: int
    n_plant_edges: int
    source_graph_hash: str
    #: Verbatim from `IngestResult.stage_seconds` (§2.1 R6): one entry per
    #: pipeline stage, in seconds.
    stage_seconds: dict[str, float]


class RunConfig(BaseModel):
    """A run's frozen configuration, written before its first call (ADR-0014's freeze, §4, §11).

    The harness refuses to start a `reported` run unless every field a
    reported number depends on — the pin, the prompt hashes, the question
    set and the context wall — is already filled in. That check is the
    harness's job (`harness.py`, QA-T10), not this model's: fields that are
    only known once the pilot has run stay optional here so a config can
    still be built and inspected before that point.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    #: `"EXP-0001"`, `"EXP-0002"`, or a pilot/tooling run's own name (§12).
    experiment: str
    #: Whether this run's numbers may be cited in the thesis (ADR-0014).
    reported: bool
    corpora: list[str]
    #: Strategy name to its parameters, e.g. `{"hierarchical": {"sheet_hops": 1}}`.
    strategies: dict[str, dict[str, Any]]
    answer_pin: ModelPin
    #: Primary and sensitivity judge, EXP-0001 only; empty for EXP-0002 runs.
    judge_pins: list[ModelPin] = Field(default_factory=list)
    #: Prompt file name to its sha256, so a prompt edit is visible in the run record (§3).
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    question_set_sha256: str
    #: `None` until the pilot has measured it (§12); required before `reported=True`.
    context_wall: ContextWall | None = None
    git_commit: str
    git_dirty: bool
    created_at: datetime
    #: Set only by an explicit CLI flag the user types, never by an
    #: environment variable (`qa-system.md` §6): a key being present is not permission to spend.
    allow_paid_calls: bool = False
