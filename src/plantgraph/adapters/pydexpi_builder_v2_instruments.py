"""Instrument objects for the v2 DEXPI builder, and the signal wiring between them.

Terms (ISA-5.1 is the standard that names instruments by letters on the drawing):

- **PSGF** (`ProcessSignalGeneratingFunction`): the sensor, e.g. transmitter `FT-1014`.
- **PIF** (`ProcessInstrumentationFunction`): the bubble that does something with a signal, e.g.
  controller `FIC-1014` or hand switch `HS-1015`. A PCF (`ProcessControlFunction`) is a
  controller PIF.
- **AEF** (`ActuatingElectricalFunction`): the start/stop or speed input of a motor-driven machine,
  the electrical counterpart of an AF (`pydexpi_builder_v2_equipment.py`).
- **AF** (`ActuatingFunction`): the actuator of a valve. It carries no tag of its own; the valve's
  tag stands for it (ADR-0044).
- **Actuating system**: pyDEXPI's record of what an AF operates, plus its small hardware: for an
  on-off valve a **solenoid** (the electric pilot, sub-tag `XY-...`), for a control valve a
  plain actuator. pyDEXPI removes them from the graph; they stay in the DEXPI file.
"""

from __future__ import annotations

from typing import cast

import pydexpi.dexpi_classes.pydantic_classes as dexpi
from pydexpi.toolkits import instrumentation_toolkit

from plantgraph.adapters.pydexpi_builder_v2_equipment import create_electrical_actuator
from plantgraph.adapters.pydexpi_loop_tags import BUBBLE_CLASSES
from plantgraph.benchmark.v2.plan_models import InstrumentSpec
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import NodeClass

Instrument = (
    dexpi.ProcessSignalGeneratingFunction
    | dexpi.ProcessInstrumentationFunction
    | dexpi.ActuatingFunction
    | dexpi.ActuatingElectricalFunction
)


def create_instrument(spec: InstrumentSpec, section: dexpi.PlantSection) -> Instrument:
    """One sensor, bubble or actuator, in its unit; the tag fills the fields the adapter reads."""
    if spec.node_class == NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
        return _create_sensor(spec, section)
    if spec.node_class in BUBBLE_CLASSES:
        return _create_bubble(spec, section)
    if spec.node_class == NodeClass.ACTUATING_FUNCTION.value:
        return _create_actuator(spec, section)
    if spec.node_class == NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value:
        return _create_electrical_actuator(spec, section)
    raise ValueError(
        f"expected ProcessSignalGeneratingFunction, ProcessInstrumentationFunction, "
        f"ProcessControlFunction, ActuatingFunction or ActuatingElectricalFunction for "
        f"instrument {spec.node_id!r}, "
        f"got {spec.node_class!r}"
    )


def _create_sensor(spec: InstrumentSpec, section: dexpi.PlantSection) -> Instrument:
    tag = _require_tag(spec)
    return dexpi.ProcessSignalGeneratingFunction(
        id=spec.node_id, processSignalGeneratingFunctionNumber=tag, parentStructure=section
    )


def _create_bubble(spec: InstrumentSpec, section: dexpi.PlantSection) -> Instrument:
    tag = _require_tag(spec)
    parsed = parse_tag(tag)
    if parsed is None or parsed.kind != "instrument":
        raise ValueError(
            f"expected an instrument tag such as FIC-1014 on {spec.node_id!r}, got {tag!r}"
        )
    if spec.loop_tag != tag:
        raise ValueError(
            f"a bubble is its loop's tag: {spec.node_id!r} has {tag!r}, loop {spec.loop_tag!r}"
        )
    bubble_class = cast(type[dexpi.ProcessInstrumentationFunction], getattr(dexpi, spec.node_class))
    # same slots as v1 and the real-file import: first letter / the other letters / the digits
    return bubble_class(
        id=spec.node_id,
        processInstrumentationFunctionCategory=parsed.first,
        processInstrumentationFunctionModifier=parsed.functions,
        processInstrumentationFunctionNumber=tag.partition("-")[2],
        parentStructure=section,
    )


def _create_actuator(spec: InstrumentSpec, section: dexpi.PlantSection) -> Instrument:
    if spec.tag is not None:
        raise ValueError(f"an actuator carries no tag; {spec.node_id!r} has {spec.tag!r}")
    return dexpi.ActuatingFunction(id=spec.node_id, parentStructure=section)


def _create_electrical_actuator(spec: InstrumentSpec, section: dexpi.PlantSection) -> Instrument:
    if spec.tag is not None:
        raise ValueError(
            f"an electrical actuator carries no tag; {spec.node_id!r} has {spec.tag!r}"
        )
    return create_electrical_actuator(spec.node_id, section)


def _require_tag(spec: InstrumentSpec) -> str:
    if spec.tag is None:
        raise ValueError(f"expected a tag on {spec.node_class} {spec.node_id!r}, got None")
    return spec.tag


# --- wiring ----------------------------------------------------------------------------------


def connect_signal(source: Instrument, target: Instrument) -> None:
    """Join two instruments by the signal line their kinds call for.

    A sensor feeds a bubble (measuring line); a bubble feeds an actuator or another bubble
    (signal line); an actuator here may be an AEF, a machine's start/stop. Anything else has no
    meaning on a P&ID.
    """
    line_id = f"{source.id}-to-{target.id}"
    if isinstance(source, dexpi.ProcessSignalGeneratingFunction) and _is_bubble(target):
        instrumentation_toolkit.add_signal_generating_function_to_instrumentation_function(
            cast(dexpi.ProcessInstrumentationFunction, target),
            source,
            dexpi.MeasuringLineFunction(id=line_id),
        )
    elif _is_bubble(source) and isinstance(
        target, dexpi.ActuatingFunction | dexpi.ActuatingElectricalFunction
    ):
        instrumentation_toolkit.add_actuating_function_to_instrumentation_function(
            cast(dexpi.ProcessInstrumentationFunction, source),
            target,
            dexpi.SignalLineFunction(id=line_id),
        )
    elif _is_bubble(source) and _is_bubble(target):
        instrumentation_toolkit.connect_instrumentation_functions(
            cast(dexpi.ProcessInstrumentationFunction, source),
            cast(dexpi.ProcessInstrumentationFunction, target),
            dexpi.SignalLineFunction(id=line_id),
        )
    else:
        raise ValueError(
            f"no signal runs from {type(source).__name__} {source.id!r} "
            f"to {type(target).__name__} {target.id!r}"
        )


def _is_bubble(instrument: Instrument) -> bool:
    return isinstance(instrument, dexpi.ProcessInstrumentationFunction)


def create_carrier(
    sensor: dexpi.ProcessSignalGeneratingFunction,
) -> dexpi.ProcessInstrumentationFunction:
    """An untagged bubble that only holds a sensor with no bubble of its own (a local gauge).

    pyDEXPI reaches a sensor only through a bubble's list, so a gauge printed as one tagged
    sensor (design convention I-2) needs this wrapper. It has no tag fields, which is how the
    adapter recognises it and leaves it out of the graph.
    """
    carrier = dexpi.ProcessInstrumentationFunction(
        id=f"{sensor.id}-carrier", parentStructure=sensor.parentStructure
    )
    instrumentation_toolkit.add_signal_generating_function_to_instrumentation_function(
        carrier, sensor, dexpi.MeasuringLineFunction(id=f"{sensor.id}-carrier-ml")
    )
    return carrier


def create_actuating_system(
    actuator: dexpi.ActuatingFunction, valve: dexpi.OperatedValve, valve_class: str
) -> dexpi.ActuatingSystem:
    """The record of which valve `actuator` operates, with the valve's solenoid (on-off valves)."""
    valve_tag = valve.pipingComponentNumber
    if valve_tag is None:
        raise ValueError(f"valve {valve.id!r} needs a tag: its actuating system takes the number")
    kind = _valve_kind(valve_class, valve_tag)
    if kind is ItemKind.ON_OFF_VALVE:
        hardware = _on_off_hardware(actuator, valve_tag)
    else:
        # no `Positioner`: unlike `ControlledActuator`, pyDEXPI's abstraction keeps it as a
        # node of its own, which would show up as a dropped class (measured in V2-T4)
        hardware = {"controlledActuator": dexpi.ControlledActuator(id=f"{actuator.id}-ca")}
    system = dexpi.ActuatingSystem(
        id=f"{actuator.id}-as",
        actuatingSystemNumber=valve_tag,
        operatedValveReference=dexpi.OperatedValveReference(id=f"{actuator.id}-ov", valve=valve),
        **hardware,
    )
    actuator.systems = system
    return system


def _valve_kind(valve_class: str, valve_tag: str) -> ItemKind:
    parsed = parse_tag(valve_tag)
    if parsed is None:
        raise ValueError(f"expected a valve tag such as FV-1014 or XV-1030, got {valve_tag!r}")
    return item_kind(valve_class, parsed.letters)


def _on_off_hardware(actuator: dexpi.ActuatingFunction, valve_tag: str) -> dict[str, object]:
    """The solenoid of an on-off valve: tag `XV-1030` gives solenoid `XY-1030` (`YV` gives `YY`)."""
    letters, _, number = valve_tag.partition("-")
    solenoid = dexpi.ControlledActuator(
        id=f"{actuator.id}-ca", subTagName=f"{letters[0]}Y-{number}"
    )
    return {"controlledActuator": solenoid}
