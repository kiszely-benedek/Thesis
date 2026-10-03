"""Anchor extraction: which items and units does a question name? (`qa-system.md` §7 step 1).

An *anchor* is a thing the question names outright: an equipment **tag**
(the short label printed next to a symbol on a P&ID, e.g. `P-101`) or a
**unit** (a group of equipment operated together, written `unit 7`). The
Hierarchical strategy starts from the anchors and routes between them.

Only the question text and the view are read. A tag may be printed with a
space (`SV 104.01`, as in ChatP&ID) or be an imported valve's
`piping_component_name`; both are found because lookup goes through
`GraphView.find_by_tag`, which normalizes case and whitespace.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.graph_view import GraphView, ItemRecord
from plantgraph.qa.scoring import normalize_scalar

# Letters and digits, joined by single "-" or "." (so "P-101" and "104.01" are one
# token, while the full stop that ends a sentence is not part of the token).
_TOKEN = r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*"
_TOKEN_RE = re.compile(_TOKEN)
_UNIT_RE = re.compile(rf"\bunit\s+({_TOKEN})", re.IGNORECASE)


class TagAnchor(BaseModel):
    """A tag the question names, with every occurrence of it (home and reference sheets)."""

    model_config = ConfigDict(frozen=True)

    #: The tag as written in the question, e.g. `"SV 104.01"`.
    text: str
    #: Character offset of the first character in the question; anchors are ordered by it.
    position: int
    occurrences: tuple[ItemRecord, ...]

    @property
    def local_keys(self) -> frozenset[str]:
        """The local key of every occurrence."""
        return frozenset(item.local_key for item in self.occurrences)

    @property
    def sheet_ids(self) -> frozenset[str]:
        """Every sheet the tag is drawn on."""
        return frozenset(item.sheet_id for item in self.occurrences)


class UnitAnchor(BaseModel):
    """A unit the question names as `unit <id>`; `unit_id` is the id as the view spells it."""

    model_config = ConfigDict(frozen=True)

    unit_id: str
    position: int


class Anchors(BaseModel):
    """Everything the question names, each kind ordered by first position in the text."""

    model_config = ConfigDict(frozen=True)

    tags: tuple[TagAnchor, ...] = ()
    units: tuple[UnitAnchor, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when nothing was found, which triggers the router fallback (design D5)."""
        return not self.tags and not self.units


def extract_anchors(question_text: str, view: GraphView) -> Anchors:
    """Find the tags and units `question_text` names; only visible view data is consulted."""
    units, unit_spans = _find_units(question_text, view)
    tokens = [
        match
        for match in _TOKEN_RE.finditer(question_text)
        if not _inside_any(match.start(), unit_spans)
    ]
    return Anchors(tags=tuple(_find_tags(tokens, view)), units=tuple(units))


def mask_anchors(question_text: str, anchors: Anchors) -> str:
    """Replace each tag by `<TAG>` and each unit id by `<UNIT>`, so wording can be matched alone.

    `unit 7` becomes `unit <UNIT>`: the word stays, only the id is hidden.
    """
    spans = [(tag.position, _tag_end(question_text, tag), "<TAG>") for tag in anchors.tags]
    spans += [_unit_id_span(question_text, unit) for unit in anchors.units]
    masked = question_text
    for start, end, placeholder in sorted(spans, reverse=True):  # right to left keeps offsets valid
        masked = masked[:start] + placeholder + masked[end:]
    return masked


def _tag_end(question_text: str, tag: TagAnchor) -> int:
    """End offset of a tag; a two-token tag may be spaced differently from its normalized text."""
    pattern = r"\s+".join(re.escape(part) for part in tag.text.split())
    match = re.compile(pattern).match(question_text, tag.position)
    return match.end() if match else tag.position + len(tag.text)


def _unit_id_span(question_text: str, unit: UnitAnchor) -> tuple[int, int, str]:
    match = _UNIT_RE.match(question_text, unit.position)
    if match is None:
        raise ValueError(f"expected 'unit <id>' at offset {unit.position}, found a different text")
    return match.start(1), match.end(1), "<UNIT>"


def _find_units(question_text: str, view: GraphView) -> tuple[list[UnitAnchor], list[range]]:
    """Units named as `unit <id>`, plus the text spans they occupy (so tag lookup skips them)."""
    known = {normalize_scalar(unit_id): unit_id for unit_id in view.unit_ids()}
    units: dict[str, UnitAnchor] = {}
    spans: list[range] = []
    for match in _UNIT_RE.finditer(question_text):
        unit_id = known.get(normalize_scalar(match.group(1)))
        if unit_id is None:
            continue
        spans.append(range(match.start(), match.end()))
        units.setdefault(unit_id, UnitAnchor(unit_id=unit_id, position=match.start()))
    return list(units.values()), spans


def _inside_any(offset: int, spans: list[range]) -> bool:
    return any(offset in span for span in spans)


def _find_tags(tokens: list[re.Match[str]], view: GraphView) -> Iterator[TagAnchor]:
    """Walk the tokens left to right; a two-token tag (`SV 104.01`) wins over its first token."""
    seen: set[str] = set()
    index = 0
    while index < len(tokens):
        anchor, consumed = _tag_at(tokens, index, view)
        index += consumed
        if anchor is None:
            continue
        key = normalize_scalar(anchor.text)
        if key not in seen:  # the same tag mentioned twice is one anchor, at its first position
            seen.add(key)
            yield anchor


def _tag_at(
    tokens: list[re.Match[str]], index: int, view: GraphView
) -> tuple[TagAnchor | None, int]:
    """The anchor starting at `tokens[index]` and how many tokens it used (1 when none)."""
    first = tokens[index]
    if index + 1 < len(tokens):
        pair_text = f"{first.group()} {tokens[index + 1].group()}"
        pair_anchor = _lookup(pair_text, first.start(), view)
        if pair_anchor is not None:
            return pair_anchor, 2
    return _lookup(first.group(), first.start(), view), 1


def _lookup(text: str, position: int, view: GraphView) -> TagAnchor | None:
    occurrences = view.find_by_tag(text)
    if not occurrences:
        return None
    return TagAnchor(text=text, position=position, occurrences=tuple(occurrences))
