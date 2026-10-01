"""Connector pairing: which outgoing and incoming label are the two ends of the same pipe.

Two rules run in sequence, in decreasing order of confidence (design
`kg-construction.md` §5.2): first the partner's own number (if the label reveals
it too), second the pipe/signal identifier and direction. Whatever fits neither
rule unambiguously comes out as `UnresolvedConnector` — it never silently
disappears (design §10 T3's acceptance condition).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Sequence

from plantgraph.benchmark.models import (
    ConnectorKind,
    ConnectorPair,
    Direction,
    MatchRule,
    UnresolvedConnector,
)
from plantgraph.resolution.connector_labels import ConnectorLabel

# source sheet, target sheet, kind, relation, line_number, fluid_code, loop_tag. For an
# outgoing label, the source is its own sheet and the target is the referenced
# sheet; for incoming, the reverse — so a real pair always lands on the same key
# (§5.2), because the splitter cuts the edge exactly this way
# (connectors.py:_cut_one_edge): the outgoing referenced_drawing_number is the
# incoming's sheet_id, and vice versa.
_GroupKey = tuple[str, str, ConnectorKind | None, str | None, str | None, str | None, str | None]


def pair_connectors(
    labels: Sequence[ConnectorLabel], sheet_ids: Collection[str]
) -> tuple[list[ConnectorPair], list[UnresolvedConnector]]:
    """Find outgoing-incoming label pairs; report whatever can't be paired, with a reason.

    Uses only dictionaries and lists — the sheet list is never iterated once per
    pair (the SMOKE-03 finding, `rejoin.py:88`, avoided exactly this mistake).
    """
    remaining, unresolved = _drop_absent_targets(labels, sheet_ids)
    outgoing = [label for label in remaining if label.direction is Direction.OUTGOING]
    incoming = [label for label in remaining if label.direction is Direction.INCOMING]

    pairs, matched_keys = _pair_by_connector_number(outgoing, incoming)
    rest = [label for label in remaining if label.key not in matched_keys]
    more_pairs, more_unresolved = _pair_by_shared_label(rest)

    return pairs + more_pairs, unresolved + more_unresolved


def _drop_absent_targets(
    labels: Sequence[ConnectorLabel], sheet_ids: Collection[str]
) -> tuple[list[ConnectorLabel], list[UnresolvedConnector]]:
    """Is the referenced sheet in the corpus — else this connector is unresolvable."""
    remaining: list[ConnectorLabel] = []
    unresolved: list[UnresolvedConnector] = []
    for label in labels:
        if label.referenced_drawing_number in sheet_ids:
            remaining.append(label)
        else:
            unresolved.append(
                UnresolvedConnector(from_key=label.key, reason="referenced drawing not in corpus")
            )
    return remaining, unresolved


def _pair_by_connector_number(
    outgoing: Sequence[ConnectorLabel], incoming: Sequence[ConnectorLabel]
) -> tuple[list[ConnectorPair], set[str]]:
    """MatchRule.CONNECTOR_NUMBER: the partner's own number matches mutually from both sides.

    Only finds a match if both labels know their partner's number — under
    `DRAWING_ONLY` this field is missing, and every connector falls to the
    weaker rule (§5.2).
    """
    incoming_by_key: dict[tuple[str, str], list[ConnectorLabel]] = defaultdict(list)
    for label in incoming:
        if label.referenced_connector_number is not None:
            incoming_by_key[(label.sheet_id, label.connector_number)].append(label)

    pairs: list[ConnectorPair] = []
    matched: set[str] = set()
    for label in outgoing:
        candidate = _mutual_connector_number_match(label, incoming_by_key)
        if candidate is None:
            continue
        pairs.append(
            ConnectorPair(
                from_key=label.key,
                to_key=candidate.key,
                line_number=label.line_number,
                match_rule=MatchRule.CONNECTOR_NUMBER,
            )
        )
        matched.add(label.key)
        matched.add(candidate.key)
    return pairs, matched


def _mutual_connector_number_match(
    label: ConnectorLabel, incoming_by_key: dict[tuple[str, str], list[ConnectorLabel]]
) -> ConnectorLabel | None:
    """Find the incoming label matching an outgoing one, or `None` if the rule doesn't apply.

    On an ambiguous index key (duplicated connector_number on the same sheet,
    see EX01's C1/C2 tags, design §2), deliberately makes no choice: leaves the
    decision to the weaker rule (`_pair_by_shared_label`).
    """
    if label.referenced_connector_number is None:
        return None
    key = (label.referenced_drawing_number, label.referenced_connector_number)
    candidates = incoming_by_key.get(key, [])
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    is_mutual = (
        candidate.referenced_connector_number == label.connector_number
        and candidate.referenced_drawing_number == label.sheet_id
    )
    return candidate if is_mutual else None


def _pair_by_shared_label(
    labels: Sequence[ConnectorLabel],
) -> tuple[list[ConnectorPair], list[UnresolvedConnector]]:
    """MatchRule.LINE_NUMBER / SERVICE_DIRECTION: pipe-segment number and direction, grouped.

    A group only becomes a pair if exactly one outgoing and one incoming label
    fall into it — every other case (empty, multiple outgoing, multiple
    incoming) stays unresolved, with a reason attached.
    """
    groups: dict[_GroupKey, list[ConnectorLabel]] = defaultdict(list)
    for label in labels:
        groups[_group_key(label)].append(label)

    pairs: list[ConnectorPair] = []
    unresolved: list[UnresolvedConnector] = []
    for group in groups.values():
        group_pair, group_unresolved = _pair_or_report_one_group(group)
        pairs += group_pair
        unresolved += group_unresolved
    return pairs, unresolved


def _pair_or_report_one_group(
    group: list[ConnectorLabel],
) -> tuple[list[ConnectorPair], list[UnresolvedConnector]]:
    outgoing = [label for label in group if label.direction is Direction.OUTGOING]
    incoming = [label for label in group if label.direction is Direction.INCOMING]
    if len(outgoing) == 1 and len(incoming) == 1:
        return [_build_shared_label_pair(outgoing[0], incoming[0])], []
    reason = f"ambiguous: {len(outgoing)} outgoing, {len(incoming)} incoming share this label"
    return [], [UnresolvedConnector(from_key=label.key, reason=reason) for label in group]


def _group_key(label: ConnectorLabel) -> _GroupKey:
    if label.direction is Direction.OUTGOING:
        source_sheet, target_sheet = label.sheet_id, label.referenced_drawing_number
    else:
        source_sheet, target_sheet = label.referenced_drawing_number, label.sheet_id
    return (
        source_sheet,
        target_sheet,
        label.kind,
        label.relation,
        label.line_number,
        label.fluid_code,
        label.loop_tag,
    )


def _build_shared_label_pair(outgoing: ConnectorLabel, incoming: ConnectorLabel) -> ConnectorPair:
    has_line_number = outgoing.line_number is not None
    rule = MatchRule.LINE_NUMBER if has_line_number else MatchRule.SERVICE_DIRECTION
    return ConnectorPair(
        from_key=outgoing.key,
        to_key=incoming.key,
        line_number=outgoing.line_number,
        match_rule=rule,
    )
