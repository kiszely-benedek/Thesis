"""`needed`: write the questions that reach one tier, so a harness run can answer exactly those.

The set is the union over the candidate policies (a question reaching the tier under any of
them is included), decided from earlier tiers' signals only. The output is a normal questions
file, laid out the way the harness expects: `<out_root>/<tier>/<corpus>/questions.jsonl`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.cascade.accept import walk_question
from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.gaps import IncompleteJoinError, gap_message
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.labels import AnchorFinder
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.harness.question_set import questions_path


@dataclass(frozen=True)
class NeededResult:
    """What `write_needed` wrote."""

    path: Path
    question_ids: list[str]
    #: How many of them the tier's run already has a row for (those replay, they cost nothing new).
    n_already_answered: int


def reaching_question_ids(joined: JoinedCorpus, tier_name: str, qsub_root: Path) -> set[str]:
    """Ids of questions that reach `tier_name` under the joined policy.

    Raises:
        IncompleteJoinError: a tier before `tier_name` lacks a row for a question that reaches it.
    """
    reaching: set[str] = set()
    earlier_gaps: dict[str, list[str]] = {}
    for qid in joined.question_ids:
        label = joined.need_labels.get(qid)
        walk = walk_question(joined.policy, qid, label, joined.signals)
        if tier_name in walk.tried or walk.missing_tier == tier_name:
            reaching.add(qid)
        elif walk.missing_tier is not None:
            earlier_gaps.setdefault(walk.missing_tier, []).append(qid)
    if earlier_gaps:
        message = gap_message(
            earlier_gaps, joined.policy.tiers, joined.reference, joined.corpus_id, qsub_root
        )
        raise IncompleteJoinError(earlier_gaps, message)
    return reaching


def write_needed(
    policies: list[CascadePolicy],
    tier_name: str,
    sources: dict[str, TierSource],
    corpus_id: str,
    questions_root: Path,
    out_root: Path,
    find_anchors: AnchorFinder | None = None,
) -> NeededResult:
    """Write the subset questions file of `tier_name`: the union over `policies`.

    Raises:
        ValueError: no policy has a tier of that name.
    """
    candidates = [p for p in policies if any(t.name == tier_name for t in p.tiers)]
    if not candidates:
        raise ValueError(f"expected a tier named {tier_name!r} in some policy, found none")
    needed: set[str] = set()
    for policy in candidates:
        joined = join_corpus(policy, sources, corpus_id, questions_root, find_anchors)
        needed |= reaching_question_ids(joined, tier_name, out_root)
    already = _already_answered(joined, tier_name, needed)
    path, ids = _write_subset(questions_root, corpus_id, needed, out_root / tier_name)
    return NeededResult(path=path, question_ids=ids, n_already_answered=already)


def _already_answered(joined: JoinedCorpus, tier_name: str, needed: set[str]) -> int:
    answered = joined.signals.get(tier_name, {})
    return sum(1 for qid in needed if qid in answered)


def _write_subset(
    questions_root: Path, corpus_id: str, needed: set[str], tier_root: Path
) -> tuple[Path, list[str]]:
    """Copy the needed lines of the reference questions file, in file order, with bare LF."""
    source, _ = load_questions_file(questions_root, corpus_id)
    lines = source.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if json.loads(line)["question_id"] in needed]
    ids = [json.loads(line)["question_id"] for line in kept]
    target = questions_path(tier_root, corpus_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes("".join(line + "\n" for line in kept).encode("utf-8"))
    return target, ids
