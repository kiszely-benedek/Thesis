"""Three protection rules read from the checklist structure: two levels, tank vents, exchangers.

- **API14C-3.4-TWO-LEVELS** (API 14C 3.4 b p.7): a pressure vessel has two independent levels of
  protection, a relief valve and a sensor trip (a switch), or a checklist omission code.
- **TOG236-TANK-EMERGENCY-VENT** (Toghraei p.236): an atmospheric tank has a normal vent and an
  emergency vent that opens if the normal one cannot pass the vapour.
- **TOG207-HX-PSD-BOTH-SIDES** (Toghraei p.207): an exchanger side that can be shut in at every
  nozzle has a pressure safety device (PSD), or the pressure model excuses it.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.hidden_state import SCOPE_NON_HYDROCARBON, FluidClass
from plantgraph.benchmark.v2.protection_scope import a4_vessels, condensate_pots, filters, tanks
from plantgraph.benchmark.v2.protection_switches import covered_by_downstream_psh
from plantgraph.benchmark.v2.protection_valves import EMERGENCY_VENT_ROLE
from plantgraph.benchmark.v2.rules.checks_exchangers import nozzle_runs
from plantgraph.benchmark.v2.rules.checks_pressure import NOT_APPLICABLE
from plantgraph.benchmark.v2.rules.checks_sac import (
    VENT_CLASSES,
    has_class_downstream,
    has_downstream_role,
    sac_facts,
)
from plantgraph.benchmark.v2.rules.control_graph import EXCHANGER_CLASSES
from plantgraph.benchmark.v2.rules.registry import CheckResult
from plantgraph.benchmark.v2.rules.sac_tally import Tally
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.sac_structure import (
    Facts,
    is_isolating,
    reaches_safety_valve,
    switch_letters_on,
    valve_free_equipment,
)


def check_two_levels(view: RuleView) -> CheckResult:
    """API14C-3.4-TWO-LEVELS: every A.4 vessel has a relief valve and a switch (or is covered)."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule API14C-3.4-TWO-LEVELS: a PSV plus a sensor trip on a vessel (API 14C §3.4 b p.7)
    facts, tally = sac_facts(view), Tally("API14C-3.4-TWO-LEVELS")
    filter_ids = set(filters(facts))
    for vessel in [*a4_vessels(facts), *sorted(filter_ids)]:
        if not reaches_safety_valve(facts, vessel):
            if vessel in filter_ids:  # a filter's own PSV is a deferred row (design 17.13 R7 f)
                tally.excused("deferred:valve_band")
            else:
                tally.missing(vessel, "a relief valve (first level)")
        elif switch_letters_on(facts, vessel):
            tally.present()
        elif covered_by_downstream_psh(facts, vessel):
            tally.excused("derived:A-4.2 a.4")  # the switch of a downstream vessel trips for it
        else:
            tally.missing(vessel, "a sensor trip (second level)")
    for _ in condensate_pots(facts):
        tally.excused(SCOPE_NON_HYDROCARBON)
    return tally.result()


def check_tank_emergency_vent(view: RuleView) -> CheckResult:
    """TOG236-TANK-EMERGENCY-VENT: a normal vent and an emergency vent on every hydrocarbon tank."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    facts, tally = sac_facts(view), Tally("TOG236-TANK-EMERGENCY-VENT")
    fluids = view.hidden.fluid_of_tank
    for tank in tanks(facts):
        if fluids.get(tank) is FluidClass.NON_FLAMMABLE:
            tally.excused(SCOPE_NON_HYDROCARBON)  # a chemical tank, outside A.5 (A.5.1 p.30)
        elif not has_class_downstream(facts, tank, VENT_CLASSES):
            tally.missing(tank, "a normal vent")
        elif not has_downstream_role(facts, tank, EMERGENCY_VENT_ROLE):
            tally.missing(tank, "an emergency vent")
        else:
            tally.present()
    return tally.result()


def _blocked_in(view: RuleView, runs: list[list[str]]) -> bool:
    """True when the side has nozzles and a block valve stands on every one of them."""
    facts = sac_facts(view)
    return bool(runs) and all(any(is_isolating(facts, n) for n in run) for run in runs)


def _has_psd(facts: Facts, exchanger: str) -> str | None:
    """The reason an exchanger needs no more protection, or None: a PSD hangs on it or a vessel."""
    if reaches_safety_valve(facts, exchanger):
        return "relief_present"
    targets = set(a4_vessels(facts)) | set(filters(facts))
    reached = valve_free_equipment(facts, exchanger) & targets
    if any(reaches_safety_valve(facts, vessel) for vessel in reached):
        return "derived:A-10.2 c.4"  # a valve-free vessel with its own PSV relieves it
    return None


def check_exchanger_psd(view: RuleView) -> CheckResult:
    """TOG207-HX-PSD-BOTH-SIDES: a side that can be shut in has a PSD or an excusing code."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule TOG207-HX-PSD-BOTH-SIDES: a shut-in exchanger side has a PSD (Toghraei 2019 p.207)
    facts, tally = sac_facts(view), Tally("TOG207-HX-PSD-BOTH-SIDES")
    exchangers = sorted(n for n in facts.graph if facts.node_class(n) in EXCHANGER_CLASSES)
    for exchanger in exchangers:
        runs = nozzle_runs(view, exchanger)
        sides = {
            "process": [*runs.process_in, *runs.process_out],
            "utility": runs.utility,
        }
        reason = _has_psd(facts, exchanger)
        for side, side_runs in sides.items():
            if not side_runs:
                continue
            if not _blocked_in(view, side_runs):
                tally.excused("side_not_blockable")
            elif reason is not None:
                tally.excused(reason)
            else:
                tally.missing(exchanger, f"a pressure safety device on the {side} side")
    return tally.result()
