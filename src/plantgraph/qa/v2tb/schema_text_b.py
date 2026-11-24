"""The schema text of a B corpus: A's text, plus the valve-position paragraph when the store has it.

The paragraph is added only when the corpus's own `LoadPlan` holds `operating_position`, so the
text of an A corpus (positions stripped) stays the one V2T-A2 was given, byte for byte.
"""

from __future__ import annotations

from plantgraph.qa.schema_text import build_schema_text
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.store.neo4j_plan import LoadPlan

_PROPERTIES_PREFIX = "Item properties (present only when the drawing shows them): "

#: Draft wording (design 3); the three tuning rounds may reword it.
POSITION_PARAGRAPH = """\
Valves may carry operating_position: NO normally open, NC normally closed, LO/LC locked open/closed,
CSO/CSC car-sealed open/closed. A valve without the property is normally open. Manual valves in
some areas carry no tag. Such a valve is named by its class, its line_number and the tagged item it
sits next to (see the answer rules)."""


def plan_holds_positions(plan: LoadPlan) -> bool:
    """Whether any node row of the plan carries `operating_position`."""
    return any(
        OPERATING_POSITION in row["props"]
        for statement in plan.node_statements
        for row in _rows(statement.parameters)
    )


def _rows(parameters: dict[str, object]) -> list[dict[str, dict[str, object]]]:
    rows = parameters.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"expected a node statement with a list of rows, found {parameters!r:.80}")
    return rows


def build_schema_text_b(plan: LoadPlan) -> str:
    """A's schema text for `plan`, with the position property and paragraph when the plan has it.

    Raises:
        ValueError: A's text has no item-property line to extend (the format changed).
    """
    text = build_schema_text(plan)
    if not plan_holds_positions(plan):
        return text
    return _with_property(text) + "\n\n" + POSITION_PARAGRAPH


def _with_property(text: str) -> str:
    lines = text.split("\n")
    for position, line in enumerate(lines):
        if line.startswith(_PROPERTIES_PREFIX):
            names = line.removeprefix(_PROPERTIES_PREFIX).split(", ")
            lines[position] = _PROPERTIES_PREFIX + ", ".join(sorted({*names, OPERATING_POSITION}))
            return "\n".join(lines)
    raise ValueError(f"expected a line starting {_PROPERTIES_PREFIX!r} in the schema text")
