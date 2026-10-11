"""Find the checklist's tags in a free-text answer (pure text work, no I/O).

A *tag* is the short identifier printed on a drawing for an item, such as `HV4750.01` for a valve.
Tags match with spaces and case ignored, and only as whole tokens: `H1007` is not found inside
`H10070`. The result is advisory; a person decides whether the answer is correct.
"""

from __future__ import annotations

import re

from plantgraph.qa.exp0001.ex01_models import Ex01ChecklistItem, TagHits


def _pattern(tag: str) -> re.Pattern[str]:
    """The tag with optional whitespace between its characters, delimited by non-alphanumerics."""
    body = r"\s*".join(re.escape(char) for char in tag if not char.isspace())
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def first_position(text: str, tag: str, aliases: list[str] | None = None) -> int | None:
    """Where the tag (or one of its aliases) first appears in `text`; `None` when absent."""
    positions = [
        match.start()
        for spelling in [tag, *(aliases or [])]
        if (match := _pattern(spelling).search(text)) is not None
    ]
    return min(positions) if positions else None


def check_tags(text: str, item: Ex01ChecklistItem) -> TagHits:
    """Which required tags `text` contains, which forbidden ones it mentions, and their order."""
    positions = {
        tag: first_position(text, tag, item.aliases.get(tag)) for tag in item.required_tags
    }
    found = [tag for tag in item.required_tags if positions[tag] is not None]
    missing = [tag for tag in item.required_tags if positions[tag] is None]
    forbidden = [tag for tag in item.forbidden_tags if first_position(text, tag) is not None]
    order_ok = _in_order([positions[tag] for tag in found]) if item.ordered else None
    return TagHits(found=found, missing=missing, forbidden_present=forbidden, order_ok=order_ok)


def _in_order(positions: list[int | None]) -> bool:
    """True when the positions (of tags found, in checklist order) strictly increase."""
    numbers = [p for p in positions if p is not None]
    return all(earlier < later for earlier, later in zip(numbers, numbers[1:], strict=False))
