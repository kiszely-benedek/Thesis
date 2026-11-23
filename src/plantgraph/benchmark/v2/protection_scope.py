"""Which tanks the API 14C atmospheric-vessel items cover (design 17.13 R7 i).

A **farm** is a group of storage tanks (pattern `U4`). A farm drawn non-flammable holds chemicals
the drawing gives only a plain `VentilationDevice`: API 14C A.5.1 (p.30) leaves chemical storage
out, so the plant declares those tanks `FluidClass.NON_FLAMMABLE` and every other tank
hydrocarbon. The farm's flag overrides the plant-wide hydrocarbon declaration for that farm only.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.hidden_state import FluidClass
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.pressure_levels import COMPRESSOR_CLASSES, VACUUM_PUMP_ROLE
from plantgraph.benchmark.v2.sac_structure import Facts
from plantgraph.graph.schema import NodeClass

#: API 14C A.4 pressure vessels (hydrocarbon); a steam condensate pot is outside A.4 (A.4.1 p.26)
A4_VESSEL_CLASSES = frozenset(
    {
        NodeClass.PRESSURE_VESSEL.value,
        NodeClass.PROCESS_COLUMN.value,
        NodeClass.GRAVITATIONAL_SEPARATOR.value,
        NodeClass.SCRUBBING_SEPARATOR.value,
    }
)
#: filters count as A.4 vessels (API p.28 names fuel-gas filters; design 17.13 R7 f)
FILTER_CLASSES = frozenset({NodeClass.LIQUID_FILTER.value, NodeClass.GAS_FILTER.value})
CONDENSATE_POT_ROLE = "condensate_drain_pot"

FARM_PATTERN = "U4"
_PLAIN_VENT_ROLE = "tank_ventilation_device"
_TANK = NodeClass.TANK.value


def tank_fluids(instance: PatternInstance) -> dict[str, FluidClass]:
    """The declared fluid class of every tank of one pattern instance."""
    plan = instance.plan
    tanks = [e.node_id for e in plan.equipment if e.node_class == _TANK]
    plain = {line.src_id for line in plan.lines if _ends_in_plain_vent(line, plan.roles)}
    farm = instance.pattern == FARM_PATTERN
    return {
        tank: FluidClass.NON_FLAMMABLE if farm and tank in plain else FluidClass.HYDROCARBON
        for tank in tanks
    }


def _ends_in_plain_vent(line: LineSpec, roles: dict[str, str]) -> bool:
    return bool(line.items) and roles.get(line.items[-1].node_id) == _PLAIN_VENT_ROLE


# ---- which nodes of a plant each SAC table covers ----------------------------------------------


def _of_class(facts: Facts, classes: frozenset[str]) -> list[str]:
    return sorted(n for n in facts.graph if facts.node_class(n) in classes and n in facts.roles)


def a4_vessels(facts: Facts) -> list[str]:
    """The A.4 pressure vessels: every vessel class but the condensate pots."""
    return [n for n in _of_class(facts, A4_VESSEL_CLASSES) if facts.role(n) != CONDENSATE_POT_ROLE]


def filters(facts: Facts) -> list[str]:
    """The liquid and gas filters, which count as A.4 vessels."""
    return _of_class(facts, FILTER_CLASSES)


def condensate_pots(facts: Facts) -> list[str]:
    """The steam condensate pots: scope `non_hydrocarbon`."""
    return [n for n in _of_class(facts, A4_VESSEL_CLASSES) if facts.role(n) == CONDENSATE_POT_ROLE]


def tanks(facts: Facts) -> list[str]:
    """Every atmospheric tank (A.5 or, for a non-flammable farm, out of scope)."""
    return _of_class(facts, frozenset({_TANK}))


def compressors(facts: Facts) -> list[str]:
    """The A.8 compressors: a vacuum liquid-ring pump is out of scope (`scope:vacuum_service`)."""
    found = _of_class(facts, COMPRESSOR_CLASSES)
    return [n for n in found if facts.role(n) != VACUUM_PUMP_ROLE]


def vacuum_pumps(facts: Facts) -> list[str]:
    """The liquid-ring vacuum pumps: compressors by class, outside A.8 (design 17.13 R7 g)."""
    return [n for n in _of_class(facts, COMPRESSOR_CLASSES) if facts.role(n) == VACUUM_PUMP_ROLE]


def furnaces(facts: Facts) -> list[str]:
    """The fired heaters (A.6)."""
    return _of_class(facts, frozenset({NodeClass.FURNACE.value}))
