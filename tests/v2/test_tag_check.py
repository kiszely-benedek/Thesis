"""The free tag existence check: tag-like words, the lookup query and the note."""

from __future__ import annotations

from plantgraph.qa.tag_check import (
    MAX_TAGS,
    format_tag_note,
    split_found_missing,
    tag_like_words,
    tag_lookup_query,
)


def test_tag_like_words_keeps_tags_once_in_order_and_skips_plain_words() -> None:
    text = "Is P-4501C upstream of TIC-49-1 or fed by SV-104.01, P-4501C in a 4-inch CO2-rich line?"

    assert tag_like_words(text) == ["P-4501C", "TIC-49-1", "SV-104.01"]


def test_a_question_without_a_tag_has_no_tag_like_words() -> None:
    assert tag_like_words("How many pumps are there in unit 7?") == []


def test_the_number_of_looked_up_tags_is_capped() -> None:
    text = " ".join(f"P-{n}" for n in range(MAX_TAGS + 5))

    assert len(tag_like_words(text)) == MAX_TAGS


def test_the_lookup_query_names_every_tag_and_matches_the_printed_valve_name_too() -> None:
    query = tag_lookup_query(["P-1", "V-2"])

    assert query.count("['P-1', 'V-2']") == 2
    assert "n.tag IN" in query and "n.piping_component_name IN" in query


def test_found_and_missing_tags_are_split_by_tag_or_name() -> None:
    rows = [{"tag": "P-1", "name": None}, {"tag": None, "name": "V-2"}]

    assert split_found_missing(["P-1", "V-2", "X-9"], rows) == (["P-1", "V-2"], ["X-9"])


def test_the_note_lists_both_groups_and_is_empty_without_tags() -> None:
    note = format_tag_note(["P-1"], ["X-9"])

    assert "- found: P-1" in note and "- not found: X-9" in note
    assert format_tag_note([], []) == ""


def test_the_note_says_none_for_an_empty_group() -> None:
    assert "- found: none" in format_tag_note([], ["X-9"])
