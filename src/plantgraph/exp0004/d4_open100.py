"""The OPEN100 strings as text-only cards, for an illustration in the thesis (never a metric).

OPEN100 is a real, published nuclear-plant P&ID set. These tag spellings were read off it
(`open100-annotation.md`); a text-only card has no class, sheet or neighbours, so the model has
only the two spellings. No gold label is stored: the outputs are quoted, not scored.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# (A, B): the pump drawn as RCS-PU-102A is listed as RC-P102A in its own schedule; the others
# test a spare, a different item with a similar tag, and the unverified CND/FWS heater pair.
OPEN100_TAG_PAIRS: tuple[tuple[str, str], ...] = (
    ("RCS-PU-102A", "RC-P102A"),
    ("RCS-PU-102A", "RCS-PU-102B"),
    ("RC-P102A", "RC-P100-X001"),
    ("CND-HTR-161", "FWS-HTR-161"),
)


class Open100Answer(BaseModel):
    """The model's answer to one text-only card."""

    model_config = ConfigDict(frozen=True)

    first_tag: str
    second_tag: str
    card: str
    answer_text: str
    same_item: bool | None
    reason: str | None


def text_only_card(first_tag: str, second_tag: str) -> str:
    """A card in the pair-card layout (design 5.1) with only the two tags."""
    return (
        f'Occurrence A: tag "{first_tag}"; class not given (text only)\n'
        f'Occurrence B: tag "{second_tag}"; class not given (text only)'
    )
