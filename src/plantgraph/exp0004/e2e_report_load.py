"""Read the E2E arms from disk: join the two tier runs, score the cascade, sum the real spend.

The join and the scoring are the EXP-0007 cascade code, called the way `cascade report
--sealed-claims` calls it (same anchor finder, same label borrowing, same headline scope rule).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from plantgraph.exp0004.e2e_dry_run import read_calls
from plantgraph.exp0004.e2e_report_models import ArmData
from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import anchor_finder, labels_from_run_dirs
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.report_claims import HEADLINE_SPLITS
from plantgraph.qa.cascade.report_scopes import counted_ids, load_splits, restrict, split_ids
from plantgraph.qa.models import Question

#: The tier names inside the frozen policy `cascade_v4_iso`.
CYPHER_TIER = "cypher-v2t"
AGENT_TIER = "agent-v2t"
#: PREREG.md section 5: "R5's 440-question headline scope".
PREREGISTERED_HEADLINE_N = 440


@dataclass(frozen=True)
class ArmInput:
    """Where one arm lives on disk."""

    label: str
    corpus_id: str
    cypher_run: Path
    agent_run: Path
    questions_root: Path
    corpora_root: Path


def require_headline_size(ids: Collection[str]) -> None:
    """Refuse a headline scope that is not the pre-registered size.

    Raises:
        ValueError: the scope does not hold exactly `PREREGISTERED_HEADLINE_N` questions.
    """
    if len(ids) != PREREGISTERED_HEADLINE_N:
        raise ValueError(
            f"expected the pre-registered headline scope of {PREREGISTERED_HEADLINE_N} "
            f"questions, found {len(ids)}"
        )


def require_arm_size(label: str, n_questions: int) -> None:
    """Refuse an arm whose restricted question set is not the pre-registered size.

    `restrict` silently drops headline ids an arm lacks, so each arm is counted after it.

    Raises:
        ValueError: the arm does not hold exactly `PREREGISTERED_HEADLINE_N` questions.
    """
    if n_questions != PREREGISTERED_HEADLINE_N:
        raise ValueError(
            f"expected arm {label} to hold the pre-registered {PREREGISTERED_HEADLINE_N} "
            f"headline questions after restriction, found {n_questions}"
        )


def headline_ids(questions_root: Path, corpus_id: str) -> tuple[list[Question], frozenset[str]]:
    """R5's questions and its headline scope: counted family, splits dev-old/dev-new/held-out."""
    _, questions = load_questions_file(questions_root, corpus_id)
    splits = load_splits(questions_root, corpus_id, questions)
    if splits is None:
        raise ValueError(f"expected a splits.json under {questions_root / corpus_id}, found none")
    ids = counted_ids(questions) & split_ids(splits, HEADLINE_SPLITS)
    require_headline_size(ids)
    return questions, ids


def real_spend_usd(run_dir: Path) -> float:
    """Sum of `cost_usd` over the calls of a run that were not served from the cache.

    A call with no response or no recorded cost (failed before the provider answered) adds nothing.
    """
    responses = [c.response for c in read_calls(run_dir / "calls.jsonl") if c.response]
    return sum(r.cost_usd or 0.0 for r in responses if not r.from_cache)


def _join(arm: ArmInput, policy: CascadePolicy) -> JoinedCorpus:
    sources = {
        CYPHER_TIER: TierSource(arm.cypher_run),
        AGENT_TIER: TierSource(arm.agent_run),
    }
    view = load_corpus_view(arm.corpora_root, arm.corpus_id)
    joined = join_corpus(
        policy,
        sources,
        arm.corpus_id,
        arm.questions_root,
        find_anchors=anchor_finder(view),
        known_labels=labels_from_run_dirs(s.run_dir for s in sources.values()),
    )
    require_complete(joined)
    return joined


def _outcome_counts(joined: JoinedCorpus, ids: Collection[str]) -> dict[str, dict[str, int]]:
    """Tier -> outcome name -> number of in-scope questions with that stored outcome."""
    return {
        tier: dict(Counter(s.outcome.value for qid, s in by_question.items() if qid in ids))
        for tier, by_question in joined.signals.items()
    }


def load_arm(
    arm: ArmInput, policy: CascadePolicy, cutoff_s: float, ids: Collection[str]
) -> ArmData:
    """Score `policy` on `ids` of one arm and collect its outcome counts and real spend."""
    scoped = restrict(_join(arm, policy), ids)
    require_arm_size(arm.label, len(scoped.question_ids))
    evaluation = evaluate_policy(scoped, cutoff_s)
    # evaluate_policy scores in `question_ids` order, so the two lists line up
    correct = {
        qid: scored.correct_at_cutoff
        for qid, scored in zip(scoped.question_ids, evaluation.scored, strict=True)
    }
    return ArmData(
        label=arm.label,
        correct=correct,
        outcomes=_outcome_counts(scoped, ids),
        spend_usd=real_spend_usd(arm.cypher_run) + real_spend_usd(arm.agent_run),
    )
