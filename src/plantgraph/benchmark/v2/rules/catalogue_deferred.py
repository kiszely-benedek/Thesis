"""Rules read from the handbooks but not encoded: the 14 deferred groups of design 4.9.

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


DEFERRED = (
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
    _deferred(
        "API14C-SAC-NO-EXCEPTION",
        "SAC devices without a derivable exception (compressor PSH/PSL/TSH/BDV, vessel LSL, ...)",
        (api("A-4.2, A-8.2", checked=False),),
        "each becomes a deferred row in T10, unless the device is cheap and inside the "
        "composition bands",
    ),
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
