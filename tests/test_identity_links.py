"""Link sets, the one-to-one rule, the same-sheet split and G2 stability (X-T3).

Uses the toy of `test_identity_deciders.py`. Exact-tag grouping already joins the S2 and S3 copies
of the spare `P-1203B`; the links then compete as the design's section 5.3 describes.
"""

from __future__ import annotations

import pytest

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.identity_candidates import ContentKey, generate_candidates
from plantgraph.resolution.identity_deciders import (
    StringSimilarityDecider,
    UnitAwareDecider,
)
from plantgraph.resolution.identity_links import (
    IdentityLink,
    IdentityLinkSet,
    LinkedGrouping,
    decide_links,
    group_with_links,
)
from plantgraph.resolution.localize import localize
from test_identity_deciders import PUMP, toy_sheets

PUMP_A = ContentKey("S1", "P-1203A", PUMP)
PUMP_REF = ContentKey("S2", "P1203A", PUMP)
SPARE_S2 = ContentKey("S2", "P-1203B", PUMP)
SPARE_S3 = ContentKey("S3", "P-1203B", PUMP)
UNPAD_S4 = ContentKey("S4", "P-123A", PUMP)


def _link(first: ContentKey, second: ContentKey, score: float) -> IdentityLink:
    return IdentityLink(first=first, second=second, score=score, string_score=score)


def _tag_groups(sheets: list[SheetGraph], grouping: LinkedGrouping) -> set[frozenset[ContentKey]]:
    """Each group as the content keys of its occurrences (independent of local-key salt)."""
    by_local_key = {
        f"{sheet.sheet_id}:{node_id}": ContentKey(
            sheet.sheet_id, attributes["tag"], attributes["node_class"]
        )
        for sheet in sheets
        for node_id, attributes in sheet.graph.nodes(data=True)
    }
    return {
        frozenset(by_local_key[key] for key in [group.home, *group.references])
        for group in grouping.groups
    }


def test_no_links_leaves_only_the_exact_tag_group() -> None:
    sheets = toy_sheets()
    grouping = group_with_links(sheets, IdentityLinkSet(decider="d0", links=[]))
    assert _tag_groups(sheets, grouping) == {frozenset({SPARE_S2, SPARE_S3})}
    assert (grouping.n_dropped_one_to_one, grouping.n_identity_conflicts) == (0, 0)


def test_one_link_merges_the_variant_into_the_home_group() -> None:
    sheets = toy_sheets()
    grouping = group_with_links(
        sheets, IdentityLinkSet(decider="x", links=[_link(PUMP_A, PUMP_REF, 1.0)])
    )
    assert frozenset({PUMP_A, PUMP_REF}) in _tag_groups(sheets, grouping)
    home_group = next(g for g in grouping.groups if g.tag == "P-1203A")
    assert home_group.home == "S1:x1"  # the home has the most properties


def test_one_to_one_drops_the_weaker_link_from_the_same_occurrence_to_the_same_sheet() -> None:
    sheets = toy_sheets()
    links = IdentityLinkSet(
        decider="d1",
        links=[_link(PUMP_A, SPARE_S2, 0.83), _link(PUMP_A, PUMP_REF, 1.0)],  # given weakest first
    )
    grouping = group_with_links(sheets, links)
    assert grouping.n_dropped_one_to_one == 1  # the A/B spare link; the stronger link won
    assert frozenset({PUMP_A, PUMP_REF}) in _tag_groups(sheets, grouping)
    assert all(SPARE_S2 not in group for group in _tag_groups(sheets, grouping) if PUMP_A in group)


def test_equal_scores_are_ordered_by_d1_score_then_content_key() -> None:
    sheets = toy_sheets()
    stronger_text = IdentityLink(first=PUMP_A, second=PUMP_REF, score=0.9, string_score=1.0)
    weaker_text = IdentityLink(first=PUMP_A, second=SPARE_S2, score=0.9, string_score=0.83)
    for ordering in ([stronger_text, weaker_text], [weaker_text, stronger_text]):
        grouping = group_with_links(sheets, IdentityLinkSet(decider="d2", links=ordering))
        assert frozenset({PUMP_A, PUMP_REF}) in _tag_groups(sheets, grouping)


def test_a_link_joining_two_occurrences_of_one_sheet_is_a_counted_conflict() -> None:
    # PUMP_A is first linked to the S2 reference; its link to the S3 spare would then place the
    # S2 reference and the S2 spare (exact-grouped with the S3 spare) in one group.
    sheets = toy_sheets()
    links = IdentityLinkSet(
        decider="d1", links=[_link(PUMP_A, PUMP_REF, 1.0), _link(PUMP_A, SPARE_S3, 0.83)]
    )
    grouping = group_with_links(sheets, links)
    assert grouping.n_dropped_one_to_one == 0
    assert grouping.n_identity_conflicts == 1
    groups = _tag_groups(sheets, grouping)
    assert frozenset({PUMP_A, PUMP_REF}) in groups
    assert frozenset({SPARE_S2, SPARE_S3}) in groups  # the conflict refused the merge


def test_d1_end_to_end_merges_the_unpad_lookalike_and_d2_does_not() -> None:
    sheets = toy_sheets()
    pairs = generate_candidates(sheets, []).pairs
    with_d1 = group_with_links(sheets, decide_links(pairs, StringSimilarityDecider(0.8)))
    with_d2 = group_with_links(sheets, decide_links(pairs, UnitAwareDecider(0.8)))
    assert any(UNPAD_S4 in group for group in _tag_groups(sheets, with_d1))
    assert all(UNPAD_S4 not in group for group in _tag_groups(sheets, with_d2))
    assert frozenset({PUMP_A, PUMP_REF}) in _tag_groups(sheets, with_d2)


def test_decide_links_records_the_decider_name_and_scores() -> None:
    pairs = generate_candidates(toy_sheets(), []).pairs
    link_set = decide_links(pairs, StringSimilarityDecider(0.99))
    assert link_set.decider == "d1"
    tank_pair = (ContentKey("S1", "TK-1201", "Tank"), ContentKey("S3", "TK 1201", "Tank"))
    assert {(link.first, link.second) for link in link_set.links} == {(PUMP_A, PUMP_REF), tank_pair}
    assert all(link.score == link.string_score == 1.0 for link in link_set.links)


def test_a_link_to_an_unknown_occurrence_is_refused() -> None:
    missing = ContentKey("S9", "P-1", PUMP)
    with pytest.raises(ValueError, match="expected the link's occurrence"):
        group_with_links(
            toy_sheets(), IdentityLinkSet(decider="x", links=[_link(PUMP_A, missing, 1.0)])
        )


def test_link_set_round_trips_through_json() -> None:
    link_set = IdentityLinkSet(decider="d2", links=[_link(PUMP_A, PUMP_REF, 0.9)])
    assert IdentityLinkSet.model_validate_json(link_set.model_dump_json()) == link_set


def test_a_g2_salt_gives_the_same_groups() -> None:
    plain, _ = localize(toy_sheets(), salt="")
    salted, _ = localize(toy_sheets(), salt="G2")
    decider = UnitAwareDecider(0.8)
    results = []
    for sheets in (plain, salted):
        link_set = decide_links(generate_candidates(sheets, []).pairs, decider)
        grouping = group_with_links(sheets, link_set)
        results.append((_tag_groups(sheets, grouping), link_set.model_dump_json(), grouping))
    assert results[0][0] == results[1][0]
    assert results[0][1] == results[1][1]  # links hold content keys only: byte-identical
    assert results[0][2].n_dropped_one_to_one == results[1][2].n_dropped_one_to_one
