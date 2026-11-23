"""Rules of design 4.4 to 4.7: compressors, exchangers and heaters, control, protection (20)."""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_support import api, lip1, tog, wired
from plantgraph.benchmark.v2.rules.registry import HandbookRule, RuleKind
from plantgraph.benchmark.v2.rules.sac import SAC_EXCEPTION_CODES

COMPRESSORS = (
    HandbookRule(
        rule_id="TOG319-ANTISURGE-DYNAMIC",
        title="Anti-surge only on dynamic compressors",
        statement="Anti-surge recycle only on dynamic (centrifugal) compressors, not on "
        "positive-displacement gas movers.",
        sources=(tog("p.319"),),
        kind=RuleKind.FORBID,
        check=wired("check_antisurge_dynamic", "checks_compressors"),
    ),
    HandbookRule(
        rule_id="TOG316-PD-COMP-CAPACITY",
        title="Capacity control of a positive-displacement compressor",
        statement="Capacity comes from a spillback line with a capacity loop, or a "
        "variable-speed drive; never discharge throttling (Table 15.10).",
        sources=(tog("p.316"), tog("p.317")),
        kind=RuleKind.PLACE,
        check=wired("check_pd_compressor_capacity", "checks_compressors"),
    ),
    HandbookRule(
        rule_id="API14C-A8-FSV",
        title="Check valve on the compressor final discharge",
        statement="A check valve on the compressor's final discharge.",
        sources=(api("A.8.3.2 p.45"), tog("p.84")),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_compressor_discharge_check", "checks_compressors"),
    ),
    HandbookRule(
        rule_id="API14C-A8-PSV",
        title="PSV on the compressor discharge",
        statement="A pressure safety valve (PSV) on the compressor discharge.",
        sources=(api("A.8.2.2.1 p.45"),),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_compressor_discharge_psv", "checks_compressors"),
    ),
)

EXCHANGERS = (
    HandbookRule(
        rule_id="TOG207-HX-NO-ISOLATION",
        title="No isolation valves around an exchanger",
        statement="Isolation at an exchanger is company policy (p.207). v2.2 follows the policy "
        "with no isolation on the process side: no exchanger has blocks on all of its process "
        "inlets and outlets, and none has a hand bypass around its process side, unless it has an "
        "installed spare or a cleaning-in-place system. Utility-side valves are outside the rule.",
        sources=(tog("p.207"),),
        kind=RuleKind.FORBID,
        since="v2.1",
        exception_codes=("has_spare", "cleaning_system", "utility_side_block"),
        check=wired("check_hx_no_isolation", "checks_exchangers"),
    ),
    HandbookRule(
        rule_id="TOG320-HX-NONTARGET",
        title="Temperature control moves the non-target stream",
        statement="The temperature controller moves the non-target stream: directly on a "
        "utility, by a bypass on a process stream.",
        sources=(tog("p.320–321"),),
        kind=RuleKind.PLANT,
        check=wired("check_hx_nontarget", "checks_exchangers"),
    ),
    HandbookRule(
        rule_id="TOG322-HX-BYPASS-VARIANT",
        title="Exchanger bypass variants",
        statement="A bypass temperature valve alone, or control valves on both the main and "
        "the bypass branch.",
        sources=(tog("p.322"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        declared_parameters=("handbook.exchanger_bypass_weights",),
        check=wired("check_hx_bypass_variant", "checks_exchangers"),
    ),
    HandbookRule(
        rule_id="TOG326-STEAM-CONDENSATE",
        title="Steam heater condensate handling",
        statement="Steam heater condensate: a trap, a trap station, or a condensate pot with "
        "level control.",
        sources=(tog("p.326–327"),),
        kind=RuleKind.ALTERNATIVE,
        since="v2.1",
        sampling_unit="item",
        declared_parameters=("trims.condensate_mode_weights",),
        check=wired("check_steam_condensate", "checks_exchangers"),
    ),
    HandbookRule(
        rule_id="TOG214-FUEL-SWITCHING-VALVES",
        title="Fuel line switching valves",
        statement="One switching valve, or two in series, on the fuel line; each valve gets "
        "its own actuator and number.",
        sources=(tog("p.214"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        declared_parameters=("handbook.fuel_switching_weights",),
        check=wired("check_fuel_switching_valves", "checks_alternatives"),
    ),
)

CONTROL = (
    HandbookRule(
        rule_id="TOG271-ONE-CV-LIQUID",
        title="One control valve in series on a liquid line",
        statement="At most one control valve in series on a liquid-filled line between two "
        "containers; a flooded vessel counts as pipe. The valves of a temperature split around "
        "an exchanger (bypass valve, or the TOG322 pair) keep the total flow and do not count.",
        sources=(tog("p.271"), tog("p.321–322")),
        kind=RuleKind.PLANT,
        exception_codes=("split_valve",),
        check=wired("check_one_cv_liquid", "checks_control"),
    ),
    HandbookRule(
        rule_id="TOG267-FE-UPSTREAM-FV",
        title="Flow element upstream of its valve",
        statement="A flow element sits upstream of the flow valve of its loop.",
        sources=(tog("p.267"),),
        kind=RuleKind.PLANT,
        check=wired("check_fe_upstream_fv", "checks_control"),
    ),
    HandbookRule(
        rule_id="TOG295-INVENTORY-ONCE",
        title="One loop per inventory",
        statement="A non-flooded liquid container has exactly one level loop (an atmospheric tank "
        "with a level transmitter may have none); a container a process-gas line touches, or "
        "whose function depends on pressure, exactly one pressure loop, any other at most one; a "
        "flooded container none (Table 15.1, rule 8 on p.270).",
        sources=(tog("p.295"), tog("p.270"), tog("p.305")),
        kind=RuleKind.PLANT,
        exception_codes=("storage_tank_batch", "pressure_floating_on:<id>", "pressure_optional"),
        check=wired("check_inventory_once", "checks_inventory"),
    ),
    HandbookRule(
        rule_id="TOG309-SPLIT-PAIRING",
        title="Control pairing at a drum split",
        statement="At a drum split, flow control goes on the smaller stream and level control "
        "on the other.",
        sources=(tog("p.309"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        declared_parameters=("handbook.reflux_class_weights",),
        check=wired("check_split_pairing", "checks_split_pairing"),
    ),
    HandbookRule(
        rule_id="TOG122-PV-NO-BYPASS",
        title="Pressure-control station without a bypass",
        statement="Some companies give pressure-control valve stations no bypass.",
        sources=(tog("p.122"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="document",
        declared_parameters=("handbook.p_pv_no_bypass_document",),
        check=wired("check_pv_no_bypass", "checks_alternatives"),
    ),
)

PROTECTION = (
    HandbookRule(
        rule_id="TOG224-PSV-PIPE-CLEAN",
        title="Clean pipe between an enclosure and its PSV",
        statement="No check valve and no control valve between an enclosure and its pressure "
        "safety valve (Table 12.8).",
        sources=(tog("p.224"),),
        kind=RuleKind.PLANT,
        check=wired("check_psv_pipe_clean", "checks_closure"),
    ),
    HandbookRule(
        rule_id="TOG219-VESSEL-PSV",
        title="Every pressure vessel reaches a PSV",
        statement="Every pressure vessel reaches a pressure safety valve (fire case), except "
        "the declared condensate pot.",
        sources=(tog("p.219"), api("A.4.2.2.1 c p.27")),
        kind=RuleKind.PLACE,
        since="v2.1",
        exception_codes=("condensate_drain_pot",),
        check=wired("check_vessel_psv"),
    ),
    HandbookRule(
        rule_id="TOG207-HX-PSD-BOTH-SIDES",
        title="Pressure safety device on each exchanger side",
        statement="Each exchanger side that can be shut in at every nozzle has a pressure safety "
        "device, or an exception: a valve-free vessel with its own safety valve relieves it.",
        sources=(tog("p.207"),),
        kind=RuleKind.PLANT,
        exception_codes=("side_not_blockable", "relief_present", "derived:A-10.2 c.4"),
        check=wired("check_exchanger_psd", "checks_protection"),
    ),
    HandbookRule(
        rule_id="TOG236-TANK-EMERGENCY-VENT",
        title="Atmospheric tank breather and emergency vent",
        statement="An atmospheric tank has a normal vent (a breather valve, or a plain vent) and "
        "an emergency vent: a safety valve to the air. A non-flammable farm's tanks are outside "
        "the rule (scope code non_hydrocarbon).",
        sources=(tog("p.236"), lip1("§7.7 PDF p.968")),
        kind=RuleKind.PLACE,
        exception_codes=("scope:non_hydrocarbon",),
        check=wired("check_tank_emergency_vent", "checks_protection"),
    ),
    HandbookRule(
        rule_id="API14C-3.4-TWO-LEVELS",
        title="Two independent levels of protection",
        statement="A pressure vessel has two independent levels of protection (a relief valve "
        "plus a sensor trip), or a safety analysis checklist exception.",
        sources=(api("§3.4 b p.7"),),
        kind=RuleKind.PLANT,
        exception_codes=("derived:A-4.2 a.4", "deferred:valve_band", "scope:non_hydrocarbon"),
        check=wired("check_two_levels", "checks_protection"),
    ),
    HandbookRule(
        rule_id="API14C-SAC",
        title="Safety analysis checklist devices present",
        statement="Per component (A.4 pressure vessel, A.5 atmospheric vessel, A.6 fired, A.7 "
        "pump, A.8 compressor, A.10 exchanger), each checklist device is present or carries an "
        "omission code of API's own: derived from structure, declared once in the hidden state, "
        "or a scope exclusion. Items without a code are deferred one by one (the API14C-SAC-* "
        "deferred rows). Sensors are drawn as a switch with an alarm, without the shut-in "
        "action.",
        sources=(
            api("A-4.2 p.29"),
            api("A-5.2 p.31"),
            api("A-6.2 p.38"),
            api("A-7.2 p.44"),
            api("A-8.2 p.47"),
            api("A-10.2 p.53"),
        ),
        kind=RuleKind.PLANT,
        exception_codes=SAC_EXCEPTION_CODES,
        check=wired("check_sac", "checks_sac"),
    ),
)
