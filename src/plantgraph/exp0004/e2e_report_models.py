"""Data shapes of the end-to-end (E2E) report: one arm's inputs and the report's tables."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.stats import Interval, PairedDifference

#: Arm labels. R5 is the already-paid baseline on exact tags; V is the tag-variant corpus.
R5_ARM = "R5"
RESOLVER_ARMS = ("d0", "d2", "d4")


def v_arm(resolver: str) -> str:
    """Label of the variant-corpus arm run with the given resolver, e.g. `V-d2`."""
    return f"V-{resolver}"


class ArmData(BaseModel):
    """What the report needs from one arm: per-question correctness plus tier outcomes and spend."""

    model_config = ConfigDict(frozen=True)

    label: str
    #: question id -> the cascade's final answer was correct within the cutoff (acc@120).
    correct: dict[str, bool]
    #: tier name -> outcome name (ANSWERED, ...) -> number of questions.
    outcomes: dict[str, dict[str, int]]
    #: Real spend of the paid run: sum of `cost_usd` of calls not served from the cache.
    spend_usd: float


class ArmRow(BaseModel):
    """One arm's headline accuracy."""

    model_config = ConfigDict(frozen=True)

    label: str
    n: int
    n_correct: int
    accuracy: Interval
    #: New spend only (cache misses). The V arms reused R5's cache, so this is NOT a cost per arm
    #: and must not be compared with R5's full spend.
    spend_usd: float


class ClaimRow(BaseModel):
    """One pre-registered claim: a paired difference and its verdict."""

    model_config = ConfigDict(frozen=True)

    claim: str
    description: str
    rule: str
    difference: PairedDifference
    passed: bool


class GroupRow(BaseModel):
    """Accuracy of one arm inside one group of questions (a family, or exposed/unexposed)."""

    model_config = ConfigDict(frozen=True)

    group: str
    arm: str
    n: int
    n_correct: int


class E2EReport(BaseModel):
    """Everything `report.md` prints."""

    model_config = ConfigDict(frozen=True)

    cutoff_s: float
    policy: str
    n_questions: int
    arms: list[ArmRow]
    claims: list[ClaimRow]
    families: list[GroupRow]
    exposure: list[GroupRow]
    #: arm label -> tier name -> outcome name -> count.
    outcomes: dict[str, dict[str, dict[str, int]]]
    notes: list[str]
