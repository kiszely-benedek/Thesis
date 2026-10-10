"""The pre-registered rules S1-S3 (note section 7) and LB-1/LB-2 (section 4), as pure functions.

S1 picks the tier-3 model on the dev runaways; S2 confirms `cascade_v1` on the second dev
corpus; S3 decides whether a label variant may replace it. The thresholds are the note's,
fixed before any result was read; change them only with a new ADR.
"""

from __future__ import annotations

from collections.abc import Iterable

from plantgraph.qa.cascade.evaluate import LatencyBound, Summary
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_models import Tier3Tally, Verdict

#: The tier-3 candidates: need @ mimo, need @ glm low effort, need @ glm default with 64k tokens.
TIER3_CANDIDATES = ("need-mimo", "need-low", "need-default-64k")
#: The tier whose runaways tier 3 exists for.
RUNAWAY_TIER = "need-default"
#: S2 and S3 are judged on this corpus (the second dev corpus; flags never inspected there).
CONFIRM_CORPUS = "D1000"
PRIMARY = "cascade_v1"
LABEL_VARIANTS = ("cascade_v1_iso", "label_router_dev")
#: S2: the cascade may lose at most this many correct answers against always-N.
S2_MAX_QUESTIONS_BEHIND = 2
#: S3: a variant must win by at least this many questions ...
S3_MIN_QUESTIONS_AHEAD = 2
#: ... at no more than this multiple of the primary's cost.
S3_MAX_COST_RATIO = 1.25


def tally_tier3(joins: Iterable[JoinedCorpus], candidate: str) -> Tier3Tally:
    """Count `candidate`'s answers on the runaways of `RUNAWAY_TIER`, over the given corpora.

    Each element of `joins` is one corpus; it must hold the runaway tier's run, and the
    candidate's run if there is one yet.
    """
    n_runaways = n_rows = n_correct = 0
    cost = latency = 0.0
    for joined in joins:
        runaways = [qid for qid, s in joined.signals[RUNAWAY_TIER].items() if s.runaway]
        n_runaways += len(runaways)
        rows = joined.runs[candidate].rows if candidate in joined.runs else {}
        for qid in runaways:
            if qid not in rows:
                continue
            n_rows += 1
            n_correct += rows[qid].correct
            cost += joined.signals[candidate][qid].cost_usd
            latency += joined.signals[candidate][qid].latency_s
    return Tier3Tally(
        tier=candidate,
        n_runaways=n_runaways,
        n_rows=n_rows,
        n_correct=n_correct,
        total_cost_usd=cost,
        mean_latency_s=latency / n_rows if n_rows else 0.0,
    )


def _tally_line(t: Tier3Tally) -> str:
    return (
        f"{t.tier}: {t.n_correct}/{t.n_runaways} correct ({t.n_rows} rows stored), "
        f"cost ${t.total_cost_usd:.4f}, mean latency {t.mean_latency_s:.1f} s"
    )


def select_tier3(tallies: list[Tier3Tally]) -> Verdict:
    """S1: the candidate with most correct dev runaways; a tie goes to the cheaper one."""
    details = [_tally_line(t) for t in tallies]
    if not tallies:
        return Verdict(rule="S1", status="INCOMPLETE", headline="no tier-3 candidate", details=[])
    incomplete = [t.tier for t in tallies if t.n_rows < t.n_runaways]
    if incomplete:
        return Verdict(
            rule="S1",
            status="INCOMPLETE",
            headline=f"candidates without a row for every dev runaway: {', '.join(incomplete)}",
            details=details,
        )
    best = min(tallies, key=lambda t: (-t.n_correct, t.total_cost_usd))
    half = tallies[0].n_runaways / 2
    if all(t.n_correct < half for t in tallies):
        details.append("every candidate answers fewer than half: Sonnet (CP-P4) becomes eligible")
    return Verdict(
        rule="S1",
        status="SELECTED",
        headline=f"tier 3 = {best.tier} ({best.n_correct}/{best.n_runaways} correct)",
        details=details,
    )


def confirm_cascade(cascade: Summary | None, always_n: Summary | None) -> Verdict:
    """S2: accuracy at most 2 questions below always-N and a lower mean cost per question."""
    if cascade is None or always_n is None:
        return Verdict(
            rule="S2",
            status="INCOMPLETE",
            headline=f"{PRIMARY} or always_n is not evaluated on {CONFIRM_CORPUS}",
        )
    accuracy_ok = cascade.n_correct >= always_n.n_correct - S2_MAX_QUESTIONS_BEHIND
    cost_ok = cascade.cost_per_question_usd < always_n.cost_per_question_usd
    return Verdict(
        rule="S2",
        status="PASS" if accuracy_ok and cost_ok else "FAIL",
        headline=f"{PRIMARY} on {CONFIRM_CORPUS}",
        details=[
            f"accuracy {cascade.n_correct} vs always-N {always_n.n_correct} "
            f"(needs >= {always_n.n_correct - S2_MAX_QUESTIONS_BEHIND}): "
            f"{'ok' if accuracy_ok else 'not met'}",
            f"cost per question ${cascade.cost_per_question_usd:.5f} vs "
            f"${always_n.cost_per_question_usd:.5f} (needs lower): "
            f"{'ok' if cost_ok else 'not met'}",
        ],
    )


def check_label_variant(name: str, variant: Summary | None, primary: Summary | None) -> Verdict:
    """S3: PASS means the variant may replace the primary (>= 2 questions ahead, <= 1.25x cost)."""
    if variant is None or primary is None:
        return Verdict(
            rule=f"S3 {name}",
            status="INCOMPLETE",
            headline=f"{name} or {PRIMARY} is not evaluated on {CONFIRM_CORPUS}",
        )
    ahead = variant.n_correct - primary.n_correct
    limit = S3_MAX_COST_RATIO * primary.total_cost_usd
    ahead_ok = ahead >= S3_MIN_QUESTIONS_AHEAD
    cost_ok = variant.total_cost_usd <= limit
    return Verdict(
        rule=f"S3 {name}",
        status="PASS" if ahead_ok and cost_ok else "FAIL",
        headline=f"{name} vs {PRIMARY} on {CONFIRM_CORPUS}",
        details=[
            f"{ahead:+d} questions (needs >= {S3_MIN_QUESTIONS_AHEAD}): "
            f"{'ok' if ahead_ok else 'not met'}",
            f"total cost ${variant.total_cost_usd:.4f} vs limit ${limit:.4f} "
            f"({S3_MAX_COST_RATIO}x primary): {'ok' if cost_ok else 'not met'}",
        ],
    )


def check_latency_bound(summary: Summary, bound: LatencyBound) -> list[Verdict]:
    """LB-1 (median) and LB-2 (p90) of one policy on one corpus; point estimates, <= passes."""
    median_ok = summary.latency_median_s <= bound.median_max_s
    p90_ok = summary.latency_p90_s <= bound.p90_max_s
    where = f"{summary.policy} on {summary.corpus_id}"
    return [
        Verdict(
            rule="LB-1",
            status="PASS" if median_ok else "FAIL",
            headline=f"{where}: median {summary.latency_median_s:.1f} s "
            f"(limit {bound.median_max_s:g} s)",
        ),
        Verdict(
            rule="LB-2",
            status="PASS" if p90_ok else "FAIL",
            headline=f"{where}: p90 {summary.latency_p90_s:.1f} s (limit {bound.p90_max_s:g} s)",
        ),
    ]
