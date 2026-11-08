"""One corpus's evaluated policies, narrowed to the questions of a scope (a "view").

The sealed tables never recompute a policy: they re-run the same offline join on a narrower
list of question ids, so every figure uses exactly the decisions the all-question table uses.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean

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


@dataclass(frozen=True)
class ScaleGroup:
    """The plants of one scale (say the five 1,000-sheet plants) pooled under one label.

    A scale with a single plant is labelled with that plant's corpus id, which keeps the
    first measurement's single-corpus tables and claims unchanged.
    """

    label: str
    plants: tuple[SealedCorpus, ...]

    @property
    def n_sheets(self) -> int:
        """The scale's size: the mean realized sheet count of its plants."""
        return round(fmean(plant.n_sheets for plant in self.plants))

    @property
    def is_pooled(self) -> bool:
        """Whether the scale has more than one plant, so intervals need the two-stage bootstrap."""
        return len(self.plants) > 1


def group_scope_views(
    group: ScaleGroup, views: Mapping[str, Mapping[str, ScopeView]]
) -> dict[str, list[ScopeView]]:
    """Scope name -> each plant's view, for the scopes every plant of the scale has."""
    first = views[group.plants[0].corpus_id]
    by_scope = {scope: [views[p.corpus_id].get(scope) for p in group.plants] for scope in first}
    return {
        scope: [v for v in found if v is not None]
        for scope, found in by_scope.items()
        if all(v is not None for v in found)
    }


def common_policies(plants: Sequence[ScopeView]) -> list[str]:
    """Policies evaluated on every plant's view, in the first plant's order."""
    return [p for p in plants[0].evaluations if all(p in v.evaluations for v in plants)]


def group_scales(
    corpora: Sequence[SealedCorpus], scales: Mapping[str, Sequence[str]] | None = None
) -> list[ScaleGroup]:
    """Corpora grouped by scale, in order of first appearance; `scales` maps label -> corpus ids.

    A corpus named in no group is a scale of its own, labelled with its corpus id.

    Raises:
        ValueError: a group names an unknown corpus, or a corpus belongs to two groups.
    """
    by_id = {c.corpus_id: c for c in corpora}
    label_of: dict[str, str] = {}
    for label, ids in (scales or {}).items():
        for corpus_id in ids:
            if corpus_id not in by_id or corpus_id in label_of:
                raise ValueError(
                    f"expected each corpus of scale {label!r} to exist in {sorted(by_id)} and "
                    f"belong to one scale, found {corpus_id!r} "
                    f"(already in {label_of.get(corpus_id)!r})"
                )
            label_of[corpus_id] = label
    members: dict[str, list[SealedCorpus]] = {}
    for corpus in corpora:
        members.setdefault(label_of.get(corpus.corpus_id, corpus.corpus_id), []).append(corpus)
    return [ScaleGroup(label, tuple(plants)) for label, plants in members.items()]
