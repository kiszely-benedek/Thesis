"""Rules of design 4.4 to 4.7: compressors, exchangers and heaters, control, protection (20)."""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_support import api, lip1, pending, tog, wired
from plantgraph.benchmark.v2.rules.registry import HandbookRule, RuleKind

# `pending("unassigned")`: a v2.1 behaviour to cite and test, which design 13 gives to no task

COMPRESSORS = (
    HandbookRule(
        rule_id="TOG319-ANTISURGE-DYNAMIC",
        title="Anti-surge only on dynamic compressors",
        statement="Anti-surge recycle only on dynamic (centrifugal) compressors, not on "
        "positive-displacement gas movers.",
        sources=(tog("p.319"),),
        kind=RuleKind.FORBID,
        check=pending("T3"),
    ),
    HandbookRule(
        rule_id="TOG316-PD-COMP-CAPACITY",
        title="Capacity control of a positive-displacement compressor",
        statement="Capacity comes from a spillback line with a capacity loop, or a "
        "variable-speed drive; never discharge throttling (Table 15.10).",
        sources=(tog("p.316"), tog("p.317")),
        kind=RuleKind.PLACE,
        check=pending("T3"),
    ),
    HandbookRule(
        rule_id="API14C-A8-FSV",
        title="Check valve on the compressor final discharge",
        statement="A check valve on the compressor's final discharge.",
        sources=(api("A.8.3.2 p.45"), tog("p.84")),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=pending("unassigned"),
    ),
    HandbookRule(
        rule_id="API14C-A8-PSV",
        title="PSV on the compressor discharge",
        statement="A pressure safety valve (PSV) on the compressor discharge.",
        sources=(api("A.8.2.2.1 p.45"),),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=pending("unassigned"),
    ),
)

EXCHANGERS = (
    HandbookRule(
        rule_id="TOG207-HX-NO-ISOLATION",
        title="No isolation valves around an exchanger",
        statement="No isolation valves and no bypass around an exchanger unless it has a spare "
        "or a cleaning system.",
        sources=(tog("p.207"),),
        kind=RuleKind.FORBID,
        since="v2.1",
        check=pending("unassigned"),
    ),
    HandbookRule(
        rule_id="TOG320-HX-NONTARGET",
        title="Temperature control moves the non-target stream",
        statement="The temperature controller moves the non-target stream: directly on a "
        "utility, by a bypass on a process stream.",
        sources=(tog("p.320–321"),),
        kind=RuleKind.PLANT,
        check=pending("T9"),
    ),
    HandbookRule(
        rule_id="TOG322-HX-BYPASS-VARIANT",
        title="Exchanger bypass variants",
        statement="A bypass temperature valve alone, or control valves on both the main and "
        "the bypass branch.",
        sources=(tog("p.322"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        check=pending("T11"),
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
        check=pending("unassigned"),
    ),
    HandbookRule(
        rule_id="TOG214-FUEL-SWITCHING-VALVES",
        title="Fuel line switching valves",
        statement="One switching valve, or two in series, on the fuel line; each valve gets "
        "its own actuator and number.",
        sources=(tog("p.214"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        check=pending("T11"),
    ),
)

CONTROL = (
    HandbookRule(
        rule_id="TOG271-ONE-CV-LIQUID",
        title="One control valve in series on a liquid line",
        statement="At most one control valve in series on a liquid-filled line between two "
        "containers; a flooded vessel counts as pipe.",
        sources=(tog("p.271"),),
        kind=RuleKind.PLANT,
        check=pending("T9"),
    ),
    HandbookRule(
        rule_id="TOG267-FE-UPSTREAM-FV",
        title="Flow element upstream of its valve",
        statement="A flow element sits upstream of the flow valve of its loop.",
        sources=(tog("p.267"),),
        kind=RuleKind.PLANT,
        check=pending("T9"),
    ),
    HandbookRule(
        rule_id="TOG295-INVENTORY-ONCE",
        title="One loop per inventory",
        statement="A non-flooded liquid container has exactly one level loop; a gas container "
        "exactly one pressure loop; a flooded container none (Table 15.1, rule 8 on p.270).",
        sources=(tog("p.295"), tog("p.270")),
        kind=RuleKind.PLANT,
        exception_codes=("storage_tank_batch", "pressure_floating_on:<id>"),
        check=pending("T9"),
    ),
    HandbookRule(
        rule_id="TOG309-SPLIT-PAIRING",
        title="Control pairing at a drum split",
        statement="At a drum split, flow control goes on the smaller stream and level control "
        "on the other.",
        sources=(tog("p.309"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        check=pending("T11"),
    ),
    HandbookRule(
        rule_id="TOG122-PV-NO-BYPASS",
        title="Pressure-control station without a bypass",
        statement="Some companies give pressure-control valve stations no bypass.",
        sources=(tog("p.122"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="train",
        declared_parameters=("handbook.p_pv_no_bypass_train",),
        check=pending("T11"),
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
        check=pending("T9"),
    ),
    HandbookRule(
        rule_id="TOG219-VESSEL-PSV",
        title="Every pressure vessel reaches a PSV",
        statement="Every pressure vessel reaches a pressure safety valve (fire case), except "
        "the declared condensate pot.",
        sources=(tog("p.219"), api("A.4.2.2.1 p.26")),
        kind=RuleKind.PLACE,
        since="v2.1",
        exception_codes=("condensate_drain_pot",),
        check=wired("check_vessel_psv"),
    ),
    HandbookRule(
        rule_id="TOG207-HX-PSD-BOTH-SIDES",
        title="Pressure safety device on each exchanger side",
        statement="Each exchanger enclosure has a pressure safety device, or a pressure-model "
        "exception.",
        sources=(tog("p.207"),),
        kind=RuleKind.PLANT,
        check=pending("T10"),
    ),
    HandbookRule(
        rule_id="TOG236-TANK-EMERGENCY-VENT",
        title="Atmospheric tank breather and emergency vent",
        statement="An atmospheric tank has a normal breather and an emergency vent.",
        sources=(tog("p.236"), lip1("§7.7 PDF p.968")),
        kind=RuleKind.PLACE,
        check=pending("T10"),
    ),
    HandbookRule(
        rule_id="API14C-3.4-TWO-LEVELS",
        title="Two independent levels of protection",
        statement="A pressure vessel has two independent levels of protection (a relief valve "
        "plus a sensor trip), or a safety analysis checklist exception.",
        sources=(api("§3.4 b p.7"),),
        kind=RuleKind.PLANT,
        check=pending("T10"),
    ),
    HandbookRule(
        rule_id="API14C-SAC",
        title="Safety analysis checklist devices present",
        statement="Per component (A.4 pressure vessel, A.5 atmospheric vessel, A.6 fired, A.7 "
        "pump, A.8 compressor, A.10 exchanger), each checklist device is present or carries an "
        "omission code. Items without a derivable exception are deferred one by one.",
        sources=(api("App. A", checked=False),),
        kind=RuleKind.PLANT,
        check=pending("T10"),
    ),
)
