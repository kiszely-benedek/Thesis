"""The v2 builder's loop-tag check and the final sealing of its instruments.

Split out of `pydexpi_builder_v2.py` to keep that file short. Both functions only read the
builder's registries (they are passed in), so they are easy to follow on their own.
"""

from __future__ import annotations

import pydexpi.dexpi_classes.pydantic_classes as dexpi

from plantgraph.adapters.pydexpi_builder_v2_instruments import Instrument, create_carrier
from plantgraph.benchmark.v2.plan_models import InstrumentSpec
from plantgraph.graph.schema import NodeClass

#: the node classes of an actuator: a valve's (AF) or a machine's start/stop (AEF)
_ACTUATOR_CLASSES = frozenset(
    {NodeClass.ACTUATING_FUNCTION.value, NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value}
)


def check_loop_tag(source: InstrumentSpec, target: InstrumentSpec) -> None:
    """A sensor or actuator wired to a bubble must carry that bubble's tag as its loop tag.

    The adapter derives `loop_tag` from the bubble; the plan states it too, so a mismatch
    would make the DEXPI graph differ from the oracle without any error.
    """
    if source.node_class == NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
        bubble, member = target, source
    elif target.node_class in _ACTUATOR_CLASSES:
        bubble, member = source, target
    else:
        return  # bubble to bubble (a cascade): no single loop tag to compare
    if member.loop_tag != bubble.tag:
        raise ValueError(
            f"{member.node_id!r} is wired to {bubble.tag!r} but states loop tag "
            f"{member.loop_tag!r}; expected {bubble.tag!r}"
        )


def seal_instruments(
    model: dexpi.ConceptualModel,
    instruments: dict[str, Instrument],
    specs: dict[str, InstrumentSpec],
    sensors_with_bubble: set[str],
    signalled_actuators: set[str],
) -> None:
    """Wrap sensors that have no bubble; refuse sensors with no location, loose actuators."""
    for node_id, instrument in instruments.items():
        if isinstance(instrument, dexpi.ProcessSignalGeneratingFunction):
            _seal_sensor(model, node_id, instrument, specs[node_id], sensors_with_bubble)
        elif isinstance(instrument, dexpi.ActuatingFunction) and instrument.systems is None:
            raise ValueError(f"actuator {node_id!r} operates no valve; expected a control link")
        elif isinstance(instrument, dexpi.ActuatingElectricalFunction):
            _seal_electrical_actuator(node_id, instrument, signalled_actuators)


def _seal_electrical_actuator(
    node_id: str, actuator: dexpi.ActuatingElectricalFunction, signalled_actuators: set[str]
) -> None:
    """S19: an electrical actuator acts on one machine and is fed by at least one bubble."""
    if actuator.actuatingElectricalLocation is None:
        raise ValueError(
            f"electrical actuator {node_id!r} acts on no machine; expected a control link"
        )
    if node_id not in signalled_actuators:
        raise ValueError(
            f"electrical actuator {node_id!r} has no signal source; expected a send_signal_to link"
        )


def _seal_sensor(
    model: dexpi.ConceptualModel,
    node_id: str,
    sensor: dexpi.ProcessSignalGeneratingFunction,
    spec: InstrumentSpec,
    sensors_with_bubble: set[str],
) -> None:
    if sensor.sensingLocation is None:
        raise ValueError(f"sensor {node_id!r} senses nothing; expected a measured_by link")
    if node_id in sensors_with_bubble:
        return
    if spec.loop_tag != spec.tag:
        raise ValueError(
            f"local instrument {node_id!r} is its own loop: expected loop tag {spec.tag!r}, "
            f"got {spec.loop_tag!r}"
        )
    model.processInstrumentationFunctions.append(create_carrier(sensor))
    sensors_with_bubble.add(node_id)
