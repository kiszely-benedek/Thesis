"""The switch-plus-alarm devices API 14C asks for, as a list of what is missing (design 17.13 R7 d).

A **switch** senses a limit (`PSHH`: pressure, switch, high-high) and an alarm bubble (`PAHH`)
shows it; the shut-in action at the source is not drawn (design 4.9 #13, deferred). The same
questions decide whether a device is *needed* (here, by the generator pass) and whether it is
*present or excused* (by the rule check), so both call the functions of this module.

Each `Switch` is one device to draw: where it sits, and its sensor and alarm letters.
"""

from __future__ import annotations

from dataclasses import dataclass

from plantgraph.benchmark.v2.hidden_state import NO_SEPARATED_PHASE_ROLES, FluidClass
from plantgraph.benchmark.v2.protection_scope import (
    a4_vessels,
    compressors,
    filters,
    furnaces,
    tanks,
)
from plantgraph.benchmark.v2.sac_structure import (
    Facts,
    has_level_loop,
    has_switch,
    nodes_with_role,
    valve_free_equipment,
)

SUCTION_TEE_ROLE = "compressor_suction_tee"
DISCHARGE_TEE_ROLE = "discharge_psv_tee"
HEATER_OUTLET_TEE_ROLE = "heater_outlet_tee"
#: the tee between the pressure valve and the temperature valve of the fuel line (A.6.3.3 p.33)
FUEL_PRESSURE_TEE_ROLE = "fuel_gas_psh_tee"
_COLUMN_CLASS = "ProcessColumn"


@dataclass(frozen=True)
class Switch:
    """One switch and its alarm to draw: `location` is the node the sensor senses."""

    location: str
    sensor: str  # `PSHH`
    alarm: str  # `PAHH`


def _switch(location: str, variable: str, direction: str) -> Switch:
    both = direction + direction
    return Switch(location, f"{variable}S{both}", f"{variable}A{both}")


def covered_by_downstream_psh(facts: Facts, vessel: str) -> bool:
    """SAC A-4.2 a.4: a valve-free route leads to a vessel or filter that has a PSH of its own."""
    targets = set(a4_vessels(facts)) | set(filters(facts))
    downstream = valve_free_equipment(facts, vessel) & targets
    return any(has_switch(facts, other, "P", "H") for other in downstream)


def _vessels_needing_psh(facts: Facts) -> list[str]:
    """The vessels that get a PSHH: those no downstream PSH covers (a.4), the terminal one first.

    A column whose overhead runs valve-free through a condenser to its reflux drum is covered once
    the drum has a switch, so the drum is the one that gets it. Of two vessels that reach each
    other, the lower id gets it.
    """
    vessels = a4_vessels(facts)
    drawn = {v for v in vessels if has_switch(facts, v, "P", "H")}
    pending = [v for v in vessels if v not in drawn]
    reach = {v: valve_free_equipment(facts, v) & set(vessels) for v in pending}
    added: list[str] = []
    while pending:
        pending = [v for v in pending if not reach[v] & (drawn | set(added))]
        terminal = [v for v in pending if not reach[v] & set(pending)] or pending[:1]
        if terminal:
            added.append(terminal[0])
            pending.remove(terminal[0])
    return added


def vessel_switches(facts: Facts) -> list[Switch]:
    """SAC A-4.2 a, d, e and the filter PSH: the missing switches of the pressure vessels."""
    # rule API14C-SAC: vessel PSH, LSH, LSL unless an omission code holds (API 14C A-4.2 p.29)
    wanted = [_switch(v, "P", "H") for v in _vessels_needing_psh(facts)]
    wanted += [_switch(f, "P", "H") for f in filters(facts) if not has_switch(facts, f, "P", "H")]
    for vessel in a4_vessels(facts):
        if needs_level_high(facts, vessel):
            wanted.append(_switch(vessel, "L", "H"))
        if needs_level_low(facts, vessel):
            wanted.append(_switch(vessel, "L", "L"))
    return wanted


def needs_level_high(facts: Facts, vessel: str) -> bool:
    """A-4.2 d: no LSH yet, and d.3 (no separated phases) does not excuse the vessel."""
    if has_switch(facts, vessel, "L", "H"):
        return False
    return facts.role(vessel) not in NO_SEPARATED_PHASE_ROLES


def needs_level_low(facts: Facts, vessel: str) -> bool:
    """A-4.2 e: no LSL yet, and e.2 (no level loop on the vessel) does not excuse it."""
    return not has_switch(facts, vessel, "L", "L") and has_level_loop(facts, vessel)


def tank_switches(facts: Facts, fluids: dict[str, FluidClass]) -> list[Switch]:
    """SAC A-5.2 c: an LSHH on each hydrocarbon tank that has none (the additive tanks)."""
    return [
        _switch(t, "L", "H")
        for t in tanks(facts)
        if fluids.get(t) is not FluidClass.NON_FLAMMABLE and not has_switch(facts, t, "L", "H")
    ]


def compressor_switches(facts: Facts) -> list[Switch]:
    """SAC A-8.2 a-d, h: PSHH and PSLL on suction and discharge, TSHH on the discharge."""
    wanted: list[Switch] = []
    for tee_role, items in (
        (SUCTION_TEE_ROLE, (("P", "H"), ("P", "L"))),
        (DISCHARGE_TEE_ROLE, (("P", "H"), ("P", "L"), ("T", "H"))),
    ):
        for compressor in compressors(facts):
            tee = tee_of_unit(facts, compressor, tee_role)
            wanted += [_switch(tee, v, d) for v, d in items if not has_switch(facts, tee, v, d)]
    return wanted


def furnace_switches(facts: Facts) -> list[Switch]:
    """SAC A-6.2 a, e: TSHH on the heater outlet tee and PSHH on the fuel-gas tee."""
    wanted: list[Switch] = []
    for furnace in furnaces(facts):
        outlet = tee_of_unit(facts, furnace, HEATER_OUTLET_TEE_ROLE)
        fuel = tee_of_unit(facts, furnace, FUEL_PRESSURE_TEE_ROLE)
        if not has_switch(facts, outlet, "T", "H"):
            wanted.append(_switch(outlet, "T", "H"))
        if not has_switch(facts, fuel, "P", "H"):
            wanted.append(_switch(fuel, "P", "H"))
    return wanted


def _unit_of(facts: Facts, node: str) -> str | None:
    unit = facts.graph.nodes[node].get("unit_id")
    return None if unit is None else str(unit)


def tee_of_unit(facts: Facts, machine: str, role: str) -> str:
    """The one node with `role` in the machine's unit (a unit holds one compressor or furnace)."""
    unit = _unit_of(facts, machine)
    same_unit = (unit, None)  # a node of a bare unit plan has no unit id: every node qualifies
    found = [
        n for n in nodes_with_role(facts, [role]) if unit is None or _unit_of(facts, n) in same_unit
    ]
    if len(found) != 1:
        raise ValueError(f"expected one node with role {role!r} for {machine!r}, found {found}")
    return found[0]


def switch_additions(facts: Facts, fluids: dict[str, FluidClass]) -> list[Switch]:
    """Every switch a unit still needs, in a fixed order: vessels, tanks, compressors, furnaces."""
    return [
        *vessel_switches(facts),
        *tank_switches(facts, fluids),
        *compressor_switches(facts),
        *furnace_switches(facts),
    ]
