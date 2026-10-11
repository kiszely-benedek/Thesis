"""The wording of the six held-out families and of the ten held-out rewordings (EXP-0006, ADR-0035).

Same rule as `templates.py`: each text is built in exactly one place. A held-out
*wording* asks the same question as a dev family (same answer, same evidence) in
different words. Wherever a question is about a unit, the literal word "unit"
stays in front of the id, so that anchor extraction (`qa/need/anchors.py`) reads
a reworded question the way it reads the dev wording.
"""

from __future__ import annotations

# --- the six held-out families ---------------------------------------------------------------


def first_meeting_point_text(first_tag: str, second_tag: str) -> str:
    """FIRST_MEETING_POINT: where the flows from two items first join."""
    return (
        f"Which item is the first place where the flow from {first_tag} "
        f"and the flow from {second_tag} come together?"
    )


def downstream_isolation_text(tag: str) -> str:
    """DOWNSTREAM_ISOLATION: the valves that cut `tag` off from everything downstream."""
    return f"To cut {tag} off from all downstream equipment, which valves must be closed?"


def valves_on_path_text(source_tag: str, target_tag: str) -> str:
    """VALVES_ON_PATH: how many valves lie between two items."""
    return f"How many valves does the flow pass between {source_tag} and {target_tag}?"


def feeding_units_text(unit_id: str) -> str:
    """FEEDING_UNITS: which units deliver flow directly into unit `unit_id`."""
    return f"Which units deliver process flow directly into unit {unit_id}?"


def units_reached_text(tag: str) -> str:
    """UNITS_REACHED: through how many other units the flow leaving `tag` passes."""
    return f"Through how many other units does the flow leaving {tag} eventually pass?"


def route_avoiding_text(source_tag: str, target_tag: str, avoided_tag: str) -> str:
    """ROUTE_AVOIDING: a yes/no question about a route that skips `avoided_tag`."""
    return f"Can flow get from {source_tag} to {target_tag} without passing through {avoided_tag}?"


# --- held-out wordings of ten dev families ---------------------------------------------------


def lookup_type_p1_text(tag: str) -> str:
    """LOOKUP_TYPE_P1."""
    return f"{tag}: what kind of equipment or component is it?"


def lookup_unit_p1_text(tag: str) -> str:
    """LOOKUP_UNIT_P1."""
    return f"{tag} belongs to which plant section?"


def neighbours_downstream_p1_text(tag: str) -> str:
    """NEIGHBOURS_DOWNSTREAM_P1."""
    return f"Name every item that is fed directly by {tag}."


def loop_actuated_valve_p1_text(loop_tag: str) -> str:
    """LOOP_ACTUATED_VALVE_P1."""
    return f"Control loop {loop_tag} drives which valve?"


def loop_measured_equipment_p1_text(loop_tag: str) -> str:
    """LOOP_MEASURED_EQUIPMENT_P1."""
    return f"The sensor of loop {loop_tag} sits on which piece of equipment?"


def flow_path_p1_text(source_tag: str, target_tag: str) -> str:
    """FLOW_PATH_P1."""
    return (
        "List, in flow order, the equipment and valves the process stream passes "
        f"from {source_tag} until it reaches {target_tag}."
    )


def upstream_isolation_p1_text(tag: str) -> str:
    """UPSTREAM_ISOLATION_P1."""
    return f"Before maintenance on {tag}, which valves have to be shut to stop every incoming flow?"


def cross_unit_p1_text(unit_id: str) -> str:
    """CROSS_UNIT_P1."""
    return f"Unit {unit_id} passes material straight on to which other units?"


def count_in_unit_p1_text(class_plural: str, unit_id: str) -> str:
    """COUNT_IN_UNIT_P1."""
    return f"What is the number of {class_plural} belonging to unit {unit_id}?"


def sheets_of_tag_p1_text(tag: str) -> str:
    """SHEETS_OF_TAG_P1."""
    return f"{tag} appears on which drawing sheets?"
