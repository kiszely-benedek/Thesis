"""The wording of the scope X families that have a text of their own (design `v2t-b` §10 R9).

Same rule as `templates.py`: each text is built in exactly one place. The two OPEN_VALVES texts are
**twins** of the registered isolation texts: the same sentence with "normally open" added. The
frozen need classifier was written from the dev wording, so a twin gets the label of its registered
text and both arms route the pair identically (`tests/v2tb/test_scope_x_routing.py` checks it).
UPSTREAM_ISOLATION_X and DOWNSTREAM_ISOLATION_X reuse the registered texts unchanged.
"""

from __future__ import annotations

import re

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def open_valves_upstream_text(tag: str) -> str:
    """OPEN_VALVES_TO_ISOLATE (dev): twin of `templates.upstream_isolation_text`."""
    return (
        f"To isolate {tag} from all upstream equipment, which normally open valves must be closed?"
    )


def open_valves_downstream_text(tag: str) -> str:
    """OPEN_VALVES_TO_ISOLATE_DOWNSTREAM (held-out): twin of `downstream_isolation_text`."""
    return (
        f"To cut {tag} off from all downstream equipment, "
        "which normally open valves must be closed?"
    )


def position_of_valve_text(tag: str) -> str:
    """POSITION_OF_VALVE, tag form: the normal operating position of one tagged valve."""
    return f"What is the normal operating position of valve {tag}?"


def class_words(class_name: str) -> str:
    """A CamelCase node class as plain words: "GateValve" becomes "gate valve"."""
    return _CAMEL_BOUNDARY.sub(" ", class_name).lower()


def position_of_described_valve_text(
    class_name: str, line_number: str, side: str, next_to: str
) -> str:
    """POSITION_OF_VALVE, descriptor form: names an untagged valve by line and nearest tagged item.

    "On the {side} side of" is deliberate: "downstream of" alone would route like a reach
    question (`need/rules.py`), and "just" would be false when untagged fittings sit between.
    The words hold neither the answer nor a role word (design `v2t-b` §10 R11, P1).

    Args:
        class_name: the valve's node class, e.g. "GateValve".
        line_number: the line number as the plant prints it (inch mark and all).
        side: "upstream" or "downstream", where the valve sits relative to `next_to`.
        next_to: the tag of the nearest tagged item on that side.
    """
    return (
        f"What is the normal operating position of the {class_words(class_name)} "
        f"on line {line_number}, on the {side} side of {next_to}?"
    )
