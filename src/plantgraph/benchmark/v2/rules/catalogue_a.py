"""Rules of design 4.1 to 4.3: identification, valve positions, pumps (20 rules)."""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_support import api, lip1, pending, tog, wired
from plantgraph.benchmark.v2.rules.registry import ConflictNote, HandbookRule, RuleKind

IDENTIFICATION = (
    HandbookRule(
        rule_id="TOG28-SPARE-NAMING",
        title="Spare naming convention",
        statement="Installed spares are tagged P-125A/B, or as unrelated numbers P-125/P-126; "
        "one convention per train.",
        sources=(tog("p.28"), lip1("§1.1 PDF p.76")),
        kind=RuleKind.ALTERNATIVE,
        since="v2.1",
        sampling_unit="train",
        check=wired("check_spare_naming"),
    ),
    HandbookRule(
        rule_id="TOG113-MANUAL-VALVE-TAGS",
        title="Manual valves tagged or untagged per train",
        statement="Within a train, either every manual valve carries a tag or none does; "
        "automatic valves, safety valves and instruments are always tagged.",
        sources=(tog("p.113"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="train",
        declared_parameters=("handbook.p_untagged_manual_train",),
        check=pending("T6"),
    ),
    HandbookRule(
        rule_id="LIP1-1.1-SHARED-LOOP-NUMBER",
        title="Loop members share the loop number",
        statement="All members of a control loop share its number.",
        sources=(lip1("§1.1 PDF p.76"),),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_shared_loop_number"),
    ),
    HandbookRule(
        rule_id="TOG113-AUTOMATIC-VALVE-LETTERS",
        title="Automatic valve tag letters",
        statement="A control valve is the loop's xV; a switching valve is XV or UV; a hand "
        "control valve is HCV (Table 7.9).",
        sources=(tog("p.113"),),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_automatic_valve_letters"),
    ),
)

VALVE_POSITIONS = (
    HandbookRule(
        rule_id="TOG114-BLOCK-DEFAULT-NO",
        title="Blocking valves normally open",
        statement="A blocking valve is normally open unless marked otherwise.",
        sources=(tog("p.114"),),
        kind=RuleKind.PLACE,
        check=pending("T5"),
    ),
    HandbookRule(
        rule_id="TOG114-VENT-DRAIN-NC",
        title="Vent and drain valves normally closed",
        statement="Vent and drain valves are normally closed.",
        sources=(tog("p.114"),),
        kind=RuleKind.PLACE,
        check=pending("T5"),
    ),
    HandbookRule(
        rule_id="TOG120-CV-BYPASS-NC",
        title="Control-valve bypass normally closed",
        statement="The bypass valve of a control-valve station is closed in normal operation.",
        sources=(tog("p.120"),),
        kind=RuleKind.PLACE,
        check=pending("T5"),
    ),
    HandbookRule(
        rule_id="TOG224-PSV-BLOCKS-CSO",
        title="Block valves at a PSV car-sealed open",
        statement="Manual valves under and over a pressure safety valve (PSV) are full port and "
        "car-sealed open (Table 12.8, Fig. 12.9).",
        sources=(tog("p.224"),),
        kind=RuleKind.PLACE,
        check=pending("T5"),
    ),
    HandbookRule(
        rule_id="TOG114-FAIL-ACTION",
        title="Every automatic valve has a fail action",
        statement="Every automatic valve has a fail action (fail open, closed or last); a "
        "min-flow control valve fails open.",
        sources=(tog("p.114–115"),),
        kind=RuleKind.PLACE,
        declared_parameters=("handbook.fail_action_table",),
        check=pending("T5"),
    ),
    HandbookRule(
        rule_id="TOG34-BL-ISOLATION",
        title="Battery-limit isolation variants",
        statement="A battery-limit crossing has a blind; or an isolation valve and a blind; or "
        "an isolation valve, a blind and a check valve.",
        sources=(tog("p.34"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        check=pending("T11"),
    ),
)

PUMPS = (
    HandbookRule(
        rule_id="TOG192-RECIP-NO-CHECK",
        title="No external check valve on a reciprocating pump",
        statement="Centrifugal and rotary pump discharges have a check valve; reciprocating "
        "pumps have none (they have an internal one). Fig. 10.31 and 10.32.",
        sources=(tog("p.84"), tog("p.192"), tog("p.193")),
        conflict=ConflictNote(
            other=api("A.7.2.2.2 p.40"),
            basis="later_source",
            choice="follow Toghraei 2019, the later source; API 14C (2001) says all pumps",
        ),
        kind=RuleKind.FORBID,
        check=wired("check_recip_no_check", "checks_pumps"),
    ),
    HandbookRule(
        rule_id="TOG192-PD-NO-MINFLOW",
        title="No min-flow line on positive-displacement pumps",
        statement="No min-flow line on reciprocating or rotary pumps.",
        sources=(tog("p.192"), tog("p.193")),
        kind=RuleKind.FORBID,
        check=wired("check_pd_no_minflow", "checks_pumps"),
    ),
    HandbookRule(
        rule_id="TOG177-MINFLOW-TAKEOFF",
        title="Min-flow take-off position",
        statement="A min-flow line leaves upstream of the check valve or downstream of the "
        "isolation valve, never between them.",
        sources=(tog("p.177"),),
        kind=RuleKind.PLACE,
        check=wired("check_minflow_takeoff", "checks_pumps"),
    ),
    HandbookRule(
        rule_id="TOG177-MINFLOW-NEED",
        title="Which centrifugal pumps get a spillback",
        statement="Centrifugal pumps that run continuously on the main stream, are above 5 hp, "
        "or sit on level control get a spillback; a pump with its own flow loop or a "
        "variable-speed drive does not.",
        sources=(tog("p.177"),),
        kind=RuleKind.PLACE,
        declared_parameters=("handbook.pump_power_weights",),
        check=wired("check_minflow_need", "checks_pumps_power"),
    ),
    HandbookRule(
        rule_id="TOG313-MINFLOW-METHOD",
        title="Min-flow method by pump power",
        statement="Below 5 hp none; 5-20 hp a restriction-orifice line; 20-35 hp an on-off "
        "switching valve on a flow transmitter; above 35 hp flow transmitter, controller, valve.",
        sources=(tog("p.313"), tog("p.179")),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        declared_parameters=("handbook.pump_power_weights",),
        check=wired("check_minflow_method", "checks_pumps_power"),
    ),
    HandbookRule(
        rule_id="TOG219-PD-RELIEF",
        title="Relief path on a positive-displacement pump",
        statement="A positive-displacement pump discharge has a relief path: a blocked outlet "
        "has no maximum pressure.",
        sources=(tog("p.219"), tog("p.192")),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_pd_relief"),
    ),
    HandbookRule(
        rule_id="TOG314-PD-NO-THROTTLE",
        title="No throttling valve on a positive-displacement pump",
        statement="No flow control valve throttles a positive-displacement pump's discharge in "
        "series; capacity comes from a variable-speed drive or stroke, or from a recirculation "
        "line with a control valve.",
        sources=(tog("p.314"),),
        kind=RuleKind.FORBID,
        check=wired("check_pd_no_throttle", "checks_pumps"),
    ),
    HandbookRule(
        rule_id="TOG270-PUMP-FLOW-CONTROLLED",
        title="Each pump set's flow is controlled once",
        statement="Each pump set's flow is controlled exactly once: its own flow loop, a "
        "variable-speed drive, or a level loop's valve on its discharge.",
        sources=(tog("p.270"),),
        kind=RuleKind.PLANT,
        check=wired("check_pump_flow_controlled", "checks_pump_flow"),
    ),
    HandbookRule(
        rule_id="TOG175-PUMP-TRIM",
        title="Centrifugal pump trim",
        statement="Centrifugal pump: suction block valve and strainer; discharge gauge, check "
        "valve, block valve. On v2.1 plants only: v2.2 drops the check on reciprocating pumps.",
        sources=(tog("p.175"), tog("p.84")),
        kind=RuleKind.PLACE,
        since="v2.1",
        check=wired("check_pump_trim"),
    ),
    HandbookRule(
        rule_id="TOG173-PUMP-REDUCERS",
        title="Reducer and enlarger at pump nozzles",
        statement="A centrifugal pump may have a reducer on its suction and an enlarger on its "
        "discharge.",
        sources=(tog("p.173–175"),),
        kind=RuleKind.ALTERNATIVE,
        sampling_unit="item",
        declared_parameters=("handbook.p_pump_reducers",),
        check=pending("T11"),
    ),
)
