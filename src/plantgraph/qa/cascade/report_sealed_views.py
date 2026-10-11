"""One corpus's evaluated policies, narrowed to the questions of a scope (a "view").

The sealed tables never recompute a policy: they re-run the same offline join on a narrower
list of question ids, so every figure uses exactly the decisions the all-question table uses.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from plantgraph.qa.cascade.evaluate import Evaluation, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_scopes import restrict, scope_ids
from plantgraph.qa.models import Question


@dataclass(frozen=True)
class SealedCorpus:
    """What the sealed tables need to know about one corpus."""

    corpus_id: str
    n_sheets: int
    questions: Sequence[Question]
    #: question id -> split name; `None` when the corpus has no `splits.json`.
    splits: Mapping[str, str] | None
    #: Policy name -> join / all-question evaluation, for the policies that could be evaluated.
    joins: Mapping[str, JoinedCorpus]
    evaluations: Mapping[str, Evaluation]


@dataclass(frozen=True)
class ScopeView:
    """The policies of one corpus evaluated on one set of question ids."""

    corpus_id: str
    scope: str
    ids: frozenset[str]
    joins: Mapping[str, JoinedCorpus]
    evaluations: Mapping[str, Evaluation]

    @property
    def n_questions(self) -> int:
        """How many questions the scope counts."""
        return len(self.ids)


def make_view(corpus: SealedCorpus, scope: str, ids: Collection[str], cutoff_s: float) -> ScopeView:
    """Evaluate every policy of `corpus` on the questions in `ids`."""
    joins = {name: restrict(joined, ids) for name, joined in corpus.joins.items()}
    evaluations = {name: evaluate_policy(joined, cutoff_s) for name, joined in joins.items()}
    return ScopeView(corpus.corpus_id, scope, frozenset(ids), joins, evaluations)


def scope_views(corpus: SealedCorpus, cutoff_s: float) -> dict[str, ScopeView]:
    """Scope name -> view, for the scopes this corpus has (held-out needs `splits.json`)."""
    ids_by_scope = scope_ids(corpus.questions, corpus.splits)
    return {
        scope: make_view(corpus, scope, ids, cutoff_s)
        for scope, ids in ids_by_scope.items()
        if ids  # a scope with no question has nothing to evaluate
    }
