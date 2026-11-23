"""Writes the design-only valve attributes of a v2.2 plant into its pyDEXPI model (design 8).

Two attributes, both about how a valve is *operated*, not how it is piped:

- the **fail action** of an automatic valve goes to pyDEXPI's own `ControlledActuator.failAction`
  (fail open, fail close, fail retain position), on the actuator the builder already made;
- the **operating position** has no native field, so it is a `CustomStringAttribute` named
  `OperatingPosition` on the valve (a `PipingComponent` can own custom attributes; a custom
  attribute is not a custom class, so the S24 invariant still holds).

The graph adapter reads neither (`tests/v2/test_valve_positions_stripped.py` proves it): under
decision D1 = A the system under test never sees a valve's position or fail action.
"""

from __future__ import annotations

from collections.abc import Mapping

import pydexpi.dexpi_classes.pydantic_classes as dexpi

from plantgraph.benchmark.v2.config_v22 import FailAction

#: the custom attribute that carries the normal position of a valve
OPERATING_POSITION_ATTRIBUTE = "OperatingPosition"

_FAIL_ACTION_OF = {
    "FO": dexpi.FailActionClassification.FailOpen,
    "FC": dexpi.FailActionClassification.FailClose,
    "FL": dexpi.FailActionClassification.FailRetainPosition,
}


def annotate_valves(
    model: dexpi.DexpiModel,
    positions: Mapping[str, str],
    fail_actions: Mapping[str, FailAction],
) -> None:
    """Write `positions` (valve id -> position) and `fail_actions` (valve id -> action) in place.

    Raises:
        ValueError: an id names no valve of the model, or a valve has no actuator to carry its
            fail action.
    """
    _write_positions(model, positions)
    _write_fail_actions(model, fail_actions)


def _write_positions(model: dexpi.DexpiModel, positions: Mapping[str, str]) -> None:
    valves = _items_by_id(model)
    missing = sorted(set(positions) - set(valves))
    if missing:
        raise ValueError(f"expected every positioned valve in the model, missing {missing[:5]}")
    for node_id, position in positions.items():
        attribute = dexpi.CustomStringAttribute(
            id=f"{node_id}-pos", attributeName=OPERATING_POSITION_ATTRIBUTE, value=position
        )
        valves[node_id].customAttributes.append(attribute)


def _conceptual_model(model: dexpi.DexpiModel) -> dexpi.ConceptualModel:
    if model.conceptualModel is None:
        raise ValueError("expected a DEXPI model with a conceptual model, found none")
    return model.conceptualModel


def _items_by_id(model: dexpi.DexpiModel) -> dict[str, dexpi.PipingComponent]:
    """Every inline piping component by id (a tee, valve or flange; not an off-page connector)."""
    return {
        item.id: item
        for system in _conceptual_model(model).pipingNetworkSystems
        for segment in system.segments
        for item in segment.items
        if isinstance(item, dexpi.PipingComponent)
    }


def _write_fail_actions(model: dexpi.DexpiModel, fail_actions: Mapping[str, FailAction]) -> None:
    pending = dict(fail_actions)
    for system in _conceptual_model(model).actuatingSystems:
        reference = system.operatedValveReference
        valve_id = reference.valve.id if reference is not None and reference.valve else None
        if valve_id in pending and system.controlledActuator is not None:
            system.controlledActuator.failAction = _FAIL_ACTION_OF[pending.pop(valve_id)]
    if pending:
        raise ValueError(
            f"expected an actuating system with a controlled actuator for every valve with a "
            f"fail action, missing {sorted(pending)[:5]}"
        )
