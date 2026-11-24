"""The P&ID reading primer of a B run: A's primer plus a paragraph on positions and untagged valves.

Background knowledge, not facts about the plant: what the position codes mean, and how an engineer
names a manual valve that prints no tag (Toghraei, TOG p.114).
"""

from __future__ import annotations

from plantgraph.qa.primer import PRIMER_SLOT, primer_block

#: Draft wording (design 3); the three tuning rounds may reword it.
POSITION_PRIMER = """\
Valve positions: a valve's normal position is NO (normally open), NC (normally closed), LO or LC
(locked open or closed) or CSO or CSC (car-sealed open or closed). A valve with no position drawn is
normally open. In some drawing sets manual valves carry no tag. Name such a valve by its class, the
line number of its pipe and the nearest tagged item along the flow (the line number may change on
the way), with the side of that item it sits on. The nearest tagged item is the first one met when
walking from the valve itself, not the item a question is about. To find a valve described this way,
start at the named tagged item and walk to the first valve of that class whose pipe has that line
number on the named side."""


def primer_block_b() -> str:
    """A's heading and primer text, followed by the B paragraph."""
    return f"{primer_block()}\n{POSITION_PRIMER}"


def fill_primer_slot_b(template: str, *, primer: bool) -> str:
    """Replace the `<<PRIMER>>` slot with the B primer block, or drop the slot and its blank line.

    Raises:
        ValueError: the template has no slot line, so the setting would be silently ignored.
    """
    slot_with_blank_line = f"{PRIMER_SLOT}\n\n"
    if slot_with_blank_line not in template:
        raise ValueError(f"expected the template to contain {PRIMER_SLOT!r} and a blank line")
    replacement = f"{primer_block_b()}\n\n" if primer else ""
    return template.replace(slot_with_blank_line, replacement, 1)
