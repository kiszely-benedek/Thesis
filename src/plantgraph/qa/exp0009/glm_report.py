"""The descriptive report of the GLM comparison arm: GLM against Luna on the same questions (§20).

Per sealed plant the report gives the paired accuracy difference (GLM minus Luna) with a bootstrap
interval, and beside it each system's cost per question, latency and outcome mix. It makes no claim
and is no gate: one plant per scale cannot carry a scale claim. Accuracy is the cascade's (the
offline `cascade_v4_iso` evaluation, one `ArmReport` per system); cost, latency and outcomes come
from the rows of each tier's run.

The paired bootstrap is the cascade code's own (`qa/cascade/stats.py`: 5,000 resamples, seed 1).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.stats import PairedDifference, median, paired_bootstrap, percentile
from plantgraph.qa.models import QuestionResult

TIERS = ("cyp", "ag")  # the Cypher tier answers first, the agent tier is the fallback


@dataclass(frozen=True)
class SystemRuns:
    """What the report reads of one system on one plant: its right answers and its tier rows."""

    name: str
    correct_ids: frozenset[str]
    rows_by_tier: Mapping[str, Sequence[QuestionResult]]


class TierSummary(BaseModel):
    """One tier's run, over the compared questions only."""

    model_config = ConfigDict(frozen=True)

    tier: str
    cost_per_question_usd: float
    median_latency_s: float
    p90_latency_s: float
    outcomes: dict[str, int]


class SystemSummary(BaseModel):
    """One system on one plant: accuracy, and its two tiers."""

    model_config = ConfigDict(frozen=True)

    name: str
    n_correct: int
    accuracy: float
    tiers: tuple[TierSummary, ...]

    @property
    def cost_per_question_usd(self) -> float:
        """Both tiers on every question, as the cost estimates of §19.9 count it."""
        return sum(t.cost_per_question_usd for t in self.tiers)


class PlantComparison(BaseModel):
    """GLM against Luna on one plant, question for question."""

    model_config = ConfigDict(frozen=True)

    plant_id: str
    scale: int
    n_questions: int
    luna: SystemSummary
    glm: SystemSummary
    glm_minus_luna: PairedDifference


def summarize_tier(tier: str, rows: Sequence[QuestionResult], ids: frozenset[str]) -> TierSummary:
    """Cost, latency and outcomes of the rows of `ids`.

    Raises:
        ValueError: the run has no row for some question (a half-finished run is not compared).
    """
    mine = [r for r in rows if r.question_id in ids]
    if {r.question_id for r in mine} != ids:
        raise ValueError(
            f"expected a {tier} row for each of {len(ids)} questions, found {len(mine)}"
        )
    latencies = [r.total_llm_latency_s for r in mine]
    return TierSummary(
        tier=tier,
        cost_per_question_usd=sum(r.total_cost_usd or 0.0 for r in mine) / len(mine),
        median_latency_s=median(latencies),
        p90_latency_s=percentile(latencies, 90),
        outcomes=dict(sorted(Counter(r.outcome.value for r in mine).items())),
    )


def summarize_system(system: SystemRuns, ids: frozenset[str]) -> SystemSummary:
    """A system's accuracy over `ids` and its tiers' summaries."""
    n_correct = len(system.correct_ids & ids)
    return SystemSummary(
        name=system.name,
        n_correct=n_correct,
        accuracy=n_correct / len(ids),
        tiers=tuple(summarize_tier(t, system.rows_by_tier[t], ids) for t in TIERS),
    )


def compare_plant(
    plant_id: str, scale: int, question_ids: Sequence[str], luna: SystemRuns, glm: SystemRuns
) -> PlantComparison:
    """The paired comparison on one plant; the pair (Luna, GLM) of each question moves together.

    Raises:
        ValueError: no questions, or a run lacks a row (see `summarize_tier`).
    """
    ids = frozenset(question_ids)
    if not ids:
        raise ValueError(f"expected questions to compare on {plant_id}, found none")
    ordered = sorted(ids)
    glm_flags = [float(q in glm.correct_ids) for q in ordered]
    luna_flags = [float(q in luna.correct_ids) for q in ordered]
    return PlantComparison(
        plant_id=plant_id,
        scale=scale,
        n_questions=len(ids),
        luna=summarize_system(luna, ids),
        glm=summarize_system(glm, ids),
        glm_minus_luna=paired_bootstrap(glm_flags, luna_flags),
    )


# ---- the text -----------------------------------------------------------------------------------


def _points(value: float) -> str:
    return f"{value * 100:+.1f}"


def _accuracy_row(c: PlantComparison) -> str:
    d = c.glm_minus_luna
    interval = f"[{_points(d.ci_low)}, {_points(d.ci_high)}]"
    return (
        f"| {c.plant_id} | {c.n_questions} | {c.luna.n_correct} ({c.luna.accuracy:.3f}) "
        f"| {c.glm.n_correct} ({c.glm.accuracy:.3f}) | {_points(d.mean)} | {interval} |"
    )


def _tier_row(plant_id: str, system: SystemSummary, tier: TierSummary) -> str:
    mix = ", ".join(f"{name} {n}" for name, n in tier.outcomes.items())
    return (
        f"| {plant_id} | {system.name} | {tier.tier} | ${tier.cost_per_question_usd:.5f} "
        f"| {tier.median_latency_s:.1f} | {tier.p90_latency_s:.1f} | {mix} |"
    )


def render_markdown(comparisons: Sequence[PlantComparison]) -> str:
    """The report: the paired accuracy table, then cost, latency and outcomes per tier."""
    lines = [
        "# GLM comparison arm (descriptive, no claim)",
        "",
        "GLM 5.3 Flash on one pinned host against GPT-6 Luna, both under the frozen V2T-A2 system "
        "and the policy `cascade_v4_iso`, on the same scope R questions of one sealed plant per "
        "scale. Differences are in percentage points, with a 95 % paired bootstrap interval.",
        "",
        "| plant | questions | Luna correct | GLM correct | GLM - Luna (points) | 95 % interval |",
        "|---|---|---|---|---|---|",
        *[_accuracy_row(c) for c in comparisons],
        "",
        "| plant | system | tier | $ per question | median latency s | p90 latency s | outcomes |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in comparisons:
        lines += [_tier_row(c.plant_id, s, t) for s in (c.luna, c.glm) for t in s.tiers]
    lines += ["", "| plant | system | $ per question, both tiers |", "|---|---|---|"]
    for c in comparisons:
        lines += [
            f"| {c.plant_id} | {s.name} | ${s.cost_per_question_usd:.5f} |" for s in (c.luna, c.glm)
        ]
    return "\n".join(lines) + "\n"
