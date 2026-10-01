"""The one phrasing of each question template (design `qa-system.md` §9, table).

Kept apart from the families because two families can share a phrasing: an
unanswerable question reuses the lookup, neighbours or flow-path text, only
with a tag that is not in the plant. Each text is built in exactly one place,
so the answerable and unanswerable versions can never drift apart.
"""

from __future__ import annotations


def lookup_type_text(tag: str) -> str:
    """The LOOKUP_TYPE question about `tag`."""
    return f"What type of item is {tag}?"


def neighbours_downstream_text(tag: str) -> str:
    """The NEIGHBOURS_DOWNSTREAM question about `tag`."""
    return f"Which equipment items and valves receive flow directly from {tag}?"


def flow_path_text(source_tag: str, target_tag: str) -> str:
    """The FLOW_PATH question from `source_tag` to `target_tag`."""
    return (
        f"Trace the process flow path from {source_tag} to {target_tag}. "
        "List every equipment item and valve in order."
    )


def upstream_isolation_text(tag: str) -> str:
    """The UPSTREAM_ISOLATION question about `tag`."""
    return f"To isolate {tag} from all upstream equipment, which valves must be closed?"


def cross_unit_text(unit_id: str) -> str:
    """The CROSS_UNIT question about unit `unit_id`."""
    return f"Which other units receive process flow directly from unit {unit_id}?"


def count_in_unit_text(class_plural: str, unit_id: str) -> str:
    """The COUNT_IN_UNIT question: how many `class_plural` are in unit `unit_id`."""
    return f"How many {class_plural} are in unit {unit_id}?"
