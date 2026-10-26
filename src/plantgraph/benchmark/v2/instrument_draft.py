"""The building blocks the instrument templates share (design generator-v2-realism.md 4.3, 4.4).

An **instrument loop** is the chain a drawing shows as small circles joined by thin lines: a
*sensor* (a transmitter such as `LT-12005`) reads the process, a *bubble* (the controller
`LIC-12005` or an indicator) decides or shows, an *actuator* (drawn as part of the valve) moves
the valve `LV-12005`. All members of one loop carry the same number (`12005`), which is how a
reader pairs them. In DEXPI terms: sensor = `ProcessSignalGeneratingFunction` (PSGF), bubble =
`ProcessInstrumentationFunction` (PIF) or, for a controller, `ProcessControlFunction` (PCF),
actuator = `ActuatingFunction` (AF, a valve's) or `ActuatingElectricalFunction` (AEF, a machine's
start/stop or speed input).

`InstrumentDraft` adds those pieces to a `TrimDraft`. The helpers below it read a part out of a
plan and change the number of a loop-numbered part, because the trims number their valves and
flow elements themselves and the loop must take that number.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.plan_models import InstrumentSpec, LineItemSpec, LineSpec
from plantgraph.benchmark.v2.tags import ParsedTag, format_instrument_tag, parse_tag
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.graph.schema import NodeClass, Relation

_PIF = NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
_PCF = NodeClass.PROCESS_CONTROL_FUNCTION.value
_AF = NodeClass.ACTUATING_FUNCTION.value
_AEF = NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value


class InstrumentDraft(TrimDraft):
    """A `TrimDraft` that also creates bubbles, controllers and actuators, and wires them."""

    def tag(self, letters: str, number: int) -> str:
        """`LIC-12005`: the unit's tag with these letters and this loop number."""
        return format_instrument_tag(letters, self.ctx.unit_no, number)

    def new_number(self) -> int:
        """A fresh number from the unit's shared instrument counter."""
        return self.ctx.numbering.instrument_number()

    def bubble_node(self, tag: str, role: str, controller: bool = False) -> str:
        """A bubble (PIF), or a controller (PCF) when `controller`; it is its own loop's tag."""
        return self._instrument_node(_PCF if controller else _PIF, tag, tag, role)

    def actuator_node(self, loop_tag: str, role: str, electrical: bool = False) -> str:
        """An untagged actuator of the loop named `loop_tag`: a valve's AF or a machine's AEF."""
        return self._instrument_node(_AEF if electrical else _AF, None, loop_tag, role)

    def sensor_and_bubble(
        self,
        sensor_letters: str,
        bubble_letters: str,
        number: int,
        location_id: str,
        role: str,
        controller: bool = False,
    ) -> tuple[str, str]:
        """A sensor on `location_id` feeding a bubble; both are numbered `number`.

        Returns the two ids. The loop tag is the bubble's, so the sensor states it as its own.
        """
        bubble_tag = self.tag(bubble_letters, number)
        sensor = self.sensor(self.tag(sensor_letters, number), bubble_tag, location_id, role)
        bubble = self.bubble_node(bubble_tag, role, controller)
        self.feed(sensor, bubble)
        return sensor, bubble

    def feed(self, source_id: str, target_id: str) -> None:
        """A signal line from a sensor or bubble to a bubble or actuator."""
        self.link(Relation.SEND_SIGNAL_TO, source_id, target_id)

    def operate(self, actuator_id: str, target_id: str) -> None:
        """The actuator moves a valve body or drives a machine."""
        self.link(Relation.CONTROL, actuator_id, target_id)

    def _instrument_node(self, node_class: str, tag: str | None, loop_tag: str, role: str) -> str:
        spec = InstrumentSpec(
            node_id=self.ctx.numbering.node_id(),
            node_class=node_class,
            unit_no=self.ctx.unit_no,
            tag=tag,
            loop_tag=loop_tag,
            measured_variable=loop_tag[0],
        )
        self._instruments.append(spec)
        self._roles[spec.node_id] = role
        return spec.node_id


# ---- reading and changing the parts of a plan ----------------------------------------------------


def parts_of(plan: TrimPlan) -> dict[str, LineItemSpec]:
    """Every inline part of the plan by node id: the open `run` and the items of its lines."""
    found = {part.node_id: part for part in plan.run}
    for line in plan.lines:
        found.update({part.node_id: part for part in line.items})
    return found


def part_of(plan: TrimPlan, port: str) -> LineItemSpec:
    """The inline part a plan names as `port` (the control valve `body`, the XV `valve`)."""
    if port not in plan.ports:
        raise ValueError(f"expected a port in {sorted(plan.ports)}, got {port!r}")
    parts = parts_of(plan)
    node_id = plan.ports[port]
    if node_id not in parts:
        raise ValueError(f"port {port!r} names {node_id!r}, which is not an inline part")
    return parts[node_id]


def parsed_tag_of(part: LineItemSpec, unit_no: int) -> ParsedTag:
    """The parsed tag of a loop-numbered part, checked to belong to `unit_no`."""
    parsed = parse_tag(part.tag or "")
    if parsed is None or parsed.kind != "instrument":
        raise ValueError(
            f"expected a loop tag such as FV-12014 on {part.node_id!r}, got {part.tag!r}"
        )
    if parsed.unit != unit_no:
        raise ValueError(f"{part.tag!r} is in unit {parsed.unit}, expected unit {unit_no}")
    return parsed


def with_part_number(plan: TrimPlan, node_id: str, number: int) -> TrimPlan:
    """The plan with the part's tag renumbered (`FE-12009` becomes `FE-12014`), letters kept.

    The loop takes its number from its valve, so a flow element planned first gives its number
    up. The old number stays unused, which a real numbering sequence also shows.
    """
    part = parts_of(plan).get(node_id)
    if part is None:
        raise ValueError(f"expected an inline part of the plan, got {node_id!r}")
    parsed = parse_tag(part.tag or "")
    if parsed is None or parsed.kind != "instrument":
        raise ValueError(f"expected a loop tag such as FE-12014 on {node_id!r}, got {part.tag!r}")
    new_tag = format_instrument_tag(parsed.letters, parsed.unit, number)
    renamed = part.model_copy(update={"tag": new_tag})
    return plan.model_copy(
        update={
            "run": tuple(renamed if p.node_id == node_id else p for p in plan.run),
            "lines": tuple(_replace_in_line(line, renamed) for line in plan.lines),
        }
    )


def _replace_in_line(line: LineSpec, renamed: LineItemSpec) -> LineSpec:
    items = tuple(renamed if p.node_id == renamed.node_id else p for p in line.items)
    return line.model_copy(update={"items": items})


def node_with_role(plan: TrimPlan, role: str) -> str:
    """The id of the one node planned for `role`; raises when there is none or several."""
    ids = sorted(node_id for node_id, node_role in plan.roles.items() if node_role == role)
    if len(ids) != 1:
        raise ValueError(f"expected exactly one node with role {role!r}, found {ids}")
    return ids[0]
