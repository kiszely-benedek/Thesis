"""The data model of the infrastructure report: spreads, table rows, self-checks, price.

Everything here is plain data. `report.py` fills it from measurements and
`report_render.py` writes it as Markdown, so neither needs to know the other.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: A repeated measurement whose largest value is more than this many times its smallest is flagged.
SPREAD_FLAG_RATIO = 1.5

#: Where a strategy row comes from: a zero-spend replay of the whole question, a replay of only
#: the database part (the Cypher tier's stored queries, no model call), or the original run.
RowBasis = Literal["replay", "db_replay", "old_run"]

#: `flag` is a warning the reader must see, not a failure of the measurement.
CheckStatus = Literal["pass", "fail", "flag"]


class Spread(BaseModel):
    """The repeats of one quantity: median, smallest and largest value."""

    model_config = ConfigDict(frozen=True)

    median: float
    minimum: float
    maximum: float
    n_repeats: int

    @property
    def ratio(self) -> float | None:
        """Largest over smallest; `None` when the smallest is not positive."""
        return self.maximum / self.minimum if self.minimum > 0 else None

    @property
    def flagged(self) -> bool:
        """True when the repeats disagree by more than `SPREAD_FLAG_RATIO`."""
        ratio = self.ratio
        return ratio is not None and ratio > SPREAD_FLAG_RATIO


class SelfCheck(BaseModel):
    """One line of the report's own accuracy statement (design note section 8)."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: CheckStatus
    detail: str


class ReferencePrice(BaseModel):
    """A public on-demand price, filled in by hand: where it came from and when it was read."""

    model_config = ConfigDict(frozen=True)

    provider: str
    region: str
    instance: str
    vcpu: int
    ram_gib: float
    usd_per_hour: float = Field(gt=0)
    url: str
    accessed: str

    @field_validator("url", "accessed")
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("expected the price source's url and access date, found a blank")
        return value


class CorpusFootprintRow(BaseModel):
    """Table I1: what one corpus costs once to build and holds while it waits."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    #: Logical sizes (sheets, nodes, relationships, properties): exact, machine-independent.
    sizes: dict[str, int]
    #: Every measured quantity by name, with the spread over its repeats.
    quantities: dict[str, Spread]
    #: Free-text warnings for this corpus (e.g. a stale metric).
    notes: list[str] = Field(default_factory=list)


class StrategyComputeRow(BaseModel):
    """Table I2: the local compute of one strategy on one corpus, per question."""

    model_config = ConfigDict(frozen=True)

    role: str
    strategy: str
    corpus_id: str
    basis: RowBasis
    needs_database: bool
    needs_memory_graph: bool
    n_questions: int
    local_median_s: float
    local_p90_s: float
    local_max_s: float
    local_sum_s: float
    #: Sums over all questions; `None` for an old run, which had no split timers.
    db_client_sum_s: float | None
    db_server_sum_s: float | None
    graph_api_sum_s: float | None
    other_sum_s: float | None
    #: Local compute over (recorded model latency + local compute), from the sums.
    local_share_of_latency: float
    token_usd_per_question: float
    n_cost_missing: int


class GrowthRow(BaseModel):
    """Table I3: one quantity on a smaller and a larger corpus, and how much it grew."""

    model_config = ConfigDict(frozen=True)

    name: str
    from_corpus: str
    to_corpus: str
    from_value: float
    to_value: float

    @property
    def ratio(self) -> float | None:
        """Larger over smaller; `None` when the smaller value is zero."""
        return self.to_value / self.from_value if self.from_value > 0 else None


class MoneyRow(BaseModel):
    """Table I4: marginal and token cost per question for one strategy and corpus."""

    model_config = ConfigDict(frozen=True)

    role: str
    corpus_id: str
    marginal_usd_per_question: float
    token_usd_per_question: float


class InfraReport(BaseModel):
    """The whole report, ready to render."""

    model_config = ConfigDict(frozen=True)

    machine_summary: str
    git_commit: str
    git_dirty: bool
    checks: list[SelfCheck]
    footprints: list[CorpusFootprintRow]
    compute: list[StrategyComputeRow]
    growth: list[GrowthRow]
    #: `None` without a price file: the report then has no money table.
    reference_price: ReferencePrice | None
    money: list[MoneyRow]
