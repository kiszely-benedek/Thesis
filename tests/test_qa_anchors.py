"""Anchor extraction: tags (also spelled with a space or as a printed name) and `unit <id>`."""

from __future__ import annotations

from plantgraph.qa.anchors import extract_anchors
from qa_routing_toy import ToyCorpus


def _corpus() -> ToyCorpus:
    toy = ToyCorpus()
    toy.item("S1", "a", "P-101", unit_id="7")
    toy.item("S1", "b", "SV 104.01", unit_id="7")
    toy.item("S2", "c", "V-3", unit_id="8")
    toy.item("S2", "d", "TK-9", piping_component_name="66KL21")
    return toy


def test_tags_are_found_and_ordered_by_position_in_the_text() -> None:
    anchors = extract_anchors("Is V-3 upstream of p-101?", _corpus().view())

    assert [anchor.text for anchor in anchors.tags] == ["V-3", "p-101"]
    assert anchors.tags[0].position < anchors.tags[1].position
    assert anchors.tags[1].local_keys == {"S1:a"}


def test_a_tag_written_with_a_space_is_found_as_one_anchor() -> None:
    anchors = extract_anchors("What does SV 104.01 do. Also V-3.", _corpus().view())

    assert [anchor.text for anchor in anchors.tags] == ["SV 104.01", "V-3"]


def test_piping_component_name_is_an_anchor() -> None:
    anchors = extract_anchors("Where does 66KL21 lead?", _corpus().view())

    assert [anchor.local_keys for anchor in anchors.tags] == [frozenset({"S2:d"})]


def test_unit_anchor_matches_known_unit_only_and_is_not_also_a_tag() -> None:
    view = _corpus().view()

    anchors = extract_anchors("List everything in unit 7 and unit 99", view)

    assert [unit.unit_id for unit in anchors.units] == ["7"]
    assert anchors.tags == ()


def test_a_repeated_tag_is_one_anchor_and_no_anchor_is_reported_empty() -> None:
    view = _corpus().view()

    assert len(extract_anchors("P-101, then P-101 again", view).tags) == 1
    assert extract_anchors("How many pumps are there?", view).is_empty
