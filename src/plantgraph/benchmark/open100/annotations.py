"""Labels for the 96 OPEN100 connectors — read off the montages.

This is stage 2's raw material: stage 1 (extract.py, crops.py) only found the
connectors and produced images of them. Here we record what each one *says* —
which sheet it references, which grid cell, which service code ("RCS", "CVCS",
"ACW", ...), and which line number.

**How this was read, and how reliable it is.** The labels were read off the
montage images on 2026-08-31 — not OCR, but visual reading, as the design note
(open100-annotation.md) recommended. This does **not** replace the manual
review the design note calls for: small, similar-looking number sequences (e.g.
the ACW-211150 series) can be misread. The `note` field flags where confidence
is lower — there, manifest.py assigns the weaker `MatchRule`, and final
verification remains the user's job.

One row's fields:
  sheet, node          — the connector's key (see ConnectorObservation.key)
  target_pid, target_sheet_no, target_grid — what it references; None if the
      label has no recognizable P&ID reference (see 11/22: an equipment name, not a sheet)
  service              — the label's short system code (e.g. "RHRS", "ACW")
  line_number          — the pipe segment's label, if it was visible on the crop
  note                 — anything needed for pairing or for judging reliability
"""

from __future__ import annotations

from pydantic import BaseModel


class RawConnectorText(BaseModel):
    """A connector's label as read off, before pairing."""

    sheet: str
    node: str
    target_pid: str | None
    target_sheet_no: int | None
    target_grid: str | None
    service: str | None
    line_number: str | None
    note: str | None

    @property
    def key(self) -> str:
        """The same key ConnectorObservation.key produces — this is how the two tables join."""
        return f"{self.sheet}:inlet/outlet{self.node}"


# sheet, node, target_pid, target_sheet_no, target_grid, service, line_number, note
_ROWS: tuple[
    tuple[str, str, str | None, int | None, str | None, str | None, str | None, str | None], ...
] = (
    # --- sheet 0: Main Steam System (PID 140) ---
    ("0", "79", "180", 1, None, "ES", "SIZE-ES-140083-SPEC-HC-X", None),
    ("0", "80", "240", 1, None, "TBS", "SIZE-MSS-140076-SPEC-HC-X", None),
    ("0", "81", "240", 1, None, "TBS", "SIZE-MSS-140077-SPEC-HC-X", None),
    ("0", "82", "190", 1, None, "HPD", "SIZE-HPSD-140082-SPEC-HC-X", None),
    ("0", "83", "150", 1, None, "ACC", "SIZE-MSS-140081-SPEC-HC-X", None),
    ("0", "84", "170", 1, None, "FWS", "SIZE-FWS-140083-SPEC-HC-X", None),
    ("0", "85", "190", 1, None, "HPD", "SIZE-HPSD-140080-SPEC-HC-X", None),
    ("0", "86", "190", 1, None, "HPD", "SIZE-HPSD-140079-SPEC-HC-X", None),
    ("0", "87", "190", 1, None, "HPD", "SIZE-HPSD-140078-SPEC-HC-X", None),
    # --- sheet 1: Air Cooled Condenser (PID 150) ---
    ("1", "3", "140", 1, "E-1", "MSS", None, "no line number on the crop — only a DETAIL marker (bell, dashed circle, wheel); the pairing with 0/83 rests only on the mutual sheet reference"),
    ("1", "5", "160", 1, None, "CND", "SIZE-ACC-150098-SPEC-HC-X", "the DETAIL A SECTION VIEW shows the same LCV 1501 + LIT 25094A/B node as 1/73 in the main view — so this is a repeated drawing of the same connection, not a second pipe; the detail view prints 150098, the main view 150104 (a discrepancy in the source drawing). Stays unresolved, because 2/16 is already 1/73's pair"),
    ("1", "22", "190", 1, None, "HPD", None, None),
    ("1", "24", "160", 1, "F-1", "CND", "SIZE-ACC-160090-SPEC-HC-X", None),
    ("1", "47", "250", 1, None, "TURB", None, "an incoming-style label, yet there is no grid cell — a genuine inconsistency in the source"),
    ("1", "73", "160", 1, None, "CND", "SIZE-COND-150104-SPEC-HC-X", None),
    # --- sheet 2: Condensate System (PID 160) ---
    ("2", "13", "150", 1, None, "ACC", "SIZE-ACC-160090-SPEC-HC-X", None),
    ("2", "14", "170", 2, "E-1", "FWS", "SIZE-FWS-175271-SPEC-HC-X", "line number collides with 7/33, probably a coincidental match"),
    ("2", "15", "200", 4, None, "WTS", "SIZE-WTS-275235-SPEC-HC-X", None),
    ("2", "16", "150", 1, "C-12", "CND", "SIZE-CND-150104-SPEC-HC-X", None),
    ("2", "17", "240", 1, "E-12", "ESS", "SIZE-ESS-165117-SPEC-HC-X", "dangling target, so the line number doesn't matter; the neighbouring SIZE-COND-161115 belongs to a different pipe, unrelated to this one — the user caught the earlier misreading"),
    ("2", "88", "290", 1, None, "WWS", None, None),
    ("2", "93", "270", 1, None, "WPS", None, None),
    ("2", "95", "240", 1, None, "MSS", "SIZE-COND-161114-SPEC-HC-X", None),
    ("2", "96", "180", 1, None, "ESS", "SIZE-ESS-165117-SPEC-HC-X", None),
    ("2", "97", "290", 1, None, "WSS", "SIZE-WSS-167118-SPEC-HC-X", None),
    # --- sheet 3: Feedwater System (PID 170) ---
    ("3", "16", "170", 2, None, "FWS", "SIZE-FWS-161131-SPEC-HC-X", None),
    ("3", "82", "140", 1, None, "MSS", "SIZE-MSS-170133-SPEC-HC-X", "line number differs from 0/84's, only the mutual sheet reference pairs them"),
    ("3", "89", "290", 1, None, "WSS", "SIZE-WSS-170134-SPEC-HC-X", None),
    # --- sheet 4: Extraction Steam System (PID 180) ---
    ("4", "16", "260", 1, None, "PDS", "SIZE-PDS-165139-SPEC-HC-X", None),
    ("4", "39", "190", 1, None, "HPSD", "SIZE-HPSD-166140-SPEC-HC-X", None),
    ("4", "41", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", None),
    ("4", "42", "200", 4, None, "WTS", None, None),
    ("4", "43", "140", 1, None, "MSS", "SIZE-ESS-140083-SPEC-HC-X", None),
    ("4", "48", "240", 1, "D-1", "TBS", "SIZE-ESS-250137-SPEC-HC-X", None),
    ("4", "104", "240", 1, "E-1", "TBS", "SIZE-ESS-250136-SPEC-HC-X", None),
    ("4", "117", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", "NOT a duplicate detection: a separate flag at the top of the sheet (towards TCV 16013), while 4/41 goes into CND-HTR-166 N9; the source drawing printed the same line number on two separate pipes — confirmed by a third reading on 2026-09-05"),
    # --- sheet 5: Reactor Coolant System, sheet 1/2 (PID 100) ---
    ("5", "12", "290", 1, None, "WSS", "SIZE-WS-101024-SPEC-HC-X", None),
    ("5", "38", "120", 1, None, "RHRS", "SIZE-RHRS-100021-SPEC-HC-X", None),
    ("5", "43", "100", 2, None, "RC", "SIZE-RCS-101006-SPEC-HC-X", "the flag reads RC-PID-100-2 (the sheet's other references read RCS-PID-100-2) — recorded exactly as printed"),
    ("5", "45", "110", 1, None, "CVCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    ("5", "46", "100", 2, None, "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("5", "47", "110", 1, "H-12", "CVCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("5", "49", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121073-SPEC-HC-X", None),
    ("5", "54", "120", 1, "E-1", "RHRS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("5", "78", "100", 2, None, "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("5", "86", "290", 1, None, "WSS", "SIZE-WSS-100023-SPEC-HC-X", None),
    ("5", "114", "110", 1, "G-12", "CVCS", "SIZE-CVCS-115C049-SPEC-HC-X", "grid cell G-12 points exactly to 10/14's position, and the line number matches too; but 10/14's own target text clearly reads PID 120-1 (RHR), not 100-1 — a contradiction in the source drawing, see the pair's note"),
    ("5", "124", "120", 1, "D-1", "RHRS", "SPEC-RHRS-121A065-SPEC-HC-X", "a genuine typo in the source: 'SPEC-' instead of 'SIZE-'"),
    # --- sheet 6: Reactor Coolant System, sheet 2/2 (PID 100) — the pump-detail sheet ---
    ("6", "16", "100", 1, "G-1", "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("6", "27", "100", 1, "C-1", "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("6", "28", "210", 2, "C-1", "ACW", "SIZE-ACW-211158-SPEC-HC-X", "DETAIL B — identity evidence for RCS-PU-102B; 211158 is read directly off the vertical label (2026-09-05, wide crop), not inferred"),
    ("6", "30", "210", 2, "C-1", "ACW", "SIZE-ACW-211157-SPEC-HC-X", "DETAIL A — identity evidence for RCS-PU-102A"),
    ("6", "31", "100", 1, "D-1", "RCS", "SIZE-RCS-101006-SPEC-HC-X", None),
    ("6", "40", "210", 2, None, "ACW", "SIZE-ACW-102160-SPEC-HC-X", "a nearby label reads COOLANT HT EXCH RC-P100-X001 — a third spelling of the pump's name; the line number was found by an independent re-reading on a wider crop"),
    ("6", "41", "210", 2, None, "ACW", None, "the same COOLANT HT EXCH RC-P100-X001 label"),
    ("6", "68", "320", 1, None, "RWS", "SIZE-RWS-104025-SPEC-HC-X", None),
    ("6", "69", "130", 1, None, "SWS", "SIZE-SWS-132172-SPEC-HC-X", None),
    ("6", "71", "320", 1, None, "RWS", None, None),
    # --- sheet 7: Aux Cooling Water System, sheet 1/2 (PID 210) ---
    ("7", "30", "170", 2, None, "FWS", "SIZE-ACW-175271-SPEC-HC-X", "corrected after an independent re-reading (211152 was recorded here by mistake — that number actually belongs to 7/75); the number 175271 also occurs on 2/14 and 7/33 with a different prefix, so it is not unique here on its own"),
    ("7", "31", "170", 2, None, "FWS", "SIZE-ACW-211270-SPEC-HC-X", None),
    ("7", "32", "240", 1, None, "TBS", "SIZE-ACW-250261-SPEC-HC-X", None),
    ("7", "33", "210", 2, "F-1", "ACW", "SIZE-FWS-175271-SPEC-HC-X", "the flag reads ACW (the line's FWS prefix was mistakenly recorded here earlier); line number collides with 2/14 and 7/30. Grid cell (F-1) points to row F at the right edge of sheet 8 — that is where 8/5 sits, whose own label reads SWS PID 130-1; sheet 8's only flag going out to 210-1 is 8/54, at the left end of the same row-F header pipe. 2026-09-05: paired with 8/54 by elimination (service_direction), see the pair's note"),
    ("7", "34", "160", 1, None, "WTS", None, "the flag reads WTS PID 160-1 / MAKE-UP WATER; sheet 160 (sheet 2) has no flag pointing to 210, and every other MAKE-UP WATER flag references drawing WTS PID 200-x — probably a mistyped drawing number (160 instead of 200). The 'FCV XXX' placeholder also shows the drawing is unfinished here. Cannot be resolved, stays unresolved"),
    ("7", "35", None, None, None, None, None, "unreadable crop; the box is unusually narrow (~17px) — possibly a falsely detected node; an independent re-reading confirmed this too: not a connector, but a nozzle/flange symbol with no text"),
    ("7", "75", "210", 2, None, "ACW", "SIZE-ACW-211152-SPEC-HC-X", "the line number was found by an independent re-reading; this pairs it with 8/7 (211152 appears on both sides)"),
    ("7", "76", "250", 1, None, "TBS", "SIZE-ACW-211153-SPEC-HC-X", None),
    # --- sheet 8: Aux Cooling Water System, sheet 2/2 (PID 210) ---
    ("8", "5", "130", 1, None, "SWS", "SIZE-ACW-111162-SPEC-HC-X", "the flag reads SWS, the line's prefix is ACW; this is the right end of the straight row-F header pipe, its left end is 8/54 — two outgoing flags on one pipe, with two vertical feeds"),
    ("8", "6", "130", 1, None, "SWS", "SIZE-SWS-130182-SPEC-HC-X", None),
    ("8", "7", "210", 1, "A-1", "ACW", "SIZE-ACW-211152-SPEC-HC-X", "paired with 7/75 (see there) after an independent re-reading"),
    ("8", "12", "100", 2, None, "RCS", "SIZE-ACW-211157-SPEC-HC-X", "the flag reads RCS, the line's prefix is ACW"),
    ("8", "13", "100", 2, None, "RCS", "SIZE-ACW-211158-SPEC-HC-X", "the flag reads RCS, the line's prefix is ACW; a branch joins before the label, but the label sits on the final segment running into the flag"),
    ("8", "15", "130", 1, None, "SWS", "SIZE-ACS-102163-SPEC-HC-X", "corrected: 270/WPS was recorded here by mistake earlier (swapped with 8/16), per an independent re-reading; the line number sits on a merging header pipe and cannot be tied to one unique source"),
    ("8", "16", "270", 1, None, "WPS", "SIZE-ACW-111164-SPEC-HC-X", "corrected: 130/ACW was recorded here by mistake earlier (swapped with 8/15), per an independent re-reading"),
    ("8", "17", "130", 1, None, "SWS", "SIZE-SWS-132181-SPEC-HC-X", None),
    ("8", "31", "100", 2, "C-1", "RCS", "SIZE-ACW-102160-SPEC-HC-X", "the flag reads RCS, the line's prefix is ACW"),
    ("8", "32", "100", 2, "A-4", "RCS", "SIZE-ACW-102161-SPEC-HC-X", "the flag reads RCS, the line's prefix is ACW; grid cell A-4, not the usual edge column"),
    ("8", "54", "210", 1, None, "ACW", None, "111156 sits on the straight row-F header pipe that runs from 8/54 to 8/5 with two vertical feeds and an outgoing flag at each end — it cannot be tied to this connector alone; its earlier pair (7/75) went to 8/7 instead. 2026-09-05: paired with 7/33 by elimination (service_direction), see there"),
    # --- sheet 9: Residual Heat Removal System, sheet 2/2 (PID 120) ---
    ("9", "2", "120", 1, None, "RHR", None, "a one-way reference: sheet 9 (RHR 120-2) references sheet 120-1 through this connector and 9/59, but not one flag on sheet 11 (120-1) references back to 120-2 — sheet 9's collector/distributor header pipes (every instrument marked XXX) are not drawn on the other side. Nothing to pair"),
    ("9", "59", "120", 1, None, "RHR", None, "same as 9/2 — a one-way reference, sheet 11 has no flag pointing back"),
    # --- sheet 10: Chemical Volume Cooling Water (PID 110) ---
    ("10", "14", "120", 1, None, "RHR", "SIZE-CVCS-115C049-SPEC-HC-X", "target text is clearly legible: PID 120-1 / RHR (2026-09-05). This contradicts the pairing with 5/114, which rests on the matching line number and grid cell G-12; an alternative pair would be 11/128 (CVCS PID 110-1, incoming, no line number)"),
    ("10", "15", "270", 1, None, "WPS", "SIZE-WPS-116050-SPEC-HC-X", None),
    ("10", "16", "320", 1, None, "RWS", "SIZE-RWS-116055-SPEC-HC-X", None),
    ("10", "24", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121071-SPEC-HC-X", None),
    ("10", "45", "100", 1, None, "RCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("10", "94", "320", 1, None, "CAS", None, "under a different name (CAS) than the other references to PID 320 (RWS) — unresolvable either way"),
    ("10", "149", "270", 1, None, "WPS", "SIZE-WPS-111058-SPEC-HC-X", None),
    ("10", "193", "300", 1, None, None, None, "the flag only reads PID 300-1 / MAKE-UP WATER, with no system code — the earlier WTS reading was not actually on the drawing"),
    ("10", "195", "320", 1, None, "RWS", "SIZE-RWS-116052-SPEC-HC-X", "the line number was found by an independent re-reading; the target is dangling, so it does not affect pairing"),
    ("10", "196", "100", 1, "C-1", "RCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    # --- sheet 11: Residual Heat Removal System, sheet 1/2 (PID 120) ---
    ("11", "18", "100", 1, None, "RCS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("11", "22", None, None, None, None, None, "'REACTOR WATER SERVICE TANK' — an equipment name, the label carries no P&ID reference. 2026-09-05: we checked all 12 sheets' equipment lists (bottom strip); no tank of this name appears on any of them — the tank is outside the corpus, but without a drawing number we cannot tell which sheet it is on"),
    ("11", "23", "100", 1, "H-1", "RCS", "SIZE-RHRS-100021-SPEC-HC-X", None),
    ("11", "109", "100", 1, None, "RCS", "SPEC-RHRS-121A065-SPEC-HC-X", None),
    ("11", "118", "110", 1, None, "CVCS", "SIZE-RHRS-121071-SPEC-HC-X", None),
    ("11", "127", "100", 1, None, "RCS", "SIZE-RHRS-121073-SPEC-HC-X", None),
    ("11", "128", "110", 1, None, "CVCS", None, "none of sheet 10's free outgoing connectors fit here"),
)

ANNOTATIONS: tuple[RawConnectorText, ...] = tuple(
    RawConnectorText(
        sheet=sheet,
        node=node,
        target_pid=target_pid,
        target_sheet_no=target_sheet_no,
        target_grid=target_grid,
        service=service,
        line_number=line_number,
        note=note,
    )
    for sheet, node, target_pid, target_sheet_no, target_grid, service, line_number, note in _ROWS
)
