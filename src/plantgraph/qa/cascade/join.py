"""Join the stored runs of a policy's tiers into per-question `Signals`, refusing on any mismatch.

Nothing is filled in silently: a run that differs from the reference tier (the policy's first
tier) in plant, question text, primer, shared prompts or pin is refused, and a question that
reaches a tier with no row is reported with the harness command that would produce it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from plantgraph.qa.cascade.accept import walk_question
from plantgraph.qa.cascade.checks import (
    JoinRefused,
    LoadedRun,
    compatibility_problems,
    load_questions_file,
    load_run,
    question_digest,
)
from plantgraph.qa.cascade.gaps import IncompleteJoinError, gap_message
from plantgraph.qa.cascade.labels import AnchorFinder, classify_need, label_from_trace
from plantgraph.qa.cascade.models import CascadePolicy, Signals
from plantgraph.qa.cascade.signals import extract_signals
from plantgraph.qa.models import Question
from plantgraph.qa.need.labels import NeedLabel

DEFAULT_QSUB_ROOT = Path("data") / "runs" / "qsub"


@dataclass(frozen=True)
class TierSource:
    """Where one tier's stored run lives, and the questions file it was started from."""

    run_dir: Path
    #: Root holding `<corpus>/questions.jsonl`; `None` means the reference questions root.
    questions_root: Path | None = None


@dataclass
class JoinedCorpus:
    """The per-question signals of every tier of a policy, for one corpus."""

    corpus_id: str
    policy: CascadePolicy
    reference: LoadedRun
    #: Reference question ids, in the order of the reference questions file.
    question_ids: list[str]
    #: tier name -> question id -> signals (only questions the tier has a row for).
    signals: dict[str, dict[str, Signals]]
    need_labels: dict[str, NeedLabel] = field(default_factory=dict)
    #: tier name -> the loaded run; the evaluation reads `correct` from its rows (gold side).
    runs: dict[str, LoadedRun] = field(default_factory=dict)


def join_corpus(
    policy: CascadePolicy,
    sources: dict[str, TierSource],
    corpus_id: str,
    questions_root: Path,
    find_anchors: AnchorFinder | None = None,
    known_labels: Mapping[str, NeedLabel] | None = None,
) -> JoinedCorpus:
    """Load every tier of `policy`, check it against the first tier, and build the signals.

    A tier without an entry in `sources` has no rows yet; its questions show up as gaps.
    `known_labels` fills in labels the policy's own runs do not carry (see `labels.py`).

    Raises:
        JoinRefused: the first tier has no run, or any run differs from it.
    """
    _, questions = load_questions_file(questions_root, corpus_id)
    reference_digests = {q.question_id: question_digest(q) for q in questions}
    runs = _load_runs(policy, sources, corpus_id, questions_root)
    first = policy.tiers[0].name
    if first not in runs:
        raise JoinRefused(f"expected a run for the first tier {first!r}, found none given")
    problems = [
        problem
        for run in runs.values()
        for problem in compatibility_problems(run, runs[first], reference_digests)
    ]
    if problems:
        raise JoinRefused("refusing to join:\n  " + "\n  ".join(problems))
    labels = _resolve_labels(runs, questions, find_anchors, known_labels or {})
    signals = {
        name: {
            qid: extract_signals(
                row, name, run.config.answer_pin, labels.get(qid), run.local_compute_s.get(qid)
            )
            for qid, row in run.rows.items()
        }
        for name, run in runs.items()
    }
    return JoinedCorpus(
        corpus_id=corpus_id,
        policy=policy,
        reference=runs[first],
        question_ids=list(reference_digests),
        signals=signals,
        need_labels=labels,
        runs=runs,
    )


def _load_runs(
    policy: CascadePolicy, sources: dict[str, TierSource], corpus_id: str, questions_root: Path
) -> dict[str, LoadedRun]:
    runs: dict[str, LoadedRun] = {}
    for tier in policy.tiers:
        source = sources.get(tier.name)
        if source is None:
            continue
        root = source.questions_root or questions_root
        runs[tier.name] = load_run(tier, source.run_dir, root, corpus_id)
    return runs


def _resolve_labels(
    runs: dict[str, LoadedRun],
    questions: list[Question],
    find_anchors: AnchorFinder | None,
    known_labels: Mapping[str, NeedLabel],
) -> dict[str, NeedLabel]:
    """One label per question: from a run's trace, else a known label, else the classifier."""
    labels: dict[str, NeedLabel] = {}
    for run in runs.values():
        for qid, row in run.rows.items():
            label = label_from_trace(row)
            if label is not None:
                labels.setdefault(qid, label)
    for qid, label in known_labels.items():
        labels.setdefault(qid, label)
    if find_anchors is None:
        return labels
    for question in questions:
        if question.question_id not in labels:
            labels[question.question_id] = classify_need(question.text, find_anchors)
    return labels


def find_gaps(joined: JoinedCorpus) -> dict[str, list[str]]:
    """Tier name -> ids of questions that reach the tier but have no row there."""
    gaps: dict[str, list[str]] = {}
    for qid in joined.question_ids:
        walk = walk_question(joined.policy, qid, joined.need_labels.get(qid), joined.signals)
        if walk.missing_tier is not None:
            gaps.setdefault(walk.missing_tier, []).append(qid)
    return gaps


def require_complete(joined: JoinedCorpus, qsub_root: Path = DEFAULT_QSUB_ROOT) -> None:
    """Raise `IncompleteJoinError` if any question reaches a tier with no row."""
    gaps = find_gaps(joined)
    if gaps:
        message = gap_message(
            gaps, joined.policy.tiers, joined.reference, joined.corpus_id, qsub_root
        )
        raise IncompleteJoinError(gaps, message)
