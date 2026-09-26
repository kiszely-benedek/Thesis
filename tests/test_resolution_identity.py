"""`group_identities` — a predikált azonosság-csoportok (design `kg-construction.md` §5.3).

Kézzel épített lokalizált lapokon teszteli elszigetelten: a teljes
splitter -> localize -> identity csővezetéket a resolver gate-jei
(`test_resolution_resolver.py`) futtatják.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.identity import group_identities


def _sheet(sheet_id: str, nodes: dict[str, dict[str, object]]) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attrs in nodes.items():
        graph.add_node(node_id, **attrs)
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def test_a_tag_on_two_sheets_forms_a_group_with_the_fuller_occurrence_as_home() -> None:
    home_sheet = _sheet(
        "0", {"occ-home": {"node_class": "CentrifugalPump", "tag": "P-1", "plant_id": "u0"}}
    )
    reference_sheet = _sheet("1", {"occ-ref": {"node_class": "CentrifugalPump", "tag": "P-1"}})

    groups, ambiguous = group_identities([home_sheet, reference_sheet])

    assert ambiguous == 0
    (group,) = groups
    assert group.tag == "P-1"
    assert group.home == "0:occ-home"
    assert group.references == ["1:occ-ref"]


def test_tie_in_property_count_is_broken_by_sheet_id_never_by_occurrence_id() -> None:
    """A holtversenyt a lap-id dönti el — az occurrence id sosem, hisz a G2 kapunál az más lenne.

    Mindkét előfordulás ugyanannyi tulajdonságot hordoz; az occurrence id
    szándékosan az ellenkező sorrendben áll, mint a sheet_id, hogy a teszt
    kibukjon, ha valaki tévedésből az id szerint választana.
    """
    sheet_a = _sheet("a", {"zzz": {"node_class": "CentrifugalPump", "tag": "P-1"}})
    sheet_b = _sheet("b", {"aaa": {"node_class": "CentrifugalPump", "tag": "P-1"}})

    groups, _ambiguous = group_identities([sheet_a, sheet_b])
    (group,) = groups

    assert group.home == "a:zzz"
    assert group.references == ["b:aaa"]


def test_a_tag_seen_on_only_one_sheet_forms_no_group() -> None:
    sheet = _sheet(
        "0",
        {
            "occ-1": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "occ-2": {"node_class": "CentrifugalPump", "tag": "P-1"},
        },
    )

    groups, ambiguous = group_identities([sheet])

    assert groups == []
    assert ambiguous == 1, "két azonos tag ugyanazon a lapon: kétértelmű, nem egy magányos csoport"


def test_ambiguous_tag_within_one_sheet_is_excluded_even_with_a_valid_partner_elsewhere() -> None:
    """EX01-en a C1 tag háromszor fordul elő egyetlen lapon — ilyenkor sehol se szabad csoportba
    kerülnie, még akkor sem, ha egy másik lapon is felbukkanna."""
    ambiguous_sheet = _sheet(
        "0",
        {
            "occ-1": {"node_class": "GlobeValve", "tag": "C1"},
            "occ-2": {"node_class": "GlobeValve", "tag": "C1"},
        },
    )
    other_sheet = _sheet("1", {"occ-3": {"node_class": "GlobeValve", "tag": "C1"}})

    groups, ambiguous = group_identities(
        [ambiguous_sheet, other_sheet], classes=frozenset({"GlobeValve"})
    )

    assert groups == []
    assert ambiguous == 1


def test_only_the_given_classes_are_considered() -> None:
    """Alapértelmezésben csak berendezés csoportosul — a szelep tag-je szakaszonként ismétlődik."""
    sheet_a = _sheet("0", {"v1": {"node_class": "GlobeValve", "tag": "C1"}})
    sheet_b = _sheet("1", {"v2": {"node_class": "GlobeValve", "tag": "C1"}})

    groups, ambiguous = group_identities([sheet_a, sheet_b])

    assert groups == []
    assert ambiguous == 0


def test_node_without_a_tag_is_ignored() -> None:
    sheet_a = _sheet("0", {"stub": {"node_class": "FlowOutPipeOffPageConnector"}})
    sheet_b = _sheet("1", {"stub": {"node_class": "FlowOutPipeOffPageConnector"}})

    groups, ambiguous = group_identities([sheet_a, sheet_b])

    assert groups == []
    assert ambiguous == 0
