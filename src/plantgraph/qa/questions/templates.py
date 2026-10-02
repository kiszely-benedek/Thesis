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


def sheets_of_tag_text(tag: str) -> str:
    """The SHEETS_OF_TAG question about `tag`."""
    return f"On which sheets is {tag} drawn?"


def cross_unit_text(unit_id: str) -> str:
    """The CROSS_UNIT question about unit `unit_id`."""
    return f"Which other units receive process flow directly from unit {unit_id}?"


def count_in_unit_text(class_plural: str, unit_id: str) -> str:
    """The COUNT_IN_UNIT question: how many `class_plural` are in unit `unit_id`."""
    return f"How many {class_plural} are in unit {unit_id}?"


# The six dev-new families (design `question-aware-retrieval.md` section 8.2).


def connected_text(source_tag: str, target_tag: str) -> str:
    """The CONNECTED yes/no question: can flow get from `source_tag` to `target_tag`."""
    return f"Can process flow reach {target_tag} from {source_tag}?"


def downstream_in_unit_text(unit_id: str, tag: str) -> str:
    """The DOWNSTREAM_IN_UNIT question: what in unit `unit_id` is fed, even indirectly, by `tag`."""
    return (
        f"Which equipment items and valves in unit {unit_id} receive flow from {tag}, "
        "directly or indirectly?"
    )


def instruments_of_item_text(tag: str) -> str:
    """The INSTRUMENTS_OF_ITEM question about equipment item `tag`."""
    return f"Which instruments measure {tag}?"


def upstream_sources_text(tag: str) -> str:
    """The UPSTREAM_SOURCES question about `tag`."""
    return f"Which source items, with nothing flowing into them, ultimately feed {tag}?"


def same_unit_text(first_tag: str, second_tag: str) -> str:
    """The SAME_UNIT yes/no question about two items."""
    return f"Are {first_tag} and {second_tag} in the same unit?"


def loops_near_item_text(tag: str) -> str:
    """The LOOPS_NEAR_ITEM question about `tag`."""
    return f"Which control loops act on valves directly connected to {tag}?"
