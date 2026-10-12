"""Plain-Hungarian topic of a question family, so the example list needs no family code.

A family is one kind of question the generator asks ("is A connected to B", "which valves
isolate X"). The visitor sees only the topic heading the family belongs to.
"""

from __future__ import annotations

from plantgraph.qa.models import QuestionFamily as F

ROUTES = "Útvonalak az üzemen át"
NEIGHBOURS = "Előtte és utána: szomszédok, források, elzárás"
INSTRUMENTS = "Műszerek és szabályozókörök"
ITEMS = "Tételek, egységek és rajzlapok"

#: Headings in the order the page lists them.
TOPIC_ORDER: tuple[str, ...] = (ROUTES, NEIGHBOURS, INSTRUMENTS, ITEMS)

_TOPIC_OF_FAMILY: dict[F, str] = {
    F.CONNECTED: ROUTES,
    F.FLOW_PATH: ROUTES,
    F.NO_PATH: ROUTES,
    F.CROSS_UNIT: ROUTES,
    F.FIRST_MEETING_POINT: ROUTES,
    F.VALVES_ON_PATH: ROUTES,
    F.ROUTE_AVOIDING: ROUTES,
    F.NEIGHBOURS_DOWNSTREAM: NEIGHBOURS,
    F.UPSTREAM_SOURCES: NEIGHBOURS,
    F.UPSTREAM_ISOLATION: NEIGHBOURS,
    F.DOWNSTREAM_ISOLATION: NEIGHBOURS,
    F.DOWNSTREAM_IN_UNIT: NEIGHBOURS,
    F.LOOP_ACTUATED_VALVE: INSTRUMENTS,
    F.LOOP_MEASURED_EQUIPMENT: INSTRUMENTS,
    F.INSTRUMENTS_OF_ITEM: INSTRUMENTS,
    F.LOOPS_NEAR_ITEM: INSTRUMENTS,
    F.LOOKUP_TYPE: ITEMS,
    F.LOOKUP_UNIT: ITEMS,
    F.COUNT_IN_UNIT: ITEMS,
    F.SAME_UNIT: ITEMS,
    F.SHEETS_OF_TAG: ITEMS,
    F.UNANSWERABLE_TAG: ITEMS,
    F.FEEDING_UNITS: ITEMS,
    F.UNITS_REACHED: ITEMS,
}


def topic_of(family: F) -> str:
    """The topic heading of a family.

    Raises:
        KeyError: the family has no topic yet (a new family was added without one).
    """
    if family not in _TOPIC_OF_FAMILY:
        raise KeyError(f"expected a topic for family {family.value}, found none in topics.py")
    return _TOPIC_OF_FAMILY[family]
