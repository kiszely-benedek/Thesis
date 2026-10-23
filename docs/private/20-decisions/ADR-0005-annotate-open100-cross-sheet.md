---
adr: 0005
title: Annotate OPEN100 cross-sheet connectors as a real validation set
status: accepted
date: 2026-08-25
supersedes: none
---

# ADR-0005 — Annotate OPEN100 cross-sheet connectors

## Context

ADR-0004 built the multi-page benchmark synthetically because no real multi-sheet ground truth was obtainable. Inspection on 2026-08-25 changed that: PID2Graph's 12 OPEN100 sheets are **one real plant** (OPEN 100 nuclear design), carrying genuine off-page connectors that name their partner sheet, grid cell and line number.

The cross-sheet truth is **in the images but absent from the GraphML**, whose nodes carry only a class label and a bounding box.

A spike settled the feasibility question. Cropping the 96 `inlet/outlet` bounding boxes shows **the label text sits inside the box and is fully legible**; the line number sits just outside, on the pipe, and a modest margin captures it. All 12 connectors on sheet 5 were read correctly on the first attempt.

## Options considered

**A. Synthetic only.** No extra work. Leaves the thesis resting entirely on generated data, which is its most attackable point at a defence.

**B. Annotate OPEN100 as well.** Roughly one to two days. Yields a real multi-sheet P&ID set with cross-sheet ground truth — which does not exist publicly — plus naturally occurring dangling references as abstention cases, plus calibration targets for the generator.

**C. Wait for the professor's factory documents.** They will be more realistic and much larger, but they arrive on an unknown date, carry no ground truth at all, and would need vastly more annotation effort. Not a substitute.

## Decision

**Option B.** Annotate the OPEN100 cross-sheet connectors and publish the result alongside the synthetic generator. Confirmed by the user 2026-08-25.

## Rationale

The cost collapsed once the spike showed the labels are directly readable — no OCR training, no bespoke detector, and the 96 items are few enough to verify by hand.

The payoff is disproportionate. Synthetic-only evidence invites *"this is not what real drawings look like"*, and the honest answer today would be a shrug. With OPEN100 annotated, the answer becomes a measurement on real drawings. That is the difference between plausible and demonstrated.

It also produces a **publishable artifact independent of the retrieval results** — useful insurance if the main experiments come out ambiguous.

## Consequences

**Enables** — real validation alongside synthetic scale sweeps; calibration of the generator against measured drawing statistics; free abstention cases (PID 190, 240, 290 are referenced but absent from the set).

**Costs** — one to two days. Licence: PID2Graph is **CC BY-SA 4.0**, so the derived annotation must be released share-alike, and that must be stated on release.

**Limits — state these plainly in the thesis.** 12 sheets is not plant scale; this validates realism, not scale. One plant, one author, one drawing convention, one date — it is a *sample*, not a distribution. The synthetic generator remains the primary instrument for the scale claim.

**⚠ Over-reliance is the main risk of this ADR** (raised by the user, 2026-08-25, and it is the right objection). OPEN100 is a *preliminary* nuclear design — clean vector drawings marked "INFORMATION ONLY – NOT FOR CONSTRUCTION", one author, one CAD tool, one day. Real factory documents will be scanned, older, multi-author, multi-era, hand-annotated, possibly a different symbol standard or language. Three guards, all binding:

1. **OPEN100 is a sanity check, not a calibration target.** The generator must produce data well outside OPEN100's ranges, not fit to them. Recorded in `40-design/splitter.md`.
2. **Label grammars stay in a per-corpus adapter**, never in core logic. Parsing `PID 120-1 (C-1)` is an OPEN100 fact, not a P&ID fact. Any component that only works on this grammar has a bug the benchmark must expose.
3. **Convention is a generator variable** — numbering scheme, label format, presence of a grid reference. Downstream components get tested against conventions they have not seen.

If the professor's documents contradict OPEN100's patterns, **the documents win** and this ADR's assumptions get revised, not defended.

**Follow-up** — design in `40-design/open100-annotation.md`. The output must use the **same manifest schema** as the synthetic splitter so downstream code cannot tell the two sources apart.
