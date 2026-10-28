"""A free check of whether the tags a question names exist in the database (V2T, ADR-0061).

A *tag* is the short identifier printed next to a symbol on a drawing, for example `P-4501C`
for a pump. A question about a tag the plant does not have should be answered "not present", but
a Cypher query on a missing tag just returns no rows, which looks like "nothing found".
This check tells the answering model which named tags exist. It reads the question text only
(no model call), and looks the tags up with one small query.

`anchors.py` cannot serve here: it keeps only tags that *exist* in a view, so it cannot see the
missing ones. This module finds *tag-like* words first, then asks the database.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from typing import Any

#: Letters, a dash, a digit, then any dash- or dot-joined letters and digits: P-4501C, TIC-49-1,
#: SV-104.01. Plain words, "CO2-rich" and "4-inch" do not match. A heuristic by design: a word
#: that merely looks like a tag is reported as "not found", which is also true.
_TAG_LIKE = re.compile(r"\b[A-Z]{1,6}-\d[A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*\b")

#: A question names a handful of tags; more than this are not looked up (a runaway input).
MAX_TAGS = 20

#: The check query is trivial; a longer time means something is wrong with the database.
TAG_CHECK_TIMEOUT_S = 10.0


def tag_like_words(question_text: str) -> list[str]:
    """The tag-like words of the question, each once, in the order they appear."""
    seen: dict[str, None] = {}
    for match in _TAG_LIKE.finditer(question_text):
        seen.setdefault(match.group(), None)
    return list(seen)[:MAX_TAGS]


def tag_lookup_query(tags: Collection[str]) -> str:
    """One query returning the tag (and the printed name of an imported valve) of each match.

    The tags come from `tag_like_words`, whose pattern allows no quote or backslash, so
    writing them into the text cannot break out of the string literals.
    """
    literals = ", ".join(f"'{tag}'" for tag in tags)
    return (
        f"MATCH (n:PlantItem) WHERE n.tag IN [{literals}] "
        f"OR n.piping_component_name IN [{literals}] "
        "RETURN DISTINCT n.tag AS tag, n.piping_component_name AS name"
    )


def split_found_missing(tags: list[str], rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Which of `tags` the lookup rows contain (as `tag` or `name`), and which it does not."""
    stored = {value for row in rows for value in (row.get("tag"), row.get("name"))}
    found = [tag for tag in tags if tag in stored]
    missing = [tag for tag in tags if tag not in stored]
    return found, missing


def format_tag_note(found: list[str], missing: list[str]) -> str:
    """The note prepended to the context; empty when the question names no tag-like word."""
    if not found and not missing:
        return ""
    return (
        "Tags named in the question, checked against the database "
        "(a tag that is not found matches no item):\n"
        f"- found: {', '.join(found) or 'none'}\n"
        f"- not found: {', '.join(missing) or 'none'}"
    )
