"""Equipment objects for the v2 DEXPI builder: machines with motors, agitators, start/stop wiring.

Terms: an **electric motor** is not a separate machine on a P&ID but a small circle "M" drawn on
the pump or compressor it drives. DEXPI models it as a *component* of the machine, sub-tagged with
the machine's number (`P-1203A` has motor `PM-1203A`). pyDEXPI keeps it in the file but removes it
from the graph. An **agitator** is the stirrer inside a vessel; pyDEXPI links the two by a plain
reference (`vessel.agitator`). An **actuating electrical function** (AEF) is the machine's
start/stop (or speed) input: it points at a nozzle of the machine, which the graph folds into a
`control` edge from the AEF to the machine (design pid-vocabulary section 5.1).
"""

from __future__ import annotations

from typing import cast

import pydexpi.dexpi_classes.pydantic_classes as dexpi

from plantgraph.adapters.pydexpi_builder_v2_lines import dexpi_class_named
from plantgraph.benchmark.v2.plan_models import EquipmentSpec
from plantgraph.graph import schema
from plantgraph.graph.schema import NodeClass

#: label chains that name a machine a motor can drive (pump, compressor, agitator, rotary mixer)
_DRIVEN_FAMILIES = ("Pump", "Compressor", "Agitator", "RotaryMixer")
#: ejectors move fluid by a motive jet, not a motor, though they are pump / compressor family
_JET_CLASSES = frozenset({"EjectorPump", "AirEjector"})
#: machines whose motor drives a gear box (a speed reducer), drawn with the motor
_GEARED_CLASSES = frozenset({"Agitator", "RotaryMixer"})


def can_have_motor(node_class: str) -> bool:
    """True for a class a motor may drive: pump, compressor, agitator, rotary mixer."""
    if node_class in _JET_CLASSES:
        return False
    labels = schema.CLASS_SPECS[NodeClass(node_class)].labels
    return any(family in labels for family in _DRIVEN_FAMILIES)


def create_equipment(spec: EquipmentSpec, section: dexpi.PlantSection) -> dexpi.Equipment:
    """One machine or vessel, with its motor component (and gear box) when `spec.has_motor`."""
    if spec.has_motor and not can_have_motor(spec.node_class):
        raise ValueError(
            f"expected a pump, compressor, agitator or rotary mixer for has_motor on "
            f"{spec.node_id!r}, got {spec.node_class!r}"
        )
    prefix, _, sequence = spec.tag.partition("-")
    equipment = cast(
        dexpi.Equipment,
        dexpi_class_named(spec.node_class)(
            id=spec.node_id,
            tagName=spec.tag,
            tagNamePrefix=prefix,
            tagNameSequenceNumber=sequence,
            parentStructure=section,
        ),
    )
    if spec.has_motor:
        _add_motor(equipment, spec)
    return equipment


def motor_tag(machine_tag: str) -> str:
    """The motor's sub-tag: an `M` after the machine's letters (`P-1203A` gives `PM-1203A`)."""
    letters, dash, number = machine_tag.partition("-")
    if not dash or not number:
        raise ValueError(f"expected an equipment tag such as P-1203A, got {machine_tag!r}")
    return f"{letters}M-{number}"


def _add_motor(equipment: dexpi.Equipment, spec: EquipmentSpec) -> None:
    equipment.motors.append(
        dexpi.AlternatingCurrentMotorAsComponent(
            id=f"{spec.node_id}-motor", subTagName=motor_tag(spec.tag)
        )
    )
    if spec.node_class in _GEARED_CLASSES:
        equipment.gearBoxes.append(dexpi.GearBox(id=f"{spec.node_id}-gearbox"))


def attach_agitator(vessel: dexpi.Equipment, agitator: dexpi.Equipment) -> None:
    """Make `agitator` the stirrer of `vessel` (a vessel or heat exchanger has at most one)."""
    owner = type(vessel).__name__
    if owner not in schema.AGITATED_EQUIPMENT_CLASSES:
        raise ValueError(f"expected a vessel or heat exchanger to own an agitator, got {owner!r}")
    if not isinstance(agitator, dexpi.Agitator):
        raise ValueError(f"expected an Agitator as the stirrer, got {type(agitator).__name__!r}")
    if getattr(vessel, "agitator", None) is not None:
        raise ValueError(f"{vessel.id!r} already has an agitator")
    setattr(vessel, "agitator", agitator)  # noqa: B010 - the field exists on the vessel families only


def create_electrical_actuator(
    node_id: str, section: dexpi.PlantSection
) -> dexpi.ActuatingElectricalFunction:
    """An untagged start/stop or speed input; the machine it acts on is set by `attach_machine`."""
    return dexpi.ActuatingElectricalFunction(id=node_id, parentStructure=section)


def attach_machine(actuator: dexpi.ActuatingElectricalFunction, nozzle: dexpi.Nozzle) -> None:
    """Point the electrical actuator at a nozzle of its machine (its actuating location)."""
    if actuator.actuatingElectricalLocation is not None:
        raise ValueError(f"electrical actuator {actuator.id!r} already acts on a machine")
    actuator.actuatingElectricalLocation = nozzle
