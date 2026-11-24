"""The wording of the scope X families that have a text of their own (design `v2t-b` §10 R9).

Same rule as `templates.py`: each text is built in exactly one place. The two OPEN_VALVES texts are
**twins** of the registered isolation texts: the same sentence with "normally open" added. The
frozen need classifier was written from the dev wording, so a twin gets the label of its registered
text and both arms route the pair identically (`tests/v2tb/test_scope_x_routing.py` checks it).
UPSTREAM_ISOLATION_X and DOWNSTREAM_ISOLATION_X reuse the registered texts unchanged.
"""

from __future__ import annotations


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
    """POSITION_OF_VALVE: the normal operating position of one valve."""
    return f"What is the normal operating position of valve {tag}?"
