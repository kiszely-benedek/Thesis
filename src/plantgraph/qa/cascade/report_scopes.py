"""Which questions each sealed-report table counts: headline, held-out, every question.

A corpus's questions may come with a `splits.json` (question id -> split name) beside
`questions.jsonl`. Without it (the dev corpora) there are no splits: the headline set is every
question except the excluded family, and the held-out scope does not exist.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_claims import (
    HEADLINE_EXCLUDED_FAMILY,
    HEADLINE_SPLITS,
    SPLIT_HELD_OUT,
    SPLIT_ORDER,
)
from plantgraph.qa.models import Question

SCOPE_HEADLINE = "headline"
SCOPE_HELD_OUT = "held-out"
SPLITS_FILENAME = "splits.json"


def load_splits(
    questions_root: Path, corpus_id: str, questions: Sequence[Question]
) -> dict[str, str] | None:
    """The corpus's `splits.json`, or `None` if there is none.

    Raises:
        ValueError: it names an unknown split, or does not cover the questions exactly once.
    """
    path = questions_root / corpus_id / SPLITS_FILENAME
    if not path.exists():
        return None
    splits: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    unknown = sorted({name for name in splits.values() if name not in SPLIT_ORDER})
    if unknown:
        raise ValueError(f"expected splits from {list(SPLIT_ORDER)} in {path}, found {unknown}")
    ids = {q.question_id for q in questions}
    if set(splits) != ids:
        missing, extra = sorted(ids - set(splits)), sorted(set(splits) - ids)
        raise ValueError(
            f"expected {path} to cover each question exactly once, "
            f"found {len(missing)} missing {missing[:3]} and {len(extra)} unknown {extra[:3]}"
        )
    return splits


def counted_ids(questions: Sequence[Question]) -> frozenset[str]:
    """Ids of every question except those of the headline-excluded family."""
    return frozenset(q.question_id for q in questions if q.family is not HEADLINE_EXCLUDED_FAMILY)


def scope_ids(
    questions: Sequence[Question], splits: Mapping[str, str] | None
) -> dict[str, frozenset[str]]:
    """Scope name -> question ids. `held-out` is present only when splits are known."""
    counted = counted_ids(questions)
    if splits is None:
        return {SCOPE_HEADLINE: counted}
    return {
        SCOPE_HEADLINE: counted & split_ids(splits, HEADLINE_SPLITS),
        SCOPE_HELD_OUT: counted & split_ids(splits, (SPLIT_HELD_OUT,)),
    }


def split_ids(splits: Mapping[str, str], names: Collection[str]) -> frozenset[str]:
    """Ids of the questions in any of the named splits."""
    return frozenset(qid for qid, name in splits.items() if name in names)


def restrict(joined: JoinedCorpus, ids: Collection[str]) -> JoinedCorpus:
    """The same join, counting only the questions in `ids` (reference order kept).

    Evaluation, references and acceptance all walk `question_ids`, so narrowing it narrows them.
    """
    kept = [qid for qid in joined.question_ids if qid in ids]
    return replace(joined, question_ids=kept)
