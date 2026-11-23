"""API14C-SAC: every device of the API 14C checklist is drawn, or carries an omission code.

The checklist (`sac.py`) lists, per component kind, the safety devices that component should
have. For each component of a plant this check asks, item by item, whether the device is drawn
(`present`) or the item is excused by a **derived** condition read from the structure, a
**declared** convention or a **scope** exclusion (`hidden_state.py`). A device that is neither is a
violation. Items the generator neither draws nor can excuse are deferred rows of the registry
(`catalogue_deferred.py`) and are not looked at here. `report` counts every code used.
"""

from __future__ import annotations

from collections import deque

from plantgraph.benchmark.v2.hidden_state import (
    DECLARED_NATURAL_DRAFT,
    DECLARED_NO_SEPARATED_PHASES,
    DECLARED_SHUTOFF_RATED,
    DECLARED_UTILITY_HEADER,
    NO_SEPARATED_PHASE_ROLES,
    SCOPE_NON_HYDROCARBON,
    SCOPE_VACUUM_SERVICE,
    FluidClass,
)
from plantgraph.benchmark.v2.pressure_levels import PUMP_CLASSES
from plantgraph.benchmark.v2.protection import ENABLED_VALVE_ADDITIONS
from plantgraph.benchmark.v2.protection_scope import (
    a4_vessels,
    compressors,
    condensate_pots,
    filters,
    furnaces,
    tanks,
    vacuum_pumps,
)
from plantgraph.benchmark.v2.protection_switches import (
    DISCHARGE_TEE_ROLE,
    FUEL_PRESSURE_TEE_ROLE,
    HEATER_OUTLET_TEE_ROLE,
    SUCTION_TEE_ROLE,
    covered_by_downstream_psh,
    tee_of_unit,
)
from plantgraph.benchmark.v2.protection_valves import (
    EMERGENCY_VENT_ROLE,
    SUCTION_PSV_ROLE,
    TUBE_PSV_ROLE,
    tube_protected_by_other_psv,
)
from plantgraph.benchmark.v2.rules.checks_exchangers import nozzle_runs
from plantgraph.benchmark.v2.rules.checks_pressure import NOT_APPLICABLE
from plantgraph.benchmark.v2.rules.control_graph import EXCHANGER_CLASSES
from plantgraph.benchmark.v2.rules.registry import CheckResult
from plantgraph.benchmark.v2.rules.sac_tally import Tally
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.sac_structure import (
    Facts,
    facts_of_graph,
    has_level_loop,
    has_switch,
    reaches_safety_valve,
    valve_free_equipment,
)
from plantgraph.graph.schema import EQUIPMENT_CLASSES

_RULE = "API14C-SAC"
_DEFERRED_VALVE_BAND = "deferred:valve_band"
_PD_PUMPS = frozenset({"ReciprocatingPump", "RotaryPump"})
_BREATHER = "BreatherValve"
VENT_CLASSES = frozenset({_BREATHER, "VentilationDevice"})


def sac_facts(view: RuleView) -> Facts:
    """The plant as `Facts`, built once per view."""
    return view.cached("sac_facts", lambda: facts_of_graph(view.graph, view.piping, view.roles))


def downstream_parts(facts: Facts, start: str) -> set[str]:
    """Every pipe part downstream of `start`, branches included, up to the next equipment."""
    seen, queue = {start}, deque([start])
    while queue:
        for nxt in facts.piping.successors(queue.popleft()):
            if nxt not in seen and facts.node_class(nxt) not in EQUIPMENT_CLASSES:
                seen.add(nxt)
                queue.append(nxt)
    return seen - {start}


def has_downstream_role(facts: Facts, start: str, role: str) -> bool:
    """True when a part with `role` hangs on `start` over pipe alone."""
    return any(facts.role(n) == role for n in downstream_parts(facts, start))


def has_class_downstream(facts: Facts, start: str, classes: frozenset[str]) -> bool:
    """True when a part of one of `classes` hangs on `start` over pipe alone."""
    return any(facts.node_class(n) in classes for n in downstream_parts(facts, start))


# ---- A.4 pressure vessels ----------------------------------------------------------------------


def _check_vessel(facts: Facts, vessel: str, tally: Tally) -> None:
    # rule API14C-SAC: vessel PSH, PSV, LSH, LSL, TSH or an omission code (API 14C A-4.2 p.29)
    if has_switch(facts, vessel, "P", "H"):
        tally.present()
    elif covered_by_downstream_psh(facts, vessel):
        tally.excused("derived:A-4.2 a.4")
    else:
        tally.missing(vessel, "a PSH (A-4.2 a)")
    _item(tally, vessel, reaches_safety_valve(facts, vessel), "a PSV (A-4.2 c)")
    if has_switch(facts, vessel, "L", "H"):
        tally.present()
    elif facts.role(vessel) in NO_SEPARATED_PHASE_ROLES:
        tally.excused(DECLARED_NO_SEPARATED_PHASES)
    else:
        tally.missing(vessel, "an LSH (A-4.2 d)")
    if has_switch(facts, vessel, "L", "L"):
        tally.present()
    elif not has_level_loop(facts, vessel):
        tally.excused("derived:A-4.2 e.2")
    else:
        tally.missing(vessel, "an LSL (A-4.2 e)")
    if facts.node_class(vessel) == "ProcessColumn":  # a steam reboiler cannot overheat it
        tally.excused("declared:A-4.2 g.3 steam_limited")


def _check_filter(facts: Facts, filter_id: str, tally: Tally) -> None:
    """Filters (design 17.13 R7 f): a PSH, d.3, e.2, and a PSV or a deferred row."""
    _item(tally, filter_id, has_switch(facts, filter_id, "P", "H"), "a PSH (A-4.2 a)")
    if reaches_safety_valve(facts, filter_id):
        tally.present()
    else:
        tally.excused(_DEFERRED_VALVE_BAND)
    tally.excused(DECLARED_NO_SEPARATED_PHASES)
    tally.excused("derived:A-4.2 e.2")


def _item(tally: Tally, node: str, drawn: bool, what: str) -> None:
    if drawn:
        tally.present()
    else:
        tally.missing(node, what)


# ---- A.5 atmospheric vessels -------------------------------------------------------------------


def _check_tank(facts: Facts, tank: str, fluid: FluidClass | None, tally: Tally) -> None:
    if fluid is FluidClass.NON_FLAMMABLE:
        tally.excused(SCOPE_NON_HYDROCARBON)  # chemical storage is not covered (A.5.1 p.30)
        return
    # rule API14C-SAC: tank vent, relief device, LSH, LSL or an omission code (A-5.2 p.31)
    _item(tally, tank, has_class_downstream(facts, tank, VENT_CLASSES), "a vent (A-5.2 a)")
    if has_class_downstream(facts, tank, frozenset({_BREATHER})):
        tally.present()
    elif has_downstream_role(facts, tank, EMERGENCY_VENT_ROLE):
        tally.excused("derived:A-5.2 b.2")  # a second vent that can pass the vapour
    else:
        tally.missing(tank, "a pressure-vacuum relief device (A-5.2 b)")
    _item(tally, tank, has_switch(facts, tank, "L", "H"), "an LSH (A-5.2 c)")
    if has_switch(facts, tank, "L", "L"):
        tally.present()
    elif not has_level_loop(facts, tank):
        tally.excused("derived:A-5.2 d.3")
    else:
        tally.missing(tank, "an LSL (A-5.2 d)")


# ---- A.6 fired components and A.8 compressors --------------------------------------------------


def _check_furnace(facts: Facts, furnace: str, tally: Tally) -> None:
    # rule API14C-SAC: furnace TSH, PSH, BSL, PSV or an omission code (API 14C A-6.2 p.38)
    outlet = tee_of_unit(facts, furnace, HEATER_OUTLET_TEE_ROLE)
    fuel = tee_of_unit(facts, furnace, FUEL_PRESSURE_TEE_ROLE)
    _item(tally, furnace, has_switch(facts, outlet, "T", "H"), "a TSH (A-6.2 a)")
    _item(tally, furnace, has_switch(facts, fuel, "P", "H"), "a fuel PSH (A-6.2 e)")
    _item(tally, furnace, has_switch(facts, furnace, "B", "L"), "a BSL (A-6.2 g)")
    for _ in range(3):  # d (air PSL), f (fuel PSL), i (fan interlock): natural draft
        tally.excused(DECLARED_NATURAL_DRAFT)
    tally.excused("derived:A-6.2 h.2")  # the furnace heats the process feed, no hot-oil loop
    if reaches_safety_valve(facts, outlet):
        tally.present()
    elif tube_protected_by_other_psv(facts, furnace):
        tally.excused("derived:A-6.2 l.3")
    elif TUBE_PSV_ROLE not in ENABLED_VALVE_ADDITIONS:
        tally.excused(_DEFERRED_VALVE_BAND)
    else:
        tally.missing(furnace, "a tube PSV (A-6.2 l)")


def _check_compressor(facts: Facts, machine: str, tally: Tally) -> None:
    # rule API14C-SAC: compressor PSH, PSL, PSV, FSV, TSH (API 14C A-8.2 p.47)
    suction = tee_of_unit(facts, machine, SUCTION_TEE_ROLE)
    discharge = tee_of_unit(facts, machine, DISCHARGE_TEE_ROLE)
    for tee, variable, direction in (
        (suction, "P", "H"), (discharge, "P", "H"), (suction, "P", "L"),
        (discharge, "P", "L"), (discharge, "T", "H"),
    ):  # fmt: skip
        _item(tally, machine, has_switch(facts, tee, variable, direction), "a switch (A-8.2)")
    if reaches_safety_valve(facts, suction):
        tally.present()
    elif SUCTION_PSV_ROLE not in ENABLED_VALVE_ADDITIONS:
        tally.excused(_DEFERRED_VALVE_BAND)
    else:
        tally.missing(machine, "a suction PSV (A-8.2 e)")
    _item(tally, machine, reaches_safety_valve(facts, discharge), "a discharge PSV (A-8.2 f)")
    _item(
        tally, machine,
        has_downstream_role(facts, machine, "compressor_discharge_check"),
        "a final-discharge check valve (A-8.2 g)",
    )  # fmt: skip


# ---- A.7 pumps and A.10 exchangers -------------------------------------------------------------


def _check_pump(facts: Facts, pump: str, tally: Tally) -> None:
    # rule API14C-SAC: pump PSV and check valve, or an omission code (API 14C A-7.2 p.44)
    cls = facts.node_class(pump)
    if cls in _PD_PUMPS:
        _item(tally, pump, has_downstream_role(facts, pump, "pd_relief_valve"), "a PSV (A-7.2 f)")
    else:
        tally.excused(DECLARED_SHUTOFF_RATED)
    if has_downstream_role(facts, pump, "discharge_check"):
        tally.present()
    elif cls == "ReciprocatingPump":
        tally.excused("conflict:TOG192-RECIP-NO-CHECK")
    else:
        tally.missing(pump, "a check valve (A-7.2 g)")


def _check_exchanger(facts: Facts, exchanger: str, tally: Tally, utility_sides: int) -> None:
    # rule API14C-SAC: exchanger PSH per section, utility side declared (API 14C A-10.2 p.53)
    for _ in range(utility_sides):
        tally.excused(DECLARED_UTILITY_HEADER)
    targets = set(a4_vessels(facts)) | set(filters(facts))
    reached = valve_free_equipment(facts, exchanger) & targets
    if any(has_switch(facts, v, "P", "H") for v in reached):
        tally.excused("derived:A-10.2 a.4")
    else:
        tally.excused("deferred:process_section_psh")


def check_sac(view: RuleView) -> CheckResult:
    """API14C-SAC: each checklist device is drawn or excused by an omission code."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    facts, tally = sac_facts(view), Tally(_RULE)
    fluids = view.hidden.fluid_of_tank
    for vessel in a4_vessels(facts):
        _check_vessel(facts, vessel, tally)
    for filter_id in filters(facts):
        _check_filter(facts, filter_id, tally)
    for _ in condensate_pots(facts):
        tally.excused(SCOPE_NON_HYDROCARBON)  # steam service, outside A.4 (A.4.1 p.26)
    for tank in tanks(facts):
        _check_tank(facts, tank, fluids.get(tank), tally)
    for furnace in furnaces(facts):
        _check_furnace(facts, furnace, tally)
    for machine in compressors(facts):
        _check_compressor(facts, machine, tally)
    for _ in vacuum_pumps(facts):
        tally.excused(SCOPE_VACUUM_SERVICE)
    pumps = [n for n in facts.graph if facts.node_class(n) in PUMP_CLASSES and n in facts.roles]
    for pump in sorted(pumps):
        _check_pump(facts, pump, tally)
    return _with_exchangers(view, facts, tally)


def _with_exchangers(view: RuleView, facts: Facts, tally: Tally) -> CheckResult:
    exchangers = sorted(n for n in facts.graph if facts.node_class(n) in EXCHANGER_CLASSES)
    for exchanger in exchangers:
        sides = 1 if nozzle_runs(view, exchanger).utility else 0
        _check_exchanger(facts, exchanger, tally, sides)
    return tally.result()
