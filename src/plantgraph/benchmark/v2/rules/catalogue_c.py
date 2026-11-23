"""Rules of design 4.8: networks, streams and pressure levels (14 rules)."""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_support import api, design, pending, tog, wired
from plantgraph.benchmark.v2.rules.registry import HandbookRule, RuleKind

NETWORKS_AND_PRESSURE = (
    HandbookRule(
        rule_id="TOG32-NETWORK-SHEETS",
        title="Relief, drain and utility lines continue on network sheets",
        statement="Relief, closed-drain and utility lines continue on network P&IDs (mainly "
        "pipes), reached through off-page connectors.",
        sources=(tog("p.32–34"),),
        kind=RuleKind.PLACE,
        check=pending("T7"),
    ),
    HandbookRule(
        rule_id="TOG141-DRAIN-DESTINATION",
        title="Drain destination by fluid class",
        statement="Hydrocarbon (non-innocent) drains are hard-piped to the closed drain; water "
        "(innocent) drains go to an open drain.",
        sources=(tog("p.141"),),
        kind=RuleKind.PLACE,
        check=pending("T7"),
    ),
    HandbookRule(
        rule_id="TOG360-UTILITY-NETWORKS",
        title="Utility distribution and collection networks",
        statement="Every utility has a distribution network; steam, cooling water and similar "
        "have a collection network (Fig. 17.1).",
        sources=(tog("p.360"),),
        kind=RuleKind.PLACE,
        check=pending("T7"),
    ),
    HandbookRule(
        rule_id="TOG33-INTERAREA",
        title="Lines between areas run over an interarea sheet",
        statement="Lines between areas (trains) run over an interarea P&ID with straight pipes.",
        sources=(tog("p.33"),),
        kind=RuleKind.PLACE,
        check=pending("T7"),
    ),
    HandbookRule(
        rule_id="TOG24-NO-VISITING-STREAM",
        title="Every line on a sheet connects to an item on it",
        statement="Every line on a sheet connects to an item on that sheet.",
        sources=(tog("p.24"),),
        kind=RuleKind.PLANT,
        check=wired("check_no_visiting_stream", "checks_closure"),
    ),
    HandbookRule(
        rule_id="PLT-NETWORK-CLOSURE",
        title="Network connectors pair and headers end",
        statement="Every network connector has a partner; every header ends at a declared end.",
        sources=(tog("p.32–34"),),
        kind=RuleKind.PLANT,
        check=pending("T7"),
    ),
    HandbookRule(
        rule_id="PLT-STREAM-CLOSURE",
        title="Every line has a source and a sink",
        statement="Every line has a source and a sink item, or a declared end (battery limit, "
        "network end, vent to atmosphere, capped maintenance drain).",
        sources=(tog("p.24"),),
        kind=RuleKind.PLANT,
        check=wired("check_stream_closure", "checks_closure"),
    ),
    HandbookRule(
        rule_id="PLT-PHASE",
        title="A gas port never meets a liquid port",
        statement="A gas port never meets a liquid port, and no pump feeds its own suction "
        "except by a recycle (invariant S12).",
        sources=(design("S12"),),
        kind=RuleKind.PLANT,
        since="v2.1",
        check=wired("check_phase"),
    ),
    HandbookRule(
        rule_id="PLT-RECYCLE-CLOSURE",
        title="A recycle returns inside its unit through a reducing element",
        statement="A spillback, min-flow or anti-surge recycle returns inside its unit, from a "
        "higher to a lower pressure level, through a reducing element (an orifice, a control "
        "valve, or the on-off valve of a switching min-flow line). A reactor's recycle-gas loop "
        "is driven by its own compressor and is not one (design 17.12).",
        sources=(tog("p.317"),),
        kind=RuleKind.PLANT,
        check=wired("check_recycle_closure", "checks_pressure"),
    ),
    HandbookRule(
        rule_id="PRS-MONOTONE",
        title="Pressure never rises along the flow except across a mover",
        statement="Along the flow the pressure level never rises except across a pump, "
        "compressor or ejector.",
        sources=(design("§6.2"),),
        kind=RuleKind.PLANT,
        check=wired("check_monotone", "checks_pressure"),
    ),
    HandbookRule(
        rule_id="TOG82-SPEC-BREAK",
        title="Spec break where the pressure level changes",
        statement="A spec break (change of pipe class) where a control valve or orifice lowers "
        "the level, or a pump or compressor raises it (Table 6.5).",
        sources=(tog("p.82"),),
        kind=RuleKind.PLANT,
        check=wired("check_spec_break", "checks_pressure"),
    ),
    HandbookRule(
        rule_id="PRS-SPEC-CLASS",
        title="Heavier pipe class on the high-pressure side",
        statement="The heavier pipe class is on the higher-level side of a spec break.",
        sources=(design("ADR-0065 F8c"),),
        kind=RuleKind.PLANT,
        check=wired("check_spec_class", "checks_pressure"),
    ),
    HandbookRule(
        rule_id="TOG156-MERGE-CHECK",
        title="Check valve where a low-pressure stream ties in",
        statement="A low-pressure or intermittent stream tying into another has a check valve.",
        sources=(tog("p.156"),),
        kind=RuleKind.PLANT,
        check=wired("check_merge_check", "checks_overpressure"),
    ),
    HandbookRule(
        rule_id="API14C-A4-OVERPRESSURE",
        title="Overpressure protection of an enclosure",
        statement="An enclosure fed from a higher level, or by a positive-displacement mover, "
        "has a pressure safety device; otherwise the exception comes from the pressure model.",
        sources=(api("A.4.2.2.1 a p.26"),),
        kind=RuleKind.PLANT,
        exception_codes=("source_cannot_exceed",),
        check=wired("check_overpressure", "checks_overpressure"),
    ),
)
