---
component: benchmark/open100
status: draft — ready to implement
related: [ADR-0005, ADR-0004, splitter.md]
date: 2026-08-25
---

# Design — OPEN100 cross-sheet annotation

Recover the cross-sheet ground truth that exists in the OPEN100 images but is missing from its GraphML, and emit it in the **same manifest format the synthetic splitter produces**. Downstream code must not be able to tell the two sources apart.

## 1. Input and output

**In**
- 12 `{0..11}.png` — the drawings (`C:\Users\b.kiszely\Desktop\Projects\Work Done\PID2Graph\Complete\PID2Graph OPEN100` — moved here 2026-09-05; `Patched/` beside it holds the tiled variant)
- 12 `{0..11}.graphml` — per-sheet graphs; nodes carry `label` + bbox only
- The sheet→PID map established 2026-08-25 (see `10-literature/pid2graph.md`)

**Out**
- `open100_manifest.json` — a `SplitManifest` (schema from `splitter.md`), with `connector_pairs` as the gold set
- `open100_connectors.csv` — the intermediate per-connector table, human-checkable

## 2. What the spike established

Bounding boxes are in **image pixel space** (max equals image size — no rescaling needed). The 96 `inlet/outlet` boxes tightly enclose the connector flag **including its label**. The line number sits just outside on the pipe; a margin of ~3× box width captures it.

**Two label grammars, and the asymmetry matters:**

| Direction | Edge | Format | Example |
|---|---|---|---|
| **Incoming** | left | `PID <pid>-<sheet> (<grid>)` / `<SERVICE>` | `PID 120-1 (C-1)` / `RHRS` |
| **Outgoing** | right | `<SYSTEM NAME>` / `<SVC>-PID-<pid>-<sheet>` | `REACTOR COOLANT SYSTEM` / `RCS-PID-100-2` |

Only **incoming** connectors carry the grid cell. So an incoming connector states "I arrive from sheet 120-1, cell C-1" — and the pairing rule follows from that.

Formatting is inconsistent in the real data (`PID-120-01` vs `PID 120-1`). Normalize; do not assume.

## 3. Pipeline

1. **Parse** each GraphML, select `label == "inlet/outlet"` nodes (96 across 12 sheets).
2. **Crop** twice per connector: the bbox alone (label) and bbox + 3× width margin (line number).
3. **Read** the crops. Montage ~12 per image and read them with a vision model — the spike did exactly this successfully, so no OCR library or training is needed.
4. **Parse** text into `raw_text`, `target_pid`, `target_sheet`, `grid_cell`, `service`, `line_number`, `direction`.
5. **Resolve** `target_pid` + `target_sheet` → one of the 12 files, or mark `dangling` (PID 190, 240, 290 are expected here).
6. **Pair.** Match on **`line_number` first** — the strongest signal, and it should appear on both sheets. Confirm with grid cell: an incoming connector on sheet A citing `(C-1)` of sheet B must match an outgoing connector in grid cell C-1 of sheet B. Grid cells are derived from the drawing border (A–H vertical, 1–12 horizontal) by linear interpolation over image dimensions.

   **⚠ Line numbers are not always capturable** (observed 2026-08-25 on the first montage). Some connectors print the line number well away from the flag, outside a 3× crop; connector `1/3` on sheet 1 has none in view while `5/47` on sheet 5 does. So pairing **cannot require** it. Ranked fallback:
   1. `line_number` exact match — trust it
   2. target sheet + grid cell, mutually consistent from both ends
   3. target sheet + service code + direction — weakest, flag for human review

   Every pair records which rule produced it, so the weak ones can be audited separately rather than blending into the gold set.
7. **Verify by hand.** All 96, against the crops. This is small enough to check exhaustively, and exhaustive checking is what makes it citable.
8. **Emit** the manifest.

## 4. Data model

Reuse `plantgraph.benchmark.models` from the splitter. One addition:

- **`ConnectorObservation`** — the raw annotation record: `sheet_file`, `node_id`, `bbox`, `direction`, `raw_text`, parsed fields, `confidence`, `verified_by_human: bool`

`ConnectorPair` and `SplitManifest` are unchanged. Keeping one schema for both producers is the point of the design.

## 5. How it is tested

- **Symmetry** — every resolved pair is found from both ends; a link appearing on only one sheet is an error to investigate, not to silently drop.
- **Conservation** — every one of the 96 connectors ends up either paired or explicitly `dangling`. None disappear.
- **Dangling set matches expectation** — PID 190, 240, 290, and PID 170 sheet 2 of 2 absent.
- **Grid resolution** — spot-check that interpolated grid cells match the printed border on several sheets.
- **Schema** — the manifest validates against the same Pydantic model as splitter output.
- Parsers are pure functions over strings: unit-test the label grammars directly, including the malformed real cases.

## 6. How it reports accuracy

It *is* the yardstick, not a measured component. Its own quality is defended by the exhaustive human verification pass and by publishing the crops next to the labels so a reader can audit any row.

Once built it scores: cross-sheet connector linking (EXP-0004) on **real** drawings, and abstention (EXP-0005) using the naturally dangling references.

## 7. Which part of the claim it serves

The realism defence. The synthetic generator carries the scale claim; this carries the answer to *"but does any of this hold on real drawings?"*

## Open questions

1. ~~**Do equipment tags repeat across sheets?**~~ — **answered 2026-08-25 by inspection: yes, verified.** `RCS-PU-102A` and `RCS-PU-102B` appear on **sheet 5** (in the process flow) and again on **sheet 6** (as "DETAIL A" and "DETAIL B", detailed views of the same pumps). Sheet 5 also carries `DET A SHT 2` / `DET B SHT 2` callouts pointing at them — an explicit, machine-readable identity link.

   **So OPEN100 gives real tag-identity ground truth as well as connector ground truth**, and annotating it costs little extra since the sheets are already in hand. Add these to the manifest as `IdentityGroup` entries.

   Two related observations, kept separate because only one is verified:
   - **Verified:** tag spelling varies *within* a sheet — sheet 5's pump symbol reads `RCS-PU-102A` while its own equipment schedule lists `RC-P102A` for the same machine. A third style appears on sheet 6: `COOLANT HT EXCH RC-P100-X001`.
   - **Not observed:** the same tag spelled differently on two *different* sheets. Do not assume it; the splitter's tag-variant generation should treat it as a hypothesis to test, not a fact to reproduce.
2. **Grid interpolation or detection?** Interpolating from image dimensions assumes a constant border margin across sheets. Verify before relying on it; fall back to detecting the printed border ticks. **Still open as of 2026-08-31** — stage 2 was completed without it, using line-number matching as the primary signal instead; a handful of pairs (see `match_rule: service_direction` in the manifest) would benefit from an independent grid check once this exists.
3. **Release form.** Annotation only (CC BY-SA, small), or bundled with images (9.3 GB source, share-alike either way)? Prefer annotation-only plus a script that fetches PID2Graph.

## Stage 2 result (2026-08-31)

All 96 connectors read from the montages and classified: **21 paired** (17 `line_number`, 1 `grid_mutual`, 3 `service_direction`), **42 dangling** (10 distinct target systems outside the 12 sheets — see `sheets.KNOWN_ABSENT`, extended today from 3 to 8 entries), **12 unresolved** (target sheet exists but no matching connector found, or the label itself doesn't resolve). `SplitManifest.accounted_for()` is `True` — every connector's fate is recorded, but "recorded" is not the same as "resolved"; the unresolved 12 and the weaker pairs are real open items, not corner cases to be quietly dropped.

**This reading was done by a Claude model looking at the crops, not the human verification pass this document specifies in step 7.** Treat `open100_connectors.csv`'s `note` column as the list of what still needs a second look, especially the `ACW-2111xx` series on sheets 7/8, where several very similar-looking line numbers made confident reading difficult.

**New finding: a shared header's label is not any connector's line number.** Sheet 1's four incoming lines (HPD-190, MSS-140, TURB-250, CND-160) don't run in independent lanes — they converge into one junction ("SEE DETAIL A THIS DWG") before feeding the fin-fan cooler array, and the labels at/after that convergence (`SIZE-TBS-100/101/102/103-SPEC`) belong to the merged downstream header, not to any one of the four original connectors. Using one of those as a connector's `line_number` would silently mix up unrelated pipes. The fixed-margin crop (`expanded(x_factor=3.0, y_margin=25)`, `crops.py`) was built for the common case — one flag, one straight line, one label beside it — and simply doesn't produce a usable line number at a merge point; the correct response is to leave `line_number` empty and fall back to target+grid matching (`MatchRule.GRID_MUTUAL`), not to grab the nearest text. Caught two real cases this way (`0/83`↔`1/3` downgraded from a false line match; `1/73`↔`2/16` recovered a genuine line the crop had put next to the wrong row) while checking the manifold region by hand against the full sheet.

**New finding: the `"pump"` label is not reliable.** Sheet 5's six graphml nodes labeled `"pump"` are all flow-element (FE) instrument bubbles, confirmed by cropping and reading their tags (`FE`/`FT-10xx`). Sheet 6 has no `"pump"`-labeled node at all. The RCS-PU-102A/102B cross-sheet identity (sheet 5 process flow ↔ sheet 6 "DETAIL A/B") remains visually confirmed but has no real graphml node to anchor an `IdentityGroup` to — recorded here in prose instead of as fabricated model data.

## Third read of sheets 3–11 (2026-09-05)

A second Claude model (Fable) re-read all 71 sheet 3–11 connectors from fresh wide crops (6× width, 80 px margin, plus tall/region crops where a line ran vertically) cut directly from the source PNGs at their new location. Targets, sheet numbers, grid cells and line numbers agree with the post-Opus `annotations.py` on all 71 rows. The differences were all in the `service` column and in notes, and were applied the same day:

- **`service` on an incoming flag is the *target* system's code, not the line prefix.** Five sheet 8 rows (8/5, 8/12, 8/13, 8/31, 8/32) and 7/33 had the line prefix (ACW/FWS) recorded where the flag prints SWS/RCS/ACW. 10/193 had a `WTS` that is not printed anywhere on the flag. 5/43 prints `RC-PID-100-2`, recorded as printed.
- **4/117 is not a duplicate detection of 4/41.** Two separate flags at different heights; the drawing prints the same line number `SIZE-CND-165117` on both. Sheet 2 has only one outgoing 165117 to PID 180 (2/96), so one of the two sheet 4 flags must stay unresolved regardless.
- **Grid convention, verified from the printed borders:** rows A–H run bottom→top (H is the top band), columns 1–12 run right→left (column 1 is the right edge). So `(F-1)` means row F, right-hand edge. Confirmed against the accepted pairs 5/47↔10/45 (H-12), 6/16↔5/78 (G-1), 5/38↔11/23 (H-1), 5/49↔11/127 (C-1). Three references are **off by one row** (5/54 says E-1, 11/18 sits in F; 10/24 says C-1, 11/118 sits in D; 5/124 says D-1, 11/109 sits on the E/D boundary) — grid interpolation must tolerate ±1 row.
- **Sheet 8 row F is one straight header with an outgoing flag at each end.** 8/54 (left, `ACW PID 210-1`, arrow out) and 8/5 (right, `SWS PID 130-1`, arrow out) are joined by a single horizontal pipe fed by two verticals; `111156` labels its left part, `111162` its right part. Neither number is attributable to one connector alone.
- **7/33's grid cell resolves to the wrong flag.** 7/33 reads `ACW PID 210-2 (F-1)`, i.e. sheet 8, row F, right edge — which is 8/5, whose own label says it goes to SWS PID 130-1. The only outgoing 210-1 flag on sheet 8 is 8/54, at the other end of the same header. Candidate pair 7/33↔8/54 (would be `SERVICE_DIRECTION`, with a contradicting grid cell). **Not applied — the user decides.**
- **10/14's target text is legible and contradicts its pair.** It reads `PID 120-1 / RHR` clearly, not 100-1. The pair 5/114↔10/14 stands on two independent signals (identical line `115C049`, and 5/114's `G-12` landing exactly on 10/14) against one (the printed target). Alternative would be 10/14↔11/128. Kept as is, note rewritten to say so.

Manifest after the third read: unchanged counts — 22 pairs (19 `line_number`, 2 `grid_mutual`, 1 `service_direction`), 42 dangling, 10 unresolved, 96/96 accounted for.

### Sheets 0–2, same method (2026-09-05, later the same day)

All 25 rows agree with `annotations.py` on target, grid, line and service — the user's 2026-08-31 corrections (1/3 without a line, 1/73 = 150104, 2/17 = 165117) hold. Two additions:

- **1/5 is a detail-view repeat, not a second connector.** It sits in the "DETAIL A SECTION VIEW" and shows the same LCV 1501 and LIT 25094A/B as 1/73 in the main view. The detail prints line 150098, the main view 150104 — a source inconsistency. It stays unresolved (2/16 is already 1/73's partner), now with a note saying why.
- **Grid references on sheets 0–2 are loose too.** 1/3 says E-1, 0/83 sits in row D. 2/16 says C-12, 1/73 sits on the D/E boundary. 1/24 says F-1, but 2/13 is on the *left* edge (column 12) in row G — wrong in both axes. Grid cells corroborate; they cannot be the primary key.

### Decisions taken 2026-09-05 (afternoon)

- **7/33↔8/54 paired at `service_direction`.** By elimination: the only free "from 210-2" flag on sheet 7 and the only "to 210-1" flag on sheet 8. Lines differ and 7/33's grid cell points at the other end of 8/54's header (8/5), so the drawing contradicts itself; recorded at the weakest tier with the contradiction in the note. Manifest: 23 pairs, 8 unresolved.
- **5/114↔10/14 kept** (line + grid against one printed target).
- 7/34: probably a mistyped drawing number (160 for 200); unresolved. 9/2, 9/59: one-directional references, sheet 11 never points back; unresolved. 11/22: searched the equipment schedules of all 12 sheets, no "Reactor Water Service Tank" anywhere; unresolved.
- 0/79↔4/43: line number 140083 is printed twice on sheet 0 (ES-140083 on 0/79, FWS-140083 on 0/84); the pair rests on sheet reciprocity, the number only corroborates.

**Finding from the equipment schedules (bottom strip of every sheet).** The same equipment tag is listed on several sheets: `CND-TK-165` (deaerator storage tank) on sheets 2, 3 and 4; `CND-HTR-166` on sheets 2, 3 and 4; `CVCS-HX-111` on sheets 8 and 10. Sheet 2 lists `CND-HTR-161` (condensate heater) and sheet 3 lists `FWS-HTR-161` (HP FWS heater) — same number, different prefix, possibly the same machine (hypothesis, not verified). This is the tag-identity ground truth open question 1 asked for, and unlike the RCS-PU-102A/B case it is printed as text in a fixed place, so it can be recovered systematically. Still no GraphML node to anchor an `IdentityGroup` to — the schedule entries are text, not annotated symbols. Parked until the identity mechanism is designed.
