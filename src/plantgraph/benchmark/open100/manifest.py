"""Assemble the final OPEN100 answer key from the labels that were read off the drawings.

Stage 2's steps, condensed here:

  1. attach the read-off label to every connector (annotations.py),
  2. connectors referencing a target are either paired up (PAIRS — identified by
     hand, see below), recorded as dangling (the target sheet is not in the
     corpus), or left unresolved (the target sheet exists, but no matching
     connector was found on it),
  3. check that all 96 connectors' fate is known — SplitManifest.accounted_for().

**The pairing is manual work, not an algorithm.** The design note describes a
ranked matching rule (line_number -> grid cell -> service+direction); here that
ranking was applied by hand, row by row, while reading the labels — not by a
runnable matcher. The PAIRS list is the record of that decision, and each row's
match_rule states how unambiguous it was.
"""

from __future__ import annotations

from plantgraph.benchmark.models import (
    ConnectorObservation,
    ConnectorPair,
    DanglingReference,
    MatchRule,
    SheetRef,
    SplitManifest,
    UnresolvedConnector,
)
from plantgraph.benchmark.open100.annotations import ANNOTATIONS, RawConnectorText
from plantgraph.benchmark.open100.sheets import KNOWN_ABSENT, SHEETS, resolve

SOURCE_NAME = "PID2Graph/OPEN100"

# (from_key, to_key, match_rule, note)
# Pairs identified by hand from reading the montages, 2026-08-31.
PAIRS: tuple[tuple[str, str, MatchRule, str | None], ...] = (
    ("0:inlet/outlet83", "1:inlet/outlet3", MatchRule.GRID_MUTUAL, "1/3 shows no line number; only the mutual sheet reference (0→ACC-150-1, 1→MSS-140-1) confirms it. 1/3 reads E-1, 0/83 sits in row D (right edge) — off by one row"),
    ("1:inlet/outlet24", "2:inlet/outlet13", MatchRule.LINE_NUMBER, "line number matches (160090); 1/24 reads F-1, but 2/13 sits on sheet 2's LEFT edge, in row G — the grid reference is off in both row and column here"),
    ("2:inlet/outlet96", "4:inlet/outlet41", MatchRule.LINE_NUMBER, "number 165117 also occurs on the dangling 2/17 (a different target) — the number alone isn't unique here, target mutuality is needed too"),
    ("0:inlet/outlet79", "4:inlet/outlet43", MatchRule.LINE_NUMBER, "different prefix (ES/ESS), same number; 140083 also occurs once more on sheet 0 as FWS-140083 (0/84, a different pipe) — here the mutual sheet reference (0→180-1, 4→140-1) decides, the number only confirms"),
    ("5:inlet/outlet38", "11:inlet/outlet23", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet43", "6:inlet/outlet31", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet45", "10:inlet/outlet196", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet46", "6:inlet/outlet27", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet47", "10:inlet/outlet45", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet49", "11:inlet/outlet127", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet54", "11:inlet/outlet18", MatchRule.LINE_NUMBER, "line number matches; 5/54 reads E-1, but 11/18 sits in row F — the grid reference is off by one row"),
    ("5:inlet/outlet78", "6:inlet/outlet16", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet114", "10:inlet/outlet14", MatchRule.LINE_NUMBER, "line number matches, and 5/114's grid cell G-12 is exactly 10/14's position; BUT 10/14's own label reads PID 120-1 (RHR), not 100-1 — a contradiction in the source drawing, two independent signals against the one label"),
    ("5:inlet/outlet124", "11:inlet/outlet109", MatchRule.LINE_NUMBER, "a genuine typo: 'SPEC-' instead of 'SIZE-', on both sides; 11/109 sits on the E/D row boundary, 5/124 reads D-1 — consistent"),
    ("6:inlet/outlet28", "8:inlet/outlet13", MatchRule.LINE_NUMBER, "211158 read directly on both sides (2026-09-05)"),
    ("6:inlet/outlet30", "8:inlet/outlet12", MatchRule.LINE_NUMBER, None),
    ("10:inlet/outlet24", "11:inlet/outlet118", MatchRule.LINE_NUMBER, "line number matches; 10/24 reads C-1, but 11/118 sits in row D — the grid reference is off by one row"),
    ("1:inlet/outlet73", "2:inlet/outlet16", MatchRule.LINE_NUMBER, "different prefix (CND/COND), same number — the user found the missing line number; 2/16 reads C-12, 1/73 sits on sheet 1's left edge on the D/E row boundary — column correct, row off by one or two"),
    ("0:inlet/outlet84", "3:inlet/outlet82", MatchRule.GRID_MUTUAL, "different line numbers, based only on the sheets' mutual reference"),
    ("7:inlet/outlet75", "8:inlet/outlet7", MatchRule.LINE_NUMBER, "SIZE-ACW-211152-SPEC-HC-X on both sides — found by an independent re-reading; replaces the earlier (weaker) 8/54-7/75 pairing"),
    ("6:inlet/outlet40", "8:inlet/outlet31", MatchRule.LINE_NUMBER, "SIZE-ACW-102160-SPEC-HC-X on both sides — the line number on 6/40's side was found by an independent re-reading on a wider crop; previously this was service_direction"),
    ("6:inlet/outlet41", "8:inlet/outlet32", MatchRule.SERVICE_DIRECTION, "paired by elimination, no line number readable on either side — an independent re-reading also confirmed there is no line number on 6/41"),
    ("7:inlet/outlet33", "8:inlet/outlet54", MatchRule.SERVICE_DIRECTION, "paired by elimination on 2026-09-05: 7/33 is the only free flag incoming from 210-2 on sheet 7, 8/54 is the only one going out to 210-1 on sheet 8; the line numbers do not match (FWS-175271 vs. the header pipe's 111156), and 7/33's grid cell (F-1) points to the OTHER end of the header pipe (8/5) — the source drawing contradicts itself, hence the weakest tier"),
)

# No IDENTITY_GROUPS in this file. The RCS-PU-102A/102B identity (sheet 5's
# flow diagram <-> sheet 6's DETAIL A/B) is visually confirmed, but has no real
# graphml node behind it: all six "pump"-labelled nodes on sheet5 are verified
# to be flow elements (FE/FT), not the pump body, and sheet6 has no
# "pump"-labelled node at all. Inventing a key for an IdentityGroup would be
# exactly the mistake already made and fixed once before (see
# 50-progress/2026-W35.md). Until a real node exists, this finding stays as
# text — see open100-annotation.md open question 1.


def _dangling_reason(pid: str | None) -> str:
    """A human-readable reason for a dangling reference, if we know the system's name."""
    name = KNOWN_ABSENT.get(pid or "")
    if name is None:
        return "target sheet not present in corpus"
    return f"target sheet not present in corpus ({name})"


def _classify(raw: RawConnectorText, paired_keys: set[str]) -> tuple[str, object]:
    """Decide which of the three fates (paired / dangling / unresolved) a connector falls into.

    The "paired" cases have already been filtered out by the caller
    (paired_keys) — this function only classifies the remainder by the label:
    is there a resolvable target?
    """
    if raw.key in paired_keys:
        return "paired", None
    if raw.target_pid is None:
        return "unresolved", UnresolvedConnector(
            from_key=raw.key, reason=raw.note or "no P&ID reference on the label"
        )
    target = SheetRef(pid=raw.target_pid, sheet_no=raw.target_sheet_no or 1)
    if resolve(target) is None:
        return "dangling", DanglingReference(
            from_key=raw.key, target=target, reason=_dangling_reason(raw.target_pid)
        )
    reason = raw.note or "target sheet exists but no matching connector was found on it"
    return "unresolved", UnresolvedConnector(from_key=raw.key, reason=reason)


def build_manifest(observations: list[ConnectorObservation]) -> SplitManifest:
    """Merge the geometry (stage 1) and the labels (annotations.py) into one manifest."""
    by_key = {raw.key: raw for raw in ANNOTATIONS}
    enriched = [_enrich(obs, by_key[obs.key]) for obs in observations]

    paired_keys = {frm for frm, _, _, _ in PAIRS} | {to for _, to, _, _ in PAIRS}
    dangling: list[DanglingReference] = []
    unresolved: list[UnresolvedConnector] = []
    for raw in ANNOTATIONS:
        bucket, entry = _classify(raw, paired_keys)
        if bucket == "dangling":
            dangling.append(entry)  # type: ignore[arg-type]
        elif bucket == "unresolved":
            unresolved.append(entry)  # type: ignore[arg-type]

    pairs = [
        ConnectorPair(from_key=frm, to_key=to, match_rule=rule, note=note)
        for frm, to, rule, note in PAIRS
    ]

    return SplitManifest(
        source=SOURCE_NAME,
        sheet_files=sorted(SHEETS, key=int),
        connectors=enriched,
        connector_pairs=pairs,
        dangling=dangling,
        unresolved=unresolved,
    )


def _enrich(obs: ConnectorObservation, raw: RawConnectorText) -> ConnectorObservation:
    """Attach the read-off label onto the geometric observation."""
    target = None
    if raw.target_pid is not None:
        target = SheetRef(pid=raw.target_pid, sheet_no=raw.target_sheet_no or 1)
    return obs.model_copy(
        update={
            "target": target,
            "grid_cell": raw.target_grid,
            "service": raw.service,
            "line_number": raw.line_number,
        }
    )


__all__ = ["build_manifest", "PAIRS"]
