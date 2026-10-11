"""Data models of the EXP-0001 report (design `exp0001-single-sheet.md` sections 8 and 11).

One report holds, per corpus size, the per-arm accuracy/cost/latency cells, the paired differences
between arms, the slope over size, and the verdicts of claims X1-X6.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.stats import Interval
from plantgraph.qa.models import Outcome

#: Arm names. ctx-* are ContextRAG (whole graph in the prompt); cyp and ag are the cascade's two
#: tiers (a Cypher query, a graph-walking agent); cascade_v3 is the offline join of both.
CTX_HIGH = "ctx-high"
CTX_LOW = "ctx-low"
CYP = "cyp"
AG = "ag"
CASCADE = "cascade_v3"
ARMS = (CTX_HIGH, CTX_LOW, CYP, AG, CASCADE)

#: Scopes: `common` = families every ladder size has (primary); `all` = every family at that size.
SCOPE_COMMON = "common"
SCOPE_ALL = "all"

Verdict = Literal["PASS", "FAIL", "REPORTED", "NOT_RUN"]


class QuestionScore(BaseModel):
    """One arm's result on one question, ready for pairing across arms."""

    model_config = ConfigDict(frozen=True)

    qid: str
    family: str
    #: Correct whatever the latency (the uncut accuracy).
    correct: bool
    #: Correct and answered within the cutoff (acc@120).
    correct_at_cutoff: bool
    cost_usd: float
    latency_s: float
    #: Raw outcome of the row that gave the final answer (the last tier tried, if none did).
    outcome: Outcome


class SizePoint(BaseModel):
    """How big one corpus is, and how many characters and tokens ContextRAG's prompt took."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n_sheets: int
    n_occurrence_nodes: int
    #: Median prompt length over ContextRAG-high calls; `None` when that arm has no run here.
    ctx_prompt_chars: int | None
    ctx_prompt_tokens_median: int | None
    chars_per_token: float | None


class ArmCell(BaseModel):
    """One arm on one corpus under one scope."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    scope: str
    n: int
    correct_at_120: int
    acc_at_120: Interval
    acc_uncut: float
    cost_mean: float
    cost_median: float
    latency_median: float
    latency_p90: float
    #: Outcome name -> number of questions (every outcome listed, zeros included).
    outcomes: dict[str, int]


class PairedDelta(BaseModel):
    """a minus b on the same questions, with a paired-bootstrap 95 % interval."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    scope: str
    a: str
    b: str
    n: int
    delta: float
    ci: Interval
    #: What is compared: accuracy within the cutoff, or cost per question in USD.
    metric: Literal["acc@120", "cost_usd"] = "acc@120"


class Trend(BaseModel):
    """Slope of the accuracy difference over log10(sheets), with a bootstrap interval."""

    model_config = ConfigDict(frozen=True)

    scope: str
    slope: float
    ci: Interval
    n_boot: int
    seed: int
    #: The corpora the slope was fitted on, in order of size.
    sizes: list[str]


class ClaimVerdict(BaseModel):
    """The outcome of one pre-registered claim; `wording` is the design note's text, unchanged."""

    model_config = ConfigDict(frozen=True)

    id: str
    wording: str
    value: str
    verdict: Verdict


class LadderReport(BaseModel):
    """Everything the EXP-0001 report prints."""

    model_config = ConfigDict(frozen=True)

    cutoff_s: float
    n_boot: int
    seed: int
    sizes: list[SizePoint]
    #: Scope name -> family names it counts (`all` lists the families seen in any corpus).
    scope_families: dict[str, list[str]]
    cells: list[ArmCell]
    deltas: list[PairedDelta]
    trends: list[Trend]
    claims: list[ClaimVerdict]
    #: Arms that could not be scored, each with the reason (a missing run is stated, never skipped).
    absent: list[str]
    #: X5's wall in sheets, for the figure's marker; `None` when it could not be fitted.
    wall_sheets: float | None = None
