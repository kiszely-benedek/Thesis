"""Which drawing sheets to show next to an answer, found without the answer key.

A "sheet" is one drawing page of the plant. Two lists are built:
- answer sheets: the sheets of every tag the answer or the question names, so even a
  yes/no or count answer shows the sheets of the things it was asked about;
- read sheets: the sheets the answering agent says it read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from plantgraph.demo.app.models import SheetLink
from plantgraph.qa.models import AnswerType, AnswerValue, FinalAnswer
from plantgraph.qa.plant_api.item_graph import ItemGraph

#: A word made of letters, digits and `-_./`, starting and ending with a letter or digit.
_WORD = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_./-]*[A-Za-z0-9])?")

#: Answer types whose answer is a tag, or a list of tags, to look up directly.
_TAG_ANSWERS = (AnswerType.TAG, AnswerType.TAG_SET, AnswerType.TAG_PATH)


def tags_in_text(text: str, item_graph: ItemGraph) -> list[str]:
    """Words of `text` that name a plant item, matched as the plant API matches tags.

    A tag always contains a digit, so plain words are skipped before the lookup.
    """
    words = [word for word in _WORD.findall(text) if any(c.isdigit() for c in word)]
    return [word for word in words if item_graph.ids_for_tag(word)]


def answer_tags(
    question_text: str, answer_type: AnswerType, answer: FinalAnswer | None, item_graph: ItemGraph
) -> list[str]:
    """The tags to show sheets for: the question's, then the answer's, first-seen order."""
    tags = tags_in_text(question_text, item_graph)
    tags += _tags_in_answer(answer_type, None if answer is None else answer.answer, item_graph)
    return _without_repeats(tags)


def sheets_by_tag(tags: Iterable[str], item_graph: ItemGraph) -> dict[str, tuple[str, ...]]:
    """Sheet id -> the tags drawn on it, over every item each tag names; sheets sorted."""
    found: dict[str, list[str]] = {}
    for tag in tags:
        for item_id in item_graph.ids_for_tag(tag):
            for sheet in item_graph.item(item_id).sheets:
                found.setdefault(sheet, []).append(tag)
    return {sheet: tuple(_without_repeats(found[sheet])) for sheet in sorted(found)}


def answer_sheet_links(
    question_text: str,
    answer_type: AnswerType,
    answer: FinalAnswer | None,
    item_graph: ItemGraph,
    pages: Mapping[str, int],
) -> tuple[SheetLink, ...]:
    """Links for the answer sheets, in page order.

    Raises:
        ValueError: a sheet is missing from `pages` (the PDF does not match the plant).
    """
    tags = answer_tags(question_text, answer_type, answer, item_graph)
    by_sheet = sheets_by_tag(tags, item_graph)
    return _links(by_sheet, pages)


def read_sheet_links(
    trace_sheets: Iterable[str], pages: Mapping[str, int]
) -> tuple[SheetLink, ...]:
    """Links for the sheets the answering tier says it read; no tags attached."""
    return _links({sheet: () for sheet in trace_sheets}, pages)


def _links(
    by_sheet: Mapping[str, tuple[str, ...]], pages: Mapping[str, int]
) -> tuple[SheetLink, ...]:
    missing = sorted(sheet for sheet in by_sheet if sheet not in pages)
    if missing:
        raise ValueError(f"expected every sheet to be in the drawing index, missing {missing[:3]}")
    links = [SheetLink(sheet_id=s, page=pages[s], tags=tags) for s, tags in by_sheet.items()]
    return tuple(sorted(links, key=lambda link: (link.page, link.sheet_id)))


def _tags_in_answer(
    answer_type: AnswerType, value: AnswerValue, item_graph: ItemGraph
) -> list[str]:
    """Tags a typed answer names; other answer types (yes/no, count, ...) name none."""
    if answer_type in _TAG_ANSWERS:
        candidates = [value] if isinstance(value, str) else value
        if not isinstance(candidates, list):
            return []
        return [tag for tag in candidates if item_graph.ids_for_tag(tag)]
    if answer_type is AnswerType.FREE_TEXT and value is not None:
        text = " ".join(value) if isinstance(value, list) else str(value)
        return tags_in_text(text, item_graph)
    return []


def _without_repeats(tags: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(tags))
