"""The typed pieces of the EXP-0009 sealed analysis: a claim row, a generic table, the report.

The analysis (design §19.11) turns the saved sealed runs into numbers. Every number sits in one of
two shapes: a **claim row** (one pre-registered claim with its interval and verdict) or a **table**
(a descriptive list). Both name the run ids they were computed from, so each figure can be traced
back to the run folders under `p1c/runs/`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.cascade.stats import Interval

#: a table cell: text, a count, a share or nothing (rendered as "-")
TableCell = str | int | float | None


class ClaimStatus(str, Enum):
    """How a claim ended: judged, only described, not run, or lacking an input."""

    PASS = "PASS"
    FAIL = "FAIL"
    DESCRIPTIVE = "DESCRIPTIVE"  # an interval with no pass rule (SB1, the data effect)
    NOT_RUN = "NOT_RUN"  # the arm never ran (B after a failed G1-B or G1-B2) or an input is absent
    INCOMPLETE = "INCOMPLETE"  # EXP-0008's wording: a comparison could not be formed


class ClaimRow(BaseModel):
    """One claim: its rule in words, the interval it was judged on and the runs behind it."""

    model_config = ConfigDict(frozen=True)

    claim: str
    arm: str
    scope: str
    #: the pre-registered pass rule (PREREG A, design §12.1), copied in words
    rule: str
    status: ClaimStatus
    #: a difference in accuracy at the cutoff (a share, not points), or seconds for K3's median
    #: latency; `None` when the claim was not run
    interval: Interval | None = None
    unit: str = "acc@C"
    #: questions behind the interval, summed over the plants it pools
    n_questions: int | None = None
    detail: str = ""
    runs: tuple[str, ...] = ()


class Table(BaseModel):
    """A descriptive list: a header, rows of numbers and text, the runs it reads."""

    model_config = ConfigDict(frozen=True)

    name: str
    title: str
    note: str = ""
    header: list[str]
    rows: list[list[TableCell]]
    runs: list[str] = Field(default_factory=list)


class PlantRecord(BaseModel):
    """One sealed plant as the analysis found it: size, run folders and question counts."""

    model_config = ConfigDict(frozen=True)

    plant_id: str
    scale: int
    sheets: int
    a2_runs: list[str]
    b_runs: list[str]
    n_a2_questions: int
    n_b_questions: int


class AnalysisReport(BaseModel):
    """Everything T17 writes: the claims, the descriptive tables and what could not be computed."""

    model_config = ConfigDict(frozen=True)

    root: str
    b_sealed: bool
    #: what "scope R", "scope X" and the bootstrap mean in this report
    scope_note: str
    plants: list[PlantRecord]
    claims: list[ClaimRow]
    #: EXP-0008's own verdict lines for the A2 claims (cost elasticity included), verbatim
    exp0008_verdicts: list[str] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
