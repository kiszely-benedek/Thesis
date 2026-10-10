"""Markdown for the report-only diagnostics: stop reasons, tool use, made-up yes, late charges."""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.qa.cascade.report_models import (
    AgentDiagnostics,
    Cell,
    LateChargeCheck,
    PolicyDiagnostics,
)

#: Display order of the agent loop's stop reasons; any other key follows alphabetically.
STOP_REASON_ORDER = ("done", "deadline", "runaway", "prompt_budget", "errors", "max_steps")
STOP_REASON_EXTRAS = ("overflow", "timed_out", "unrecorded")


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return lines + ["| " + " | ".join(r) + " |" for r in rows] + [""]


def _cell(cell: Cell) -> str:
    return f"{cell.total} ({cell.correct} correct)"


def _stop_reason_rows(agents: Sequence[tuple[str, AgentDiagnostics]]) -> list[list[str]]:
    keys = [*STOP_REASON_ORDER, *STOP_REASON_EXTRAS]
    return [
        [policy, a.tier, str(a.n_tried), *(str(a.stop_reasons.get(k, 0)) for k in keys)]
        for policy, a in agents
    ]


def _agent_lines(diagnostics: Sequence[PolicyDiagnostics]) -> list[str]:
    agents = [(d.policy, d.agent) for d in diagnostics if d.agent is not None]
    if not agents:
        return []
    keys = [*STOP_REASON_ORDER, *STOP_REASON_EXTRAS]
    lines = ["### Agent tier: stop reasons", ""]
    lines += _table(["policy", "tier", "questions tried", *keys], _stop_reason_rows(agents))
    rows = [
        [policy, _cell(a.answered_without_tool_call), _cell(a.answered_touching_no_item)]
        for policy, a in agents
    ]
    lines += ["### Agent tier: answers without evidence gathered", ""]
    return lines + _table(["policy", "no tool call", "no plant item touched"], rows)


def _named_tag_lines(diagnostics: Sequence[PolicyDiagnostics]) -> list[str]:
    rows = [
        [d.policy, str(d.agent.n_with_named_tags), _cell(d.agent.named_tag_never_touched)]
        for d in diagnostics
        if d.agent is not None and d.agent.named_tag_never_touched is not None
    ]
    if not rows:
        return []
    lines = ["### Agent tier: a tag named in the question was never touched", ""]
    return lines + _table(["policy", "questions naming a tag", "never touched"], rows)


def _isolation_lines(diagnostics: Sequence[PolicyDiagnostics]) -> list[str]:
    rows = [
        [
            d.policy,
            f"{d.isolation.primary.correct}/{d.isolation.primary.total}",
            f"{d.isolation.control_valves_excluded.correct}/"
            f"{d.isolation.control_valves_excluded.total}",
        ]
        for d in diagnostics
        if d.isolation is not None
    ]
    if not rows:
        return []
    lines = [
        "### UPSTREAM_ISOLATION: secondary score, control valves do not isolate",
        "",
        "Secondary only (offline re-score); the primary score is the gold key as built. "
        "Secondary reference = gold minus control valves.",
        "",
    ]
    return lines + _table(["policy", "primary correct", "secondary correct"], rows)


def _boolean_lines(diagnostics: Sequence[PolicyDiagnostics]) -> list[str]:
    rows = [
        [d.policy, str(d.boolean_no_questions), str(d.boolean_no_answered_yes)] for d in diagnostics
    ]
    lines = ["### Made-up yes (BOOLEAN questions whose gold is no)", ""]
    return lines + _table(["policy", "gold-no questions", "answered yes"], rows)


def _late_lines(checks: Sequence[LateChargeCheck]) -> list[str]:
    if not checks:
        return []
    rows = [
        [
            c.run_id,
            c.strategy,
            str(c.n_abandoned_in_rows),
            str(c.n_timeouts_logged),
            f"{c.n_late_logged} (${c.late_cost_logged_usd:.4f})",
            f"${c.estimate_usd:.4f}",
        ]
        for c in checks
    ]
    header = ["run", "strategy", "abandoned calls", "timeouts logged", "late answers", "estimate"]
    lines = ["### Abandoned calls: estimate against logged late charges", ""]
    return lines + _table(header, rows)


def diagnostics_lines(
    diagnostics: Sequence[PolicyDiagnostics], late_charges: Sequence[LateChargeCheck]
) -> list[str]:
    """All diagnostics sections of one corpus; empty when there is nothing to show."""
    if not diagnostics:
        return []
    return [
        *_agent_lines(diagnostics),
        *_named_tag_lines(diagnostics),
        *_isolation_lines(diagnostics),
        *_boolean_lines(diagnostics),
        *_late_lines(late_charges),
    ]
