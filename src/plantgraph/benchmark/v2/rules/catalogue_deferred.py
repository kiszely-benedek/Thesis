"""Rules read from the handbooks but not encoded: design 4.9, TOG73 (T3), SAC items (T10).

A deferred entry still has a rule id, a source and a reason, so the thesis can say what was read
and left out. Its `kind` is nominal (the closest of the four); it has no check.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_support import api, lip1, lip_pc, tog
from plantgraph.benchmark.v2.rules.registry import HandbookRule, RuleKind, RuleStatus, SourceRef


def _deferred(
    rule_id: str, title: str, sources: tuple[SourceRef, ...], reason: str
) -> HandbookRule:
    return HandbookRule(
        rule_id=rule_id,
        title=title,
        statement=title,
        sources=sources,
        kind=RuleKind.PLACE,
        status=RuleStatus.DEFERRED,
        deferral_reason=reason,
    )


#: the checklist items with no device drawn and no code to derive, declare or scope (design 17.13
#: R6, R7, R8): one row each, so the registry says what was read and left out
_SAC_DEFERRED = (
    _deferred(
        "API14C-SAC-A4-PSL",
        "Vessel pressure switch low (A-4.2 b)",
        (api("A-4.2 b p.29"),),
        "no derivable omission code for most vessels (b.2 'atmospheric in service' must not be "
        "read from the ordinal level, 17.13 R1); +0.94 instruments per sheet",
    ),
    _deferred(
        "API14C-SAC-A4-FSV",
        "Vessel outlet check valve (A-4.2 f)",
        (api("A-4.2 f p.29"),),
        "f.3 holds only where a control valve stands on the outlet; a check valve on a column "
        "overhead or a reboiler circuit is not how engineers draw it",
    ),
    _deferred(
        "API14C-SAC-A4-FILTER-PSV",
        "Safety valve on a filter (A-4.2 c)",
        (api("A-4.2 c p.29"),),
        "a filter is an A.4 vessel (17.13 R7 f) but has no c.3 or c.4 from structure; one valve "
        "per filter would press on the valve band (code deferred:valve_band)",
    ),
    _deferred(
        "API14C-SAC-A6-HEATER-CHECK",
        "Check valve on the heater outlet (A-6.2 m)",
        (api("A-6.2 m p.38"),),
        "m.2 (backflow volume insignificant) is a judgement for a hydrocarbon feed; left to a "
        "process engineer (17.13 R8)",
    ),
    _deferred(
        "API14C-SAC-A6-STACK-TSH",
        "Stack temperature switch high (A-6.2 b)",
        (api("A-6.2 b p.38"),),
        "the model draws no stack: the furnace allowlist has no stack class or nozzle",
    ),
    _deferred(
        "API14C-SAC-A6-AIR-INTAKE-ARRESTOR",
        "Flame arrestor on the air intake (A-6.2 j)",
        (api("A-6.2 j p.38"),),
        "no air-intake line is modelled; drawing one needs a new furnace port",
    ),
    _deferred(
        "API14C-SAC-A6-STACK-ARRESTOR",
        "Stack arrestor (A-6.2 k)",
        (api("A-6.2 k p.38"),),
        "no stack is modelled",
    ),
    _deferred(
        "API14C-SAC-A7-PSH-PSL",
        "Pump discharge pressure switches high and low (A-7.2 b, d)",
        (api("A-7.2 b p.44"), api("A-7.2 d p.44")),
        "the omission b.2 needs a design pressure the ordinal model lacks; 154 pumps would add "
        "+3.95 instruments per sheet and a switch on every process pump is offshore practice",
    ),
    _deferred(
        "API14C-SAC-A8-SDV-BDV-ASH",
        "Shut-down and blowdown valves, gas detection at a compressor",
        (api("A.8.2.2.3 p.45"), api("A.8.3.5 p.45")),
        "not SAC items (17.13 R6): they come from the text and Figure A-8; gas detection needs an "
        "enclosed building the model lacks, and the valves would press on the valve band",
    ),
    _deferred(
        "API14C-SAC-A10-PROCESS-SECTION",
        "Exchanger process-section pressure switches (A-10.2 a, b)",
        (api("A-10.2 a p.53"), api("A-10.2 b p.53")),
        "no omission code remains where no valve-free vessel carries a PSH: a.2 needs a design "
        "pressure, b.2 must not be read off the ordinal ATM level",
    ),
)

DEFERRED = (
    _deferred(
        "TOG73-UNTAGGED-BRANCH-PIPES",
        "No line number on short branch pipes",
        (tog("p.73"),),
        "the frozen DEXPI builder refuses a run without a parseable line number "
        "(adapters/pydexpi_builder_v2_lines.py `line_list_fields`) and the adapter keys stream "
        "kinds by it; the frozen line view itself folds such branches correctly "
        "(tests/v2/test_tog73_line_view.py)",
    ),
    _deferred(
        "LIP1-1.1-GAUGE-FUNCTIONAL-ONLY",
        "Functional-only identification for local gauges (no loop number)",
        (lip1("§1.1 PDF p.56"),),
        "gauges would share tags like PI; this breaks S9 and identity by tag in the frozen "
        "resolver",
    ),
    _deferred(
        "LIP1-1.1-PARALLEL-NUMBERING",
        "Parallel loop numbering",
        (lip1("§1.1 PDF p.58"),),
        "FIC-101 and LIC-101 would share a loop number, which collides with the ADR-0027 "
        "signal-connector key",
    ),
    _deferred(
        "LIP1-1.1-SEQUENCE-GAPS",
        "Gaps in tag sequences",
        (lip1("§1.1 PDF p.58"), lip1("§1.1 PDF p.76")),
        "no effect on what the thesis measures",
    ),
    _deferred(
        "API14C-2-S-LETTERS",
        "API 'S' device letters (PSH/LSH meaning safety)",
        (api("§2", checked=False),),
        "the same letters mean different things in ISA; the frozen primer (ADR-0041) explains ISA",
    ),
    _deferred(
        "LIPPC-8.19-TRIP-SOLENOID-ON-CV",
        "Trip by a solenoid on the control valve",
        (lip_pc("§8.19"),),
        "one valve with two drivers breaks S7 and LOOP_ACTUATED_VALVE",
    ),
    _deferred(
        "LIPPC-8.23-MINFLOW-KICKBACK",
        "Min-flow by a PCV kickback or a flow-switch pump trip",
        (lip_pc("§8.23"),),
        "page not verifiable; the flow-switch trip is a new motor-trip shape",
    ),
    _deferred(
        "TOG322-3WAY-EXCHANGER-VALVE",
        "Three-way exchanger valve",
        (tog("p.322"),),
        "needs a new class (ADR-0016)",
    ),
    _deferred(
        "TOG192-PULSATION-DAMPENER",
        "Pulsation dampener; back-pressure regulator on dosing pumps; self-acting regulators",
        (tog("p.192"), tog("p.195")),
        "no fitting class for a dampener; a one-member regulator loop breaks S8",
    ),
    _deferred(
        "TOG9-BLANKETING-VRU",
        "Tank blanketing and vapour recovery unit",
        (tog("ch.9", checked=False), tog("ch.15", checked=False)),
        "needs split-range pressure valves and a vapour-recovery network; for later",
    ),
    _deferred(
        "TOG8-DOUBLE-BLOCK-BLEED",
        "Double block and bleed; blinds at pump isolation valves",
        (tog("ch.8", checked=False), tog("p.175")),
        "changes isolation answers; low value",
    ),
    _deferred(
        "TOG213-FIRED-HEATER-DETAIL",
        "Fired heater passes, pilot gas line, snuffing steam",
        (tog("p.213–215"),),
        "a new heater pattern variant; large",
    ),
    *_SAC_DEFERRED,
    _deferred(
        "API14C-4.2.3-SHUT-IN-SOURCE",
        "Shut-in at the primary source",
        (api("§4.2.3 p.14"),),
        "needs trip-to-motor interlock edges across sheets, which S19/S20 forbid; v2.2 reports "
        "the share of trips that act at the source",
    ),
    _deferred(
        "TOG16-INTERLOCK-STYLE-MULTISTAGE",
        "Interlock-diamond drawing style; multi-stage compressors; lube-oil and seal systems",
        (tog("ch.16", checked=False), tog("ch.10", checked=False)),
        "drawing style, or detail P&IDs",
    ),
)
