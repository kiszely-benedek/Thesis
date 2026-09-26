"""Azonosság-csoportosítás: ugyanaz a berendezés több lapon is (design `kg-construction.md` §5.3).

A splitter némely berendezést több lapra is felrajzol (`splitter.py:_duplicate_equipment`):
egy teljes attribútumú home-előfordulás, és minden szomszédos lapon egy csonkolt
reference (csak tag és node_class). A `localize()` már lezárta a közös node_id-t
(L1 szivárgás, design §4.1), ezért ez a modul csak a tag-en és az osztályon
keresztül ismerheti fel, hogy két előfordulás ugyanaz a fizikai berendezés —
pontosan úgy, ahogy egy valódi berendezés-jegyzék is csak a tag alapján
azonosítana.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import NamedTuple

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES

#: (tag, node_class) — ez azonosítja a fizikai berendezést, sosem az occurrence id
#: (design §5.3: a home kiválasztása ne függjön a salt-tal átnevezett helyi kulcstól).
_TagKey = tuple[str, str]


class _Occurrence(NamedTuple):
    """Egy tag-kulcs egyetlen előfordulása egy lokalizált lapon."""

    sheet_id: str
    local_key: str
    property_count: int


def group_identities(
    sheets: Sequence[SheetGraph], classes: frozenset[str] = EQUIPMENT_CLASSES
) -> tuple[list[IdentityGroup], int]:
    """(tag, node_class) szerint csoportosítja az előfordulásokat, és megkeresi a predikált home-ot.

    Csak `classes` osztályaira nézi (alapértelmezetten csak berendezés): a
    szelepek tag-je csővezeték-szakaszonként ismétlődik, azok laponkénti
    összevonása hamis egyesítést adna (design §5.3).

    Returns:
        A megtalált csoportok (rendezve tag szerint), és a lapon belül
        kétértelmű — ezért kizárt — tag-kulcsok száma.
    """
    occurrences_by_key = _occurrences_by_tag_key(sheets, classes)
    ambiguous_tag_keys = _drop_ambiguous_within_a_sheet(occurrences_by_key)
    groups = [
        _build_group(tag, occurrences)
        for (tag, _node_class), occurrences in sorted(occurrences_by_key.items())
        if len({occ.sheet_id for occ in occurrences}) >= 2
    ]
    return groups, ambiguous_tag_keys


def _occurrences_by_tag_key(
    sheets: Sequence[SheetGraph], classes: frozenset[str]
) -> dict[_TagKey, list[_Occurrence]]:
    occurrences: dict[_TagKey, list[_Occurrence]] = defaultdict(list)
    for sheet in sheets:
        for node_id, attrs in sheet.graph.nodes(data=True):
            tag = attrs.get("tag")
            node_class = attrs.get("node_class")
            if not tag or node_class not in classes:
                continue
            local_key = f"{sheet.sheet_id}:{node_id}"
            occurrences[(tag, node_class)].append(
                _Occurrence(sheet.sheet_id, local_key, len(attrs))
            )
    return occurrences


def _drop_ambiguous_within_a_sheet(occurrences_by_key: dict[_TagKey, list[_Occurrence]]) -> int:
    """Kihagy egy tag-kulcsot, ha egy laponon belül nem egyedi (pl. EX01 duplikált szelep-tagjei).

    A kizárt kulcs egyik előfordulása sem kerül csoportba — a resolver inkább
    egyáltalán nem dönt, mint hogy találgasson, melyik a helyes pár.
    """
    ambiguous_keys = [
        key
        for key, occurrences in occurrences_by_key.items()
        if len({occ.sheet_id for occ in occurrences}) < len(occurrences)
    ]
    for key in ambiguous_keys:
        del occurrences_by_key[key]
    return len(ambiguous_keys)


def _build_group(tag: str, occurrences: list[_Occurrence]) -> IdentityGroup:
    """A legtöbb tulajdonságú előfordulás lesz a predikált home; holtversenyt a lap-id dönt el.

    Sosem az occurrence id: a G2 kapu (salt-tal átnevezett gráf) ugyanazt a
    home-ot kell adja, pedig az id-k teljesen mások lennének.
    """
    home = min(occurrences, key=lambda occ: (-occ.property_count, occ.sheet_id))
    references = sorted(occ.local_key for occ in occurrences if occ.local_key != home.local_key)
    return IdentityGroup(tag=tag, home=home.local_key, references=references)
