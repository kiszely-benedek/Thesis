"""Score a `Resolution` against its answer key (design `kg-construction.md` §6).

Two things are scored: the predicted off-page connector pairs (does the
resolver correctly say "this pipe leaving sheet A continues as this one
entering sheet B"?) and the predicted identity groups (does it correctly say
"this pump drawn on sheet A is the same physical pump as the one on sheet
B"?). Both come out as precision/recall/F1 over a set of unordered pairs, so
the same helper (`_pair_score`) computes both.

This module has no pyDEXPI and no Neo4j import, and it is reusable outside the
synthetic splitter (EXP-0004 will call it on OPEN100, whose truth comes from
`ConnectorObservation` and the OPEN100 manifest, not from a splitter run) —
every scoring function below takes predicted and true pairs/groups already in
one shared key space, and only the two `*_to_original` adapters and
`score_resolution` know about the synthetic `OccurrenceMap`.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from pydantic import BaseModel

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup, SplitManifest
from plantgraph.resolution.localize import OccurrenceMap
from plantgraph.resolution.models import Resolution


class PairScore(BaseModel):
    """Precision/recall/F1 over a set of unordered pairs, plus the counts behind them.

    `precision`, `recall` and `f1` are `None` exactly when their denominator is
    zero (e.g. nothing was predicted, so precision is undefined) — never
    silently coerced to 0.0 or 1.0.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None


class ResolutionScore(BaseModel):
    """One `resolve()` run's accuracy against the answer key: pairs, identity, and rules used."""

    connector_pairs: PairScore
    identity: PairScore
    pair_precision_by_rule: dict[str, float | None]


def pairs_to_original(
    pairs: Sequence[ConnectorPair], occurrence_map: OccurrenceMap
) -> list[ConnectorPair]:
    """Rewrite the resolver's local keys ("sheet:occ_id") to the manifest's original keys."""
    return [
        pair.model_copy(
            update={
                "from_key": occurrence_map.original_key(pair.from_key),
                "to_key": occurrence_map.original_key(pair.to_key),
            }
        )
        for pair in pairs
    ]


def groups_to_original(
    groups: Sequence[IdentityGroup], occurrence_map: OccurrenceMap
) -> list[IdentityGroup]:
    """Rewrite an identity group's home/reference local keys to the manifest's original keys."""
    return [
        group.model_copy(
            update={
                "home": occurrence_map.original_key(group.home),
                "references": [
                    occurrence_map.original_key(reference) for reference in group.references
                ],
            }
        )
        for group in groups
    ]


def score_connector_pairs(
    predicted: Sequence[ConnectorPair], gold: Sequence[ConnectorPair]
) -> PairScore:
    """Precision/recall of predicted connector pairs against the answer key.

    A pair is compared as the unordered set `{from_key, to_key}`: OPEN100 pairs
    have no inherent "from/to" direction (`benchmark/open100/manifest.py`), so
    a reversed pair still counts as a true positive.
    """
    predicted_set = {frozenset((pair.from_key, pair.to_key)) for pair in predicted}
    gold_set = {frozenset((pair.from_key, pair.to_key)) for pair in gold}
    return _pair_score(predicted_set, gold_set)


def score_identity_groups(
    predicted: Sequence[IdentityGroup], gold: Sequence[IdentityGroup]
) -> PairScore:
    """Precision/recall of predicted identity groups against the answer key, scored pairwise.

    A group is a set of occurrences claimed to be the same physical piece of
    equipment (one "home" plus its "reference" repeats). Scoring a whole group
    at once would not tell apart "merged everything correctly" from "merged
    two unrelated groups into one" — so each group of k occurrences is first
    turned into the k(k-1)/2 unordered occurrence pairs it implies ("these two
    are the same item"), and precision/recall are then computed over that set
    of pairs, exactly like `score_connector_pairs`. A citation for this
    reduction is still owed (design note open question 6).
    """
    return _pair_score(_pairwise_links(predicted), _pairwise_links(gold))


def score_resolution(
    resolution: Resolution, manifest: SplitManifest, occurrence_map: OccurrenceMap | None
) -> ResolutionScore:
    """Score one `resolve()` run against its answer key.

    Args:
        resolution: the resolver's output to score.
        manifest: the answer key (`SplitManifest`) it is scored against.
        occurrence_map: translates the resolver's local keys back to the
            manifest's original keys. Pass `None` when the resolver's output
            is already in manifest space, as it is for OPEN100 — there is no
            synthetic renaming to undo, since that pipeline never calls
            `localize()`.
    """
    predicted_pairs = _to_original_pairs(resolution.connector_pairs, occurrence_map)
    predicted_groups = _to_original_groups(resolution.identity_groups, occurrence_map)
    return ResolutionScore(
        connector_pairs=score_connector_pairs(predicted_pairs, manifest.connector_pairs),
        identity=score_identity_groups(predicted_groups, manifest.identity_groups),
        pair_precision_by_rule=_pair_precision_by_rule(predicted_pairs, manifest.connector_pairs),
    )


def _to_original_pairs(
    pairs: Sequence[ConnectorPair], occurrence_map: OccurrenceMap | None
) -> list[ConnectorPair]:
    if occurrence_map is None:
        return list(pairs)
    return pairs_to_original(pairs, occurrence_map)


def _to_original_groups(
    groups: Sequence[IdentityGroup], occurrence_map: OccurrenceMap | None
) -> list[IdentityGroup]:
    if occurrence_map is None:
        return list(groups)
    return groups_to_original(groups, occurrence_map)


def _pairwise_links(groups: Sequence[IdentityGroup]) -> set[frozenset[str]]:
    """Every unordered occurrence pair that some group claims is the same physical item."""
    links: set[frozenset[str]] = set()
    for group in groups:
        members = [group.home, *group.references]
        links.update(frozenset(pair) for pair in combinations(members, 2))
    return links


def _pair_score(predicted: set[frozenset[str]], gold: set[frozenset[str]]) -> PairScore:
    true_positives = len(predicted & gold)
    false_positives = len(predicted - gold)
    false_negatives = len(gold - predicted)
    precision, recall, f1 = _precision_recall_f1(true_positives, false_positives, false_negatives)
    return PairScore(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _precision_recall_f1(
    true_positives: int, false_positives: int, false_negatives: int
) -> tuple[float | None, float | None, float | None]:
    precision = _safe_ratio(true_positives, true_positives + false_positives)
    recall = _safe_ratio(true_positives, true_positives + false_negatives)
    f1 = None
    if precision is not None and recall is not None and precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _pair_precision_by_rule(
    predicted: Sequence[ConnectorPair], gold: Sequence[ConnectorPair]
) -> dict[str, float | None]:
    """Precision of predicted pairs, broken down by which rule found them (design §5.2).

    This shows whether the weaker rules (`LINE_NUMBER`, `SERVICE_DIRECTION`)
    are pulling their weight or introducing wrong pairs that the strongest
    rule (`CONNECTOR_NUMBER`) would not have made.
    """
    gold_set = {frozenset((pair.from_key, pair.to_key)) for pair in gold}
    predicted_by_rule: dict[str, list[ConnectorPair]] = {}
    for pair in predicted:
        predicted_by_rule.setdefault(pair.match_rule.value, []).append(pair)
    return {rule: _rule_precision(pairs, gold_set) for rule, pairs in predicted_by_rule.items()}


def _rule_precision(pairs: Sequence[ConnectorPair], gold_set: set[frozenset[str]]) -> float | None:
    if not pairs:
        return None
    hits = sum(1 for pair in pairs if frozenset((pair.from_key, pair.to_key)) in gold_set)
    return hits / len(pairs)
