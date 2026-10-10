"""The data model of the cascade report: per-corpus results, the S1-S3 and LB-1/LB-2 verdicts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.cascade.evaluate import Comparison, LatencyBound, Summary


class Cell(BaseModel):
    """Correct answers out of the questions in one group, for one policy."""

    model_config = ConfigDict(frozen=True)

    correct: int
    total: int


class AcceptanceResult(BaseModel):
    """How well the first tier's acceptance rule judges its own answers (against gold)."""

    model_config = ConfigDict(frozen=True)

    n_accepted: int
    n_accepted_correct: int
    n_first_tier_correct: int
    #: Share of accepted answers that are correct.
    precision: float
    #: Share of the correct first-tier answers that were accepted rather than escalated.
    recall: float


class RandomSummary(BaseModel):
    """Random escalation at the policy's own escalation count (see `references.py`)."""

    model_config = ConfigDict(frozen=True)

    n_draws: int
    n_escalated: int
    correct_mean: float
    correct_low: float
    correct_high: float
    correct_at_cutoff_mean: float
    correct_at_cutoff_low: float
    correct_at_cutoff_high: float
    cost_total_mean_usd: float
    latency_mean_s: float


class Verdict(BaseModel):
    """One pre-registered rule's outcome. SELECTED is S1's pass: it picks, it does not pass."""

    model_config = ConfigDict(frozen=True)

    rule: str
    status: Literal["PASS", "FAIL", "SELECTED", "INCOMPLETE"]
    headline: str
    details: list[str] = Field(default_factory=list)


class PolicyResult(BaseModel):
    """One evaluated policy on one corpus, with its references and paired comparisons."""

    model_config = ConfigDict(frozen=True)

    summary: Summary
    #: LB-1 and LB-2 for this policy on this corpus (PASS or FAIL, with the numbers).
    latency_verdicts: list[Verdict] = Field(default_factory=list)
    acceptance: AcceptanceResult | None = None
    #: Policy minus always-N, per question (`None` for always-N itself or if it is missing).
    vs_always_n: Comparison | None = None
    #: Escalating exactly the gold-wrong first-tier answers; the upper bound.
    oracle: Summary | None = None
    random: RandomSummary | None = None
    vs_random: Comparison | None = None
    #: Why oracle and random escalation are missing, when they are defined for the policy.
    references_skipped: str | None = None


class NotEvaluated(BaseModel):
    """A policy that could not be evaluated on a corpus, and why (never filled silently)."""

    model_config = ConfigDict(frozen=True)

    policy: str
    reason: str
    #: Tier name -> number of questions that reach the tier with no row there.
    gaps: dict[str, int] = Field(default_factory=dict)


class AgentDiagnostics(BaseModel):
    """What the agent tier did on the questions a policy sent to it (report-only, reads gold)."""

    model_config = ConfigDict(frozen=True)

    tier: str
    n_tried: int
    #: Why each tried question's loop ended (`done`, `deadline`, ...; `timed_out` = the row
    #: was cut off and keeps no stop reason).
    stop_reasons: dict[str, int]
    #: Answered with no tool call at all (total = such answers, correct = the right ones).
    answered_without_tool_call: Cell
    #: Answered although the agent never touched a plant item (no `touched_keys` in any step).
    answered_touching_no_item: Cell
    #: Tried questions with a tag named in the text that no step touched (total = such questions,
    #: correct = the right ones); `None` when the corpus item graph was not given.
    named_tag_never_touched: Cell | None = None
    #: Tried questions whose text names at least one plant tag (the base of the line above).
    n_with_named_tags: int = 0


class IsolationScores(BaseModel):
    """UPSTREAM_ISOLATION correct counts: the key as built, and with control valves removed."""

    model_config = ConfigDict(frozen=True)

    #: Scored against the gold key (primary; unchanged).
    primary: Cell
    #: Secondary, labelled "control valves do not isolate": gold minus control valves. Its total
    #: leaves out questions whose gold holds only control valves.
    control_valves_excluded: Cell


class PolicyDiagnostics(BaseModel):
    """Free diagnostics of one policy (arXiv 2609.05880), computed from the stored rows."""

    model_config = ConfigDict(frozen=True)

    policy: str
    #: BOOLEAN questions whose gold is "no": total, and how many the policy answered "yes".
    boolean_no_questions: int
    boolean_no_answered_yes: int
    agent: AgentDiagnostics | None = None
    #: U4; `None` when the item graph was not given or the corpus has no isolation question.
    isolation: IsolationScores | None = None


class LateChargeCheck(BaseModel):
    """The abandoned-call cost estimate against the late charges the run logged."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    strategy: str
    #: Calls abandoned at their timeout, summed over the strategy's rows.
    n_abandoned_in_rows: int
    #: `calls.jsonl` lines with `error_kind="timeout"` / `"late_after_timeout"` for the strategy.
    n_timeouts_logged: int
    n_late_logged: int
    #: Billed cost of the late answers that did arrive; the other abandoned calls are unknown.
    late_cost_logged_usd: float
    #: What the cascade charges instead: abandoned calls times the per-call upper bound.
    estimate_usd: float


class CorpusReport(BaseModel):
    """Everything the report says about one corpus."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n_questions: int
    policies: list[PolicyResult]
    not_evaluated: list[NotEvaluated]
    #: dimension ("need label", "family", "k bin") -> group -> policy -> cell.
    breakdowns: dict[str, dict[str, dict[str, Cell]]]
    diagnostics: list[PolicyDiagnostics] = Field(default_factory=list)
    late_charges: list[LateChargeCheck] = Field(default_factory=list)


class Tier3Tally(BaseModel):
    """One tier-3 candidate's answers on the dev runaways (pooled over the dev corpora)."""

    model_config = ConfigDict(frozen=True)

    tier: str
    #: Dev runaways in all dev corpora (the same for every candidate).
    n_runaways: int
    #: Runaways the candidate has a stored row for.
    n_rows: int
    n_correct: int
    total_cost_usd: float
    mean_latency_s: float


class Report(BaseModel):
    """The full report: corpora, tier-3 tallies and the verdicts."""

    model_config = ConfigDict(frozen=True)

    #: The latency bound the report was computed under (LB-1, LB-2, cutoff C).
    bound: LatencyBound
    corpora: list[CorpusReport]
    tier3: list[Tier3Tally]
    verdicts: list[Verdict]
