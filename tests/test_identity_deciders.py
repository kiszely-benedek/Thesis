"""Deciders D0 to D2 on a hand-built toy whose pairs are the design's hard cases (X-T3).

Toy sheets (all equipment; `Pxxxx` are pumps):
- S1: home pump `P-1203A` (unit 12) and home tank `TK-1201` (unit 12);
- S2: reference `P1203A` (the S1 pump, written differently), home spare `P-1203B` (unit 12);
- S3: reference `TK 1201`, reference `P-1203B` (exact copy of the spare) and a unit-12 tank;
- S4: home pump `P-123A` in unit 1: the `unpad_sequence` look-alike of `P-1203A`
  (unit 1 sequence 23 against unit 12 sequence 03).
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.identity_candidates import (
    CandidatePair,
    ContentKey,
    generate_candidates,
)
from plantgraph.resolution.identity_deciders import (
    ExactTagDecider,
    PairDecider,
    StringSimilarityDecider,
    UnitAwareDecider,
    normalise_tag,
    string_similarity,
    units_agree,
)

PUMP = "CentrifugalPump"
TANK = "Tank"


def _sheet(sheet_id: str, nodes: dict[str, dict[str, object]]) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attributes in nodes.items():
        graph.add_node(node_id, **attributes)
    return SheetGraph(sheet_id, graph)


def toy_sheets() -> list[SheetGraph]:
    return [
        _sheet(
            "S1",
            {
                "x1": {"node_class": PUMP, "tag": "P-1203A", "unit_id": "12"},
                "x2": {"node_class": TANK, "tag": "TK-1201", "unit_id": "12"},
            },
        ),
        _sheet(
            "S2",
            {
                "y1": {"node_class": PUMP, "tag": "P1203A"},
                "y2": {"node_class": PUMP, "tag": "P-1203B", "unit_id": "12"},
            },
        ),
        _sheet(
            "S3",
            {
                "z1": {"node_class": TANK, "tag": "TK 1201"},
                "z2": {"node_class": PUMP, "tag": "P-1203B"},
                "z3": {"node_class": TANK, "tag": "TK-9999", "unit_id": "12"},
            },
        ),
        _sheet("S4", {"w1": {"node_class": PUMP, "tag": "P-123A", "unit_id": "1"}}),
    ]


def toy_pair(sheet_a: str, tag_a: str, sheet_b: str, tag_b: str) -> CandidatePair:
    """The toy's candidate pair between two occurrences, in either order."""
    wanted = {(sheet_a, tag_a), (sheet_b, tag_b)}
    for pair in generate_candidates(toy_sheets(), []).pairs:
        if {
            (pair.first.sheet_id, pair.first.tag),
            (pair.second.sheet_id, pair.second.tag),
        } == wanted:
            return pair
    raise AssertionError(f"no candidate pair for {wanted}")


SPARE = ("S1", "P-1203A", "S2", "P-1203B")
UNPAD = ("S1", "P-1203A", "S4", "P-123A")
VARIANT = ("S1", "P-1203A", "S2", "P1203A")


def test_normaliser_keeps_upper_case_letters_and_digits_only() -> None:
    assert normalise_tag("12-p-03a") == "12P03A"
    assert normalise_tag("TK 1201") == "TK1201"
    assert normalise_tag("---") == ""


@pytest.mark.parametrize(
    ("tag_a", "tag_b", "expected"),
    [
        ("P-1203A", "P-1203B", 10 / 12),  # A/B spares: five of six characters shared
        ("P-1203A", "P-123A", 10 / 11),  # unpad ambiguity: looks even closer than the spares
        ("P-1203A", "P1203a", 1.0),  # separator and case only
        ("---", "P-1", 0.0),  # nothing left to compare
    ],
)
def test_d1_similarity_table(tag_a: str, tag_b: str, expected: float) -> None:
    assert string_similarity(tag_a, tag_b) == pytest.approx(expected)


def test_d0_accepts_only_equal_tag_and_class() -> None:
    assert not ExactTagDecider().decide(toy_pair(*SPARE)).accept
    same = CandidatePair(
        first=ContentKey("S1", "P-1", PUMP),
        second=ContentKey("S2", "P-1", PUMP),
        blocking_key=(PUMP, "1"),
        card="",
    )
    assert ExactTagDecider().decide(same).score == 1.0


def test_d1_text_alone_accepts_the_spare_and_the_unpad_lookalike() -> None:
    d1 = StringSimilarityDecider(threshold=0.8)
    assert d1.decide(toy_pair(*VARIANT)).accept
    assert d1.decide(toy_pair(*SPARE)).accept  # the false friend that context must catch
    assert d1.decide(toy_pair(*UNPAD)).accept
    assert not StringSimilarityDecider(threshold=0.95).decide(toy_pair(*SPARE)).accept


def test_d2_rejects_the_unpad_lookalike_by_unit_but_still_accepts_the_same_unit_spare() -> None:
    d2 = UnitAwareDecider(threshold=0.8)
    assert d2.decide(toy_pair(*VARIANT)).accept  # S2's reference prints no unit; its sheet has 12
    assert d2.decide(toy_pair(*SPARE)).accept  # same unit: only the one-to-one rule separates it
    unpad = d2.decide(toy_pair(*UNPAD))
    assert (unpad.score, unpad.accept) == (0.0, False)  # unit 12 against unit 1


def test_d2_scores_like_d1_when_units_agree() -> None:
    pair = toy_pair(*SPARE)
    assert (
        UnitAwareDecider(0.5).decide(pair).score == StringSimilarityDecider(0.5).decide(pair).score
    )


def _unit_pair(
    first_unit: str | None,
    first_sheet_units: tuple[str, ...],
    second_sheet_units: tuple[str, ...],
) -> CandidatePair:
    return CandidatePair(
        first=ContentKey("S1", "P-1", PUMP),
        second=ContentKey("S2", "P1", PUMP),
        blocking_key=(PUMP, "1"),
        card="",
        first_unit=first_unit,
        first_sheet_units=first_sheet_units,
        second_unit=None,
        second_sheet_units=second_sheet_units,
    )


def test_d2_accepts_a_unit_among_several_on_bs_sheet() -> None:
    # B's sheet prints units 12 and 13; A is unit 13: "among" holds (the design's rule)
    assert UnitAwareDecider(0.5).decide(_unit_pair("13", ("13",), ("12", "13"))).accept


def test_d2_uses_every_unit_of_a_references_sheet() -> None:
    assert units_agree(_unit_pair(None, ("11", "12"), ("12", "14")))
    assert not units_agree(_unit_pair(None, ("11", "12"), ("14",)))


@pytest.mark.parametrize(
    ("first_unit", "first_sheet_units", "second_sheet_units"),
    [("12", ("12",), ()), (None, (), ("12",)), (None, (), ())],  # unknown on either side rejects
)
def test_d2_rejects_unknown_units(
    first_unit: str | None, first_sheet_units: tuple[str, ...], second_sheet_units: tuple[str, ...]
) -> None:
    pair = _unit_pair(first_unit, first_sheet_units, second_sheet_units)
    assert not UnitAwareDecider(0.5).decide(pair).accept


def test_candidate_pairs_carry_the_cards_unit_facts() -> None:
    pair = toy_pair(*VARIANT)  # A: the S1 home pump, B: S2's reference without a printed unit
    assert (pair.first_unit, pair.first_sheet_units) == ("12", ("12",))
    assert (pair.second_unit, pair.second_sheet_units) == (None, ("12",))


@pytest.mark.parametrize("threshold", [0.0, -0.1, 1.5])
def test_thresholds_outside_zero_one_are_refused(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        StringSimilarityDecider(threshold)
    with pytest.raises(ValueError, match="threshold"):
        UnitAwareDecider(threshold)


def test_every_decider_satisfies_the_protocol() -> None:
    deciders: list[PairDecider] = [
        ExactTagDecider(),
        StringSimilarityDecider(0.8),
        UnitAwareDecider(0.8),
    ]
    assert [d.name for d in deciders] == ["d0", "d1", "d2"]
