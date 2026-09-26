"""Csatlakozó-párosítás: melyik kimenő és bejövő felirat ugyanannak a csőnek a két vége.

Két szabály fut sorban, a bizalmi szint szerint csökkenő sorrendben (design
`kg-construction.md` §5.2): elsőként a partner saját száma (ha a felirat ezt is
elárulja), másodszor a csővezeték/jel-azonosító és az irány. Ami egyik szabályba
sem fér bele egyértelműen, `UnresolvedConnector`-ként kerül ki — sosem tűnik el
csendben (design §10 T3 elfogadási feltétele).
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

# forrás-lap, cél-lap, fajta, reláció, line_number, fluid_code. Kimenő feliratnál
# a forrás a saját lapja és a cél a hivatkozott lap; bejövőnél fordítva — így egy
# valódi pár mindig ugyanide esik (§5.2), mert a splitter épp így vágja el az élt
# (connectors.py:_cut_one_edge): a kimenő referenced_drawing_number a bejövő
# sheet_id-je, és fordítva.
_GroupKey = tuple[str, str, ConnectorKind | None, str | None, str | None, str | None]


def pair_connectors(
    labels: Sequence[ConnectorLabel], sheet_ids: Collection[str]
) -> tuple[list[ConnectorPair], list[UnresolvedConnector]]:
    """Kimenő-bejövő feliratpárokat keres; ami nem párosítható, azt megindokolva jelenti.

    Csak szótárakat és listákat használ, a lap-lista sosem ismétlődik végig
    párononként (a SMOKE-03 lelet, `rejoin.py:88`, épp ezt a hibát kerülte).
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
    """A hivatkozott lap benne van-e a korpuszban — ha nincs, a csatlakozó eleve megoldhatatlan."""
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
    """MatchRule.CONNECTOR_NUMBER: a partner saját száma mindkét oldalról kölcsönösen egyezik.

    Csak akkor talál, ha mindkét felirat ismeri a partnere számát — `DRAWING_ONLY`-nál
    ez a mező hiányzik, és minden csatlakozó a gyengébb szabályra esik (§5.2).
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
    """A kimenő felirathoz illő bejövőt keresi, vagy `None`-t, ha a szabály nem alkalmazható.

    Kétértelmű index-kulcsnál (duplikált connector_number ugyanazon a lapon,
    lásd EX01 C1/C2 tag-jeit, design §2) szándékosan nem választ: a gyengébb
    szabályra (`_pair_by_shared_label`) hagyja a döntést.
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
    """MatchRule.LINE_NUMBER / SERVICE_DIRECTION: csővezeték-szám és irány, csoportba rendezve.

    Egy csoport csak akkor válik párrá, ha pontosan egy kimenő és egy bejövő
    felirat esik rá — minden más eset (üres, több kimenő, több bejövő)
    megoldatlan marad, megindokolva.
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
