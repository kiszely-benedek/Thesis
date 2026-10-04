"""The optional P&ID reading primer: a short block of general drawing conventions.

A primer is background knowledge about how P&IDs (piping and instrumentation
diagrams, the engineering drawings of a plant) are read -- not facts about the
plant being asked about. Prompt templates carry a `<<PRIMER>>` slot line;
`fill_primer_slot` turns it into the primer block, or removes it entirely so
that the prompt is byte-identical to one rendered before the primer existed.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

PRIMER_SLOT = "<<PRIMER>>"

_PRIMER_PATH = Path(__file__).parent / "prompts" / "primer_pid_v1.txt"

_PRIMER_HEADING = (
    "General P&ID reading conventions (background knowledge, not facts about this plant):"
)


@cache
def primer_text() -> str:
    """The primer file's text, without its trailing newline (like `legend_text`)."""
    return _PRIMER_PATH.read_text(encoding="utf-8").strip()


def primer_block() -> str:
    """The heading and primer text that replace the slot when the primer is on."""
    return f"{_PRIMER_HEADING}\n{primer_text()}"


def fill_primer_slot(template: str, *, primer: bool) -> str:
    """Replace the `<<PRIMER>>` slot with the primer block, or drop the slot and its blank line.

    Raises:
        ValueError: the template has no slot line, so the setting would be silently ignored.
    """
    slot_with_blank_line = f"{PRIMER_SLOT}\n\n"
    if slot_with_blank_line not in template:
        raise ValueError(f"expected the template to contain {PRIMER_SLOT!r} and a blank line")
    replacement = f"{primer_block()}\n\n" if primer else ""
    return template.replace(slot_with_blank_line, replacement, 1)
