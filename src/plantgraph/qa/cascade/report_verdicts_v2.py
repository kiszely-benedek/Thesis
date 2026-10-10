"""The pre-registered rules V2 and V3 (cascade-v2 note, section 9.3), as pure functions.

V2 picks the cascade on the first dev corpus (D100); V3 checks that pick on the second
(D1000). Both rank by acc@C (correct within the cutoff) and need LB-1 and LB-2 (the median and
p90 latency limits). They read `Summary` numbers only. The thresholds were fixed before any
v2 result was read; change them only with a new ADR. V1, V4 and V5 are dropped (ADR-0048,
acceptance of 2026-10-10: no tier 3, no step cap).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.evaluate import LatencyBound, Summary
from plantgraph.qa.cascade.report_models import Verdict

#: The deployable cascades that compete; references (always-G/N/C, random, oracle) do not.
CANDIDATES = ("cascade_v1", "cascade_v1_iso", "cascade_v2", "cascade_v2_iso")
SELECT_CORPUS = "D100"
CONFIRM_CORPUS_V3 = "D1000"
#: V3: the D100 choice may trail the best eligible D1000 candidate by this many questions.
V3_MAX_QUESTIONS_BEHIND = 2


class Selection(BaseModel):
    """A rule's verdict and the candidate it chose (`None` while the rule is incomplete)."""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    chosen: str | None


def is_eligible(summary: Summary, bound: LatencyBound) -> bool:
    """True when the policy meets LB-1 (median) and LB-2 (p90) on this corpus."""
    return summary.latency_median_s <= bound.median_max_s and (
        summary.latency_p90_s <= bound.p90_max_s
    )


def _best_accuracy_first(summaries: list[Summary]) -> Summary:
    """Highest acc@C; a tie goes to the cheaper policy, then to the name (so it is stable)."""
    return min(summaries, key=lambda s: (-s.n_correct_at_cutoff, s.cost_per_question_usd, s.policy))


def _line(summary: Summary, bound: LatencyBound) -> str:
    eligible = "eligible" if is_eligible(summary, bound) else "not eligible"
    return (
        f"{summary.policy}: acc@{summary.cutoff_s:g} {summary.n_correct_at_cutoff}/"
        f"{summary.n_questions}, median {summary.latency_median_s:.1f} s, "
        f"p90 {summary.latency_p90_s:.1f} s, ${summary.cost_per_question_usd:.5f}/question "
        f"({eligible})"
    )


def _candidates_on(
    summaries: Mapping[str, Summary],
) -> tuple[list[Summary], list[str]]:
    """The candidates that were evaluated, and the names of those that were not."""
    found = [summaries[name] for name in CANDIDATES if name in summaries]
    missing = [name for name in CANDIDATES if name not in summaries]
    return found, missing


def _incomplete(rule: str, corpus: str, missing: list[str]) -> Selection:
    headline = f"not evaluated on {corpus}: {', '.join(missing)}"
    return Selection(
        verdict=Verdict(rule=rule, status="INCOMPLETE", headline=headline), chosen=None
    )


def _choose(found: list[Summary], bound: LatencyBound) -> tuple[Summary, bool]:
    """The best eligible candidate; with none eligible, the lowest p90 (and `False`)."""
    eligible = [s for s in found if is_eligible(s, bound)]
    if eligible:
        return _best_accuracy_first(eligible), True
    return min(found, key=lambda s: (s.latency_p90_s, s.policy)), False


def select_on_dev(summaries: Mapping[str, Summary], bound: LatencyBound) -> Selection:
    """V2: among candidates meeting LB-1 and LB-2 on D100, the highest acc@C (tie: cheaper)."""
    found, missing = _candidates_on(summaries)
    if missing:
        return _incomplete("V2", SELECT_CORPUS, missing)
    best, was_eligible = _choose(found, bound)
    note = "" if was_eligible else " - latency bound not met on dev (lowest p90 chosen)"
    verdict = Verdict(
        rule="V2",
        status="SELECTED",
        headline=f"{best.policy} on {SELECT_CORPUS}{note}",
        details=[_line(s, bound) for s in found],
    )
    return Selection(verdict=verdict, chosen=best.policy)


def confirm_on_scale(
    chosen: str | None, summaries: Mapping[str, Summary], bound: LatencyBound
) -> Selection:
    """V3: keep the D100 choice if eligible on D1000 and within 2 questions of the best eligible.

    Otherwise the best eligible D1000 candidate takes over, reported as a scale effect.
    """
    found, missing = _candidates_on(summaries)
    if chosen is None or missing:
        names = missing or ["the V2 choice"]
        return _incomplete("V3", CONFIRM_CORPUS_V3, names)
    best, was_eligible = _choose(found, bound)
    own = summaries[chosen]
    kept = was_eligible and is_eligible(own, bound)
    kept = kept and own.n_correct_at_cutoff >= best.n_correct_at_cutoff - V3_MAX_QUESTIONS_BEHIND
    details = [_line(s, bound) for s in found]
    if kept:
        headline = f"{chosen} confirmed on {CONFIRM_CORPUS_V3}"
        return Selection(verdict=_v3("PASS", headline, details), chosen=chosen)
    if not was_eligible:
        headline = f"no candidate meets the latency bound on {CONFIRM_CORPUS_V3}; lowest p90 is "
        return Selection(verdict=_v3("FAIL", headline + best.policy, details), chosen=best.policy)
    headline = f"{chosen} not confirmed; {best.policy} chosen instead"
    details.append("scale effect: the best policy changes between D100 and D1000")
    return Selection(verdict=_v3("FAIL", headline, details), chosen=best.policy)


def _v3(status: Literal["PASS", "FAIL"], headline: str, details: list[str]) -> Verdict:
    return Verdict(rule="V3", status=status, headline=headline, details=details)
