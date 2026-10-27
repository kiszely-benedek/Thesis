"""The dev quality check's report: accuracy per family and the list of wrong answers.

The check answers "is the frozen system roughly right on v2?" before any sealed spend. Both tiers
(a Cypher query, a graph-walking agent) answer every dev question; `cascade_v3` is then joined
offline, as in every earlier report. The failure list is what a later tuning round reads: for each
wrong cascade answer, the question, the expected and the given answer, and which tier gave it.
Diagnostic only: nothing is tuned on these runs without creating a new, separately labelled system.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.evaluate import ScoredDecision, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies
from plantgraph.qa.models import Question, QuestionResult

CYPHER_TIER = "cypher-luna"
AGENT_TIER = "agent-luna"
#: ADR-0044 U2: left out of the headline numbers, still listed here so its failures are visible.
EXCLUDED_FAMILY = "LOOP_ACTUATED_VALVE"


class FamilyRow(BaseModel):
    """One family's questions and how many each arm got right."""

    model_config = ConfigDict(frozen=True)

    family: str
    n: int
    cypher_correct: int
    agent_correct: int
    #: cascade_v3, correct and within the 120 s cutoff.
    cascade_correct: int
    #: Questions the cascade's final answer came from each tier (`none` = no tier answered).
    answered_by_cypher: int
    answered_by_agent: int


class Failure(BaseModel):
    """A question the cascade got wrong (or answered too late)."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: str
    expected: str
    got: str
    #: The tier whose answer was final, or `none`.
    answered_by: str
    cypher_correct: bool
    agent_correct: bool
    outcome: str


class DevReport(BaseModel):
    """Per-family table, totals and the failure list of one dev check."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n: int
    rows: list[FamilyRow]
    failures: list[Failure]


def _given(row: QuestionResult) -> str:
    """What the tier answered: the answer text, `not_present`, or the outcome if none."""
    if row.final_answer is None:
        return f"<{row.outcome.value}>"
    return "not_present" if row.final_answer.not_present else str(row.final_answer.answer)


def _failure(question: Question, scored: ScoredDecision, joined: JoinedCorpus) -> Failure:
    qid = question.question_id
    tier = scored.decision.answered_by or scored.decision.tiers_tried[-1]
    final = joined.runs[tier].rows[qid]
    return Failure(
        question_id=qid,
        family=question.family.value,
        expected=str(question.reference),
        got=_given(final),
        answered_by=scored.decision.answered_by or "none",
        cypher_correct=joined.runs[CYPHER_TIER].rows[qid].correct,
        agent_correct=joined.runs[AGENT_TIER].rows[qid].correct,
        outcome=final.outcome.value,
    )


def build_dev_report(joined: JoinedCorpus, questions: list[Question], cutoff_s: float) -> DevReport:
    """Per-family counts and the cascade's failures from a joined corpus (pure: no files)."""
    scored = {s.decision.question_id: s for s in evaluate_policy(joined, cutoff_s).scored}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures = []
    for question in questions:
        qid, result = question.question_id, scored[question.question_id]
        c = counts[question.family.value]
        c["n"] += 1
        c["cypher"] += joined.runs[CYPHER_TIER].rows[qid].correct
        c["agent"] += joined.runs[AGENT_TIER].rows[qid].correct
        c["cascade"] += result.correct_at_cutoff
        c["by_cypher"] += result.decision.answered_by == CYPHER_TIER
        c["by_agent"] += result.decision.answered_by == AGENT_TIER
        if not result.correct_at_cutoff:
            failures.append(_failure(question, result, joined))
    rows = [
        FamilyRow(
            family=family,
            n=c["n"],
            cypher_correct=c["cypher"],
            agent_correct=c["agent"],
            cascade_correct=c["cascade"],
            answered_by_cypher=c["by_cypher"],
            answered_by_agent=c["by_agent"],
        )
        for family, c in sorted(counts.items())
    ]
    return DevReport(corpus_id=joined.corpus_id, n=len(questions), rows=rows, failures=failures)


def load_dev_report(
    corpus_id: str, cyp_run: Path, ag_run: Path, questions_root: Path, cutoff_s: float
) -> DevReport:
    """Join the two stored tier runs under `cascade_v3` and build the report.

    Raises:
        IncompleteJoinError: a tier lacks a row for some question.
    """
    policy = load_policies(POLICIES_DIR)["cascade_v3"]
    _, questions = load_questions_file(questions_root, corpus_id)
    sources = {CYPHER_TIER: TierSource(cyp_run), AGENT_TIER: TierSource(ag_run)}
    joined = join_corpus(policy, sources, corpus_id, questions_root)
    require_complete(joined)
    return build_dev_report(joined, questions, cutoff_s)


def _pct(right: int, n: int) -> str:
    return f"{right / n:.3f}" if n else "-"


def _totals(rows: list[FamilyRow]) -> FamilyRow:
    return FamilyRow(
        family="ALL",
        n=sum(r.n for r in rows),
        cypher_correct=sum(r.cypher_correct for r in rows),
        agent_correct=sum(r.agent_correct for r in rows),
        cascade_correct=sum(r.cascade_correct for r in rows),
        answered_by_cypher=sum(r.answered_by_cypher for r in rows),
        answered_by_agent=sum(r.answered_by_agent for r in rows),
    )


def _row_text(r: FamilyRow) -> str:
    return (
        f"| {r.family} | {r.n} | {_pct(r.cypher_correct, r.n)} | {_pct(r.agent_correct, r.n)} | "
        f"{_pct(r.cascade_correct, r.n)} | {r.answered_by_cypher} / {r.answered_by_agent} |"
    )


def render_dev_markdown(report: DevReport) -> str:
    """Markdown: the per-family table (with totals) and the failure list."""
    headline = [r for r in report.rows if r.family != EXCLUDED_FAMILY]
    table = [
        "| Family | n | Cypher | Agent | cascade_v3 | Final answer from cypher / agent |",
        "|---|---|---|---|---|---|",
        *[_row_text(r) for r in report.rows],
        _row_text(_totals(report.rows)),
        _row_text(
            _totals(headline).model_copy(update={"family": f"ALL without {EXCLUDED_FAMILY}"})
        ),
    ]
    failed = [
        "| Question | Family | Expected | Got | Answered by | Cypher ok | Agent ok | Outcome |",
        "|---|---|---|---|---|---|---|---|",
        *[
            f"| {f.question_id} | {f.family} | {f.expected} | {f.got} | {f.answered_by} | "
            f"{f.cypher_correct} | {f.agent_correct} | {f.outcome} |"
            for f in report.failures
        ],
    ]
    return "\n".join(
        [
            f"# Dev quality check on {report.corpus_id} (diagnostic, n={report.n})",
            "",
            "Accuracy is the share correct (Cypher, Agent: uncut; cascade_v3: within 120 s).",
            "",
            *table,
            "",
            f"## cascade_v3 failures ({len(report.failures)})",
            "",
            *failed,
            "",
        ]
    )


def write_dev_report(report: DevReport, out_dir: Path) -> list[Path]:
    """Write `dev_report.md`, `dev_report.json` and `failures.jsonl`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = {
        "dev_report.md": render_dev_markdown(report),
        "dev_report.json": report.model_dump_json(indent=2) + "\n",
        "failures.jsonl": "".join(f.model_dump_json() + "\n" for f in report.failures),
    }
    for name, text in texts.items():
        (out_dir / name).write_bytes(text.encode("utf-8"))
    return [out_dir / name for name in texts]
