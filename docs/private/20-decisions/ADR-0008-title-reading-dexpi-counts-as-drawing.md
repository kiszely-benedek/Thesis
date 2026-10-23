---
adr: 0008
title: A DEXPI/Proteus file counts as a "drawing"; no pixels-to-graph front end
status: accepted
date: 2026-09-25
accepted: 2026-09-25
full: full/ADR-0008-title-reading-dexpi-counts-as-drawing.md
supersedes: none
---

# ADR-0008 — A DEXPI file counts as a "drawing"

**Question.** The title says "Tudásgráf-építés *műszaki rajzokból* …" — must the system read drawing
*images*, or is a machine-readable DEXPI/Proteus P&ID enough?

**Options**
- **R1** DEXPI/Proteus input counts as a drawing — scope stays as ADR-0001/0007.
- **R2** Pixels required — a whole new phase: detector (weights unverified), OCR (PID2Graph has no text),
  rendering our plants to images first, and 75.46 % edge mAP error carried into every result.
- **R3** Pixels as an optional demo — same work as R2, measures nothing.

**Decision: R1.** The professor's answer, relayed by the user on 2026-09-25. **P&IDs only** — no other drawing
type (user, 2026-09-26).

**Why**
- It is the professor's reading of the title the professor registered.
- Single-page digitization is taken by four groups (ADR-0001); multi-sheet scale is open.
- ChatP&ID, the paper we extend, also starts from DEXPI XML.

**Branch point, kept re-openable.** A pixels front end would be one more producer of per-sheet graphs
(`SheetGraph`, ADR-0009). Nothing downstream would change.

**Costs.** The thesis says plainly: "drawing" means a machine-readable DEXPI P&ID; scanned drawings are out of
scope.

**Open.** The professor's answer **in writing**.

**Revisit if** the written answer differs, or an examiner asks for image input. Drawing reading is a stretch
*"if we will have time"* (user, 2026-09-26; ADR-0011).

## Outcome log
- **2026-09-26** User: *"Yeah its R1, but if we have time, because we finish so early we can go to R2 as well."* R2 (reading drawing images) is a **stretch after the headline results**, not a reopening of this decision.

## Confirmation (2026-10-05)

The professor confirmed on the 2026-10-05 call (relayed by the user): a DEXPI file counts as a drawing; **P&IDs alone are enough** (no second drawing type); evaluating on generated plants is acceptable, with external validity stated as a limitation; the self-flag cascade as the researched method is the intended emphasis.
