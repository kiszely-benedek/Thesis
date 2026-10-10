"""Plain-text rendering of a live answer for the `ask` command: the answer and a tier table."""

from __future__ import annotations

from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall, TierReport

_TABLE_HEADER = (
    f"{'tier':<16}{'outcome':<16}{'accepted':<10}{'latency_s':>10}{'cost_usd':>10}"
    f"{'calls':>7}{'cached':>8}{'steps':>7}{'rows':>6}  stop"
)


def render_live_answer(answer: LiveAnswer) -> str:
    """The answer, who gave it, the totals and one table row per tried tier."""
    lines = [f"policy: {answer.policy}"]
    if not answer.evaluated_policy:
        lines.append(f"WARNING: not the evaluated policy. {answer.notice}")
    lines += [f"question: {answer.question_text}", f"outcome: {answer.outcome.value}"]
    if answer.final_answer is not None:
        lines.append(f"answer: {answer.final_answer.answer}")
    lines.append(_answered_by(answer))
    lines.append(
        f"latency {answer.latency_s:.1f} s (wall {answer.wall_s:.1f} s), cost "
        f"${answer.cost_usd:.4f}, spent now ${answer.spent_usd:.4f}"
        f"{', all from cache' if answer.from_cache else ''}"
    )
    if answer.trace_sheets:
        lines.append(f"sheets read: {', '.join(answer.trace_sheets)}")
    lines += ["", _TABLE_HEADER, *(_tier_row(report) for report in answer.tiers)]
    return "\n".join(lines)


def render_needs_paid_call(needed: NeedsPaidCall) -> str:
    """Why nothing was answered in replay mode, and how to allow the call."""
    return (
        f"cache miss at tier {needed.missing_tier!r}: {needed.reason}\n"
        "no network call was made; rerun without --replay-only to ask live "
        "(paid, within --session-cap-usd)"
    )


def _answered_by(answer: LiveAnswer) -> str:
    if answer.answered_by is None:
        return "answered by: nobody"
    fallback = " (fallback: no tier was accepted)" if answer.fell_back else ""
    return f"answered by: {answer.answered_by}{fallback}"


def _tier_row(report: TierReport) -> str:
    steps = "-" if report.n_steps is None else str(report.n_steps)
    rows = "-" if report.n_rows is None else str(report.n_rows)
    return (
        f"{report.tier:<16}{report.outcome.value:<16}{'yes' if report.accepted else 'no':<10}"
        f"{report.latency_s:>10.1f}{report.cost_usd:>10.4f}{report.n_calls:>7}"
        f"{report.n_cached:>8}{steps:>7}{rows:>6}  {report.stop_reason or ''}"
    )
