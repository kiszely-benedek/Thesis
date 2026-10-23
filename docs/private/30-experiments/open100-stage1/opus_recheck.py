"""Independent blind transcription of the 71 off-page connector flags in
bboxes_3plus.json (OPEN100 / PID2Graph sheets 3-11).

Each row was read from a wide crop taken directly from the full-resolution
sheet PNG (see opus_wide_crops/), plus targeted 3-6x zooms where a label or a
pipe junction was ambiguous. Text is transcribed as printed, including the
drawing's own typos and inconsistent prefixes.

A `line_number` is recorded only where the label could be traced to the pipe
run that actually terminates at (or originates from) this flag's own arrow.
Where the nearest label belongs to a neighbouring branch, or sits on a header
downstream of a merge that this flag feeds, the field is left None.
"""

# sheet, node, target_pid, target_sheet_no, grid_cell, service, line_number, confidence, note
ROWS = (
    # ---- sheet 3 ------------------------------------------------------------
    ("3", "16", "170", 2, None, "FWS", "SIZE-FWS-161131-SPEC-HC-X", "high",
     "flag text: FWS TO STEAM GENERATOR / FWS PID 170-2"),
    ("3", "82", "140", 1, None, "MSS", "SIZE-MSS-170133-SPEC-HC-X", "high",
     "flag text: FWS TO MAIN STM BYPASS / MSS PID 140-1"),
    ("3", "89", "290", 1, None, "WSS", "SIZE-WSS-170134-SPEC-HC-X", "high",
     "flag text: FW SAMPLE / WSS PID 290-1"),

    # ---- sheet 4 ------------------------------------------------------------
    ("4", "16", "260", 1, None, "PDS", "SIZE-PDS-165139-SPEC-HC-X", "high",
     "flag text: PDS PID 260-1 / PLANT DRAIN SYSTEM"),
    ("4", "39", "190", 1, None, "HPSD", "SIZE-HPSD-166140-SPEC-HC-X", "high",
     "flag text: HPSD PID 190-1 / HIGH PRESSURE STM DRAIN"),
    ("4", "41", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", "high",
     "second line reads CONDENSATE; identical line number appears on sheet 4 "
     "node 117, which is a different run (this one feeds CND-HTR-166 N9)"),
    ("4", "42", "200", 4, None, "WTS", None, "high",
     "no line-number label anywhere on the run from the flag through LCV 6509 "
     "to CND-TK-165 nozzle N1"),
    ("4", "43", "140", 1, None, "MSS", "SIZE-ESS-140083-SPEC-HC-X", "medium",
     "only label on the continuous run from this flag to ESS-HTR-180, but its "
     "service prefix is ESS while the flag says MSS; drain tees and a PSV "
     "branch sit between the flag and the label"),
    ("4", "48", "240", 1, "D-1", "TBS", "SIZE-ESS-250137-SPEC-HC-X", "high",
     "flag service TBS, line label prefix ESS"),
    ("4", "104", "240", 1, "E-1", "TBS", "SIZE-ESS-250136-SPEC-HC-X", "high",
     "flag service TBS, line label prefix ESS"),
    ("4", "117", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", "high",
     "second line printed CONDENSATE SYSYTEM (sic); duplicate line number, "
     "same string as sheet 4 node 41 on a different run (this one feeds "
     "TCV 16013 / ESS-HTR-180)"),

    # ---- sheet 5 ------------------------------------------------------------
    ("5", "12", "290", 1, None, "WSS", "SIZE-WS-101024-SPEC-HC-X", "high",
     "line label prefix printed WS, not WSS; branch tees off the vertical "
     "SIZE-RCS-101002 header and the label is on the branch itself"),
    ("5", "38", "120", 1, None, "RHRS", "SIZE-RHRS-100021-SPEC-HC-X", "high",
     "flag printed RHRS PID-120-01 (dash form, zero-padded sheet number)"),
    ("5", "43", "100", 2, None, "RC", "SIZE-RCS-101006-SPEC-HC-X", "high",
     "flag second line printed RC-PID-100-2; every other reference to this "
     "target on the same sheet is printed RCS-PID-100-2"),
    ("5", "45", "110", 1, None, "CVCS", "SIZE-CVCS-101022-SPEC-HC-X", "high",
     "flag printed CVCS-PID-110-1 (dash form)"),
    ("5", "46", "100", 2, None, "RCS", "SIZE-RCS-100008-SPEC-HC-X", "high",
     "flag printed RCS-PID-100-2 (dash form)"),
    ("5", "47", "110", 1, "H-12", "CVCS", "SIZE-CVCS-110053-SPEC-HC-X", "high",
     None),
    ("5", "49", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121073-SPEC-HC-X", "high",
     None),
    ("5", "54", "120", 1, "E-1", "RHRS", "SIZE-RHRS-121A072-SPEC-HC-X", "high",
     None),
    ("5", "78", "100", 2, None, "RCS", "SIZE-RCS-100007-SPEC-HC-X", "high",
     None),
    ("5", "86", "290", 1, None, "WSS", "SIZE-WSS-100023-SPEC-HC-X", "high",
     None),
    ("5", "114", "110", 1, "G-12", "CVCS", "SIZE-CVCS-115C049-SPEC-HC-X",
     "high", None),
    ("5", "124", "120", 1, "D-1", "RHRS", "SPEC-RHRS-121A065-SPEC-HC-X",
     "high", "line label starts SPEC- rather than SIZE-"),

    # ---- sheet 6 ------------------------------------------------------------
    ("6", "16", "100", 1, "G-1", "RCS", "SIZE-RCS-100007-SPEC-HC-X", "high",
     "explicit leader line runs from the label to this flag's own pipe"),
    ("6", "27", "100", 1, "C-1", "RCS", "SIZE-RCS-100008-SPEC-HC-X", "high",
     "explicit leader line runs from the label to this flag's own pipe"),
    ("6", "28", "210", 2, "C-1", "ACW", "SIZE-ACW-211158-SPEC-HC-X", "high",
     "vertical riser to COOLANT HT EXCH RC-P100-X001 terminates at this "
     "flag's tee; no other source joins it"),
    ("6", "30", "210", 2, "C-1", "ACW", "SIZE-ACW-211157-SPEC-HC-X", "high",
     None),
    ("6", "31", "100", 1, "D-1", "RCS", "SIZE-RCS-101006-SPEC-HC-X", "high",
     None),
    ("6", "40", "210", 2, None, "ACW", "SIZE-ACW-102160-SPEC-HC-X", "high",
     "continuous run: HX outlet, right, down, into the flag; no merge"),
    ("6", "41", "210", 2, None, "ACW", None, "medium",
     "run from COOLANT HT EXCH RC-P100-X001 into this flag carries no label; "
     "the nearby SIZE-ACW-102161-SPEC-HC-X sits beside YE 102A35 on a "
     "different line and has no leader to this run"),
    ("6", "68", "320", 1, None, "RWS", "SIZE-RWS-104025-SPEC-HC-X", "high",
     None),
    ("6", "69", "130", 1, None, "SWS", "SIZE-SWS-132172-SPEC-HC-X", "high",
     None),
    ("6", "71", "320", 1, None, "RWS", None, "high",
     "short run from RCS-VE-104 outlet through LCV 1043 carries no line "
     "number; the nearest label SIZE-RCS-103011-SPEC-HC-X is on the vessel "
     "inlet line on the far side"),

    # ---- sheet 7 ------------------------------------------------------------
    ("7", "30", "170", 2, None, "FWS", "SIZE-ACW-175271-SPEC-HC-X", "high",
     "flag service FWS but line label prefix ACW; number 175271 also appears "
     "as SIZE-FWS-175271 on sheet 7 node 33"),
    ("7", "31", "170", 2, None, "FWS", "SIZE-ACW-211270-SPEC-HC-X", "high",
     "flag service FWS but line label prefix ACW"),
    ("7", "32", "240", 1, None, "TBS", "SIZE-ACW-250261-SPEC-HC-X", "high",
     "flag printed TBS-240-1 with no PID keyword; line label prefix ACW"),
    ("7", "33", "210", 2, "F-1", "ACW", "SIZE-FWS-175271-SPEC-HC-X", "high",
     "flag service ACW but line label prefix FWS; see sheet 7 node 30"),
    ("7", "34", "160", 1, None, "WTS", None, "high",
     "no line-number label on the run from the flag through FCV XXX into the "
     "tank nozzle"),
    ("7", "35", None, None, None, None, None, "low",
     "not an off-page connector: the bbox is a ~17x8 px nozzle/flange symbol "
     "on the vertical drop below FCV XXX into the tank; no text at all"),
    ("7", "75", "210", 2, None, "ACW", "SIZE-ACW-211152-SPEC-HC-X", "high",
     "flag second line AUX COOLING WATER SYSTEM"),
    ("7", "76", "250", 1, None, "TBS", "SIZE-ACW-211153-SPEC-HC-X", "high",
     "flag service TBS but line label prefix ACW"),

    # ---- sheet 8 ------------------------------------------------------------
    ("8", "5", "130", 1, None, "SWS", "SIZE-ACW-111162-SPEC-HC-X", "high",
     "flag service SWS but line label prefix ACW; label sits between "
     "MOV 1114 and the flag"),
    ("8", "6", "130", 1, None, "SWS", "SIZE-SWS-130182-SPEC-HC-X", "high",
     "flag second line reads SERVICE WATER, not SERVICE WATER SYSTEM"),
    ("8", "7", "210", 1, "A-1", "ACW", "SIZE-ACW-211152-SPEC-HC-X", "high",
     None),
    ("8", "12", "100", 2, None, "RCS", "SIZE-ACW-211157-SPEC-HC-X", "high",
     "flag service RCS but line label prefix ACW"),
    ("8", "13", "100", 2, None, "RCS", "SIZE-ACW-211158-SPEC-HC-X", "medium",
     "flag service RCS but line label prefix ACW; a branch merges into this "
     "run just upstream of the label, though the label is on the terminal "
     "segment that enters the flag"),
    ("8", "15", "130", 1, None, "SWS", "SIZE-ACS-102163-SPEC-HC-X", "medium",
     "two verticals merge into this header upstream of the flag, so the "
     "label describes the merged run rather than any single source"),
    ("8", "16", "270", 1, None, "WPS", "SIZE-ACW-111164-SPEC-HC-X", "high",
     "flag service WPS but line label prefix ACW"),
    ("8", "17", "130", 1, None, "SWS", "SIZE-SWS-132181-SPEC-HC-X", "high",
     None),
    ("8", "31", "100", 2, "C-1", "RCS", "SIZE-ACW-102160-SPEC-HC-X", "high",
     "flag printed RCS PID 100-2(C-1) with no space before the bracket"),
    ("8", "32", "100", 2, "A-4", "RCS", "SIZE-ACW-102161-SPEC-HC-X", "high",
     "grid cell A-4, not the A-1/C-1 pattern used elsewhere"),
    ("8", "54", "210", 1, None, "ACW", None, "medium",
     "flag second line printed AUC COOLING WATER SYSTEM (sic); the nearest "
     "label SIZE-ACW-111156-SPEC-HC-X sits downstream of a point where "
     "another ACW line merges into this run, so it is not attributable to "
     "this connector alone"),

    # ---- sheet 9 ------------------------------------------------------------
    ("9", "2", "120", 1, None, "RHR", None, "high",
     "flag text: RES HEAT REMOVAL SYSTEM / RHR PID 120-1; collection header "
     "with many branches merging in and no line-number label anywhere along "
     "its full width (checked the whole run)"),
    ("9", "59", "120", 1, None, "RHR", None, "high",
     "flag text: RES HEAT REMOVAL SYSTEM / RHR PID 120-1; distribution "
     "header with many branches and no line-number label anywhere along it"),

    # ---- sheet 10 -----------------------------------------------------------
    ("10", "14", "120", 1, None, "RHR", "SIZE-CVCS-115C049-SPEC-HC-X", "high",
     "flag service RHR but line label prefix CVCS"),
    ("10", "15", "270", 1, None, "WPS", "SIZE-WPS-116050-SPEC-HC-X", "high",
     None),
    ("10", "16", "320", 1, None, "RWS", "SIZE-RWS-116055-SPEC-HC-X", "high",
     None),
    ("10", "24", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121071-SPEC-HC-X",
     "high", None),
    ("10", "45", "100", 1, None, "RCS", "SIZE-CVCS-110053-SPEC-HC-X", "high",
     "flag service RCS but line label prefix CVCS"),
    ("10", "94", "320", 1, None, "CAS", None, "medium",
     "the two nearby labels SIZE-CVCS-116042-SPEC-HC-X and "
     "SIZE-CVCS-116041-SPEC-HC-X both have leader lines to other branches, "
     "not to this flag's run, which joins a bold vertical header"),
    ("10", "149", "270", 1, None, "WPS", "SIZE-WPS-111058-SPEC-HC-X", "high",
     None),
    ("10", "193", "300", 1, None, None, None, "high",
     "flag reads PID 300-1 / MAKE-UP WATER with no service abbreviation; no "
     "line-number label on the run into CVCS-VCT-118 nozzle N2"),
    ("10", "195", "320", 1, None, "RWS", "SIZE-RWS-116052-SPEC-HC-X", "high",
     "leader line from the label points to the segment between N3 and "
     "LCV 1161 on this flag's own run"),
    ("10", "196", "100", 1, "C-1", "RCS", "SIZE-CVCS-101022-SPEC-HC-X",
     "high", "flag service RCS but line label prefix CVCS"),

    # ---- sheet 11 -----------------------------------------------------------
    ("11", "18", "100", 1, None, "RCS", "SIZE-RHRS-121A072-SPEC-HC-X", "high",
     "flag text RES HEAT REMOVAL SYSTEM / RCS PID 100-1; a branch through "
     "MOV 1216 leaves just upstream but the label is on the segment that "
     "enters the flag"),
    ("11", "22", None, None, None, None, None, "medium",
     "single-line flag reading REACTOR WATER SERVICE TANK - a bare equipment "
     "name with no PID number, no sheet reference and no grid cell; no "
     "line-number label on its run either"),
    ("11", "23", "100", 1, "H-1", "RCS", "SIZE-RHRS-100021-SPEC-HC-X", "high",
     "explicit leader line runs from the label to this flag's own pipe"),
    ("11", "109", "100", 1, None, "RCS", "SPEC-RHRS-121A065-SPEC-HC-X",
     "medium",
     "label uses the SPEC- prefix and is printed twice: rotated along the "
     "vertical riser that feeds this flag, and again horizontally beside a "
     "downward branch; the supply run also has a merge, so attribution is "
     "probable rather than certain"),
    ("11", "118", "110", 1, None, "CVCS", "SIZE-RHRS-121071-SPEC-HC-X",
     "high", "flag service CVCS but line label prefix RHRS"),
    ("11", "127", "100", 1, None, "RCS", "SIZE-RHRS-121073-SPEC-HC-X", "high",
     None),
    ("11", "128", "110", 1, None, "CVCS", None, "high",
     "run leaves the flag rightward then turns up with no label; the nearby "
     "verticals SIZE-RHRS-100060 and SIZE-RHRS-100061 are different lines"),
)

assert len(ROWS) == 71, len(ROWS)
