---
id: zenodo.14803338
title: PID2Graph
authors: Stürmer, Graumann, Koch (DLR)
year: 2025
status: read
relevance: dataset
tags: [dataset, graphml, benchmark, open100]
doi: 10.5281/zenodo.14803338
license: CC BY-SA 4.0
size: 9.3 GB
---

## What it is
P&ID images paired with graph ground truth. Symbols are **nodes** (bounding box + label), lines are **edges** (label). Ground truth in **`.graphml`**, loadable with NetworkX. Published with arXiv 2411.13929.

## Contents
Two views of the same material:
- **Complete plans** — full P&ID pages with their graphs
- **Patched plans** — overlapping page sections, each with its own graph

Special node labels: `connector` (connection points) and `border-node` (a line crossing a **patch** boundary).

Three component subsets, **all inside the single 9.3 GB zip**:
1. **Dataset-PID** (CC BY-SA 4.0) — 500 synthetic pages, 32 symbol classes, from Paliwal et al.
2. **PID2Graph OPEN100** — **12 real** reactor plans from open-100.com, mean 382±125 nodes/plan, 7 symbol classes, 2 line classes, no dashed lines
3. **PID2Graph Synthetic** — ISO 10628 symbols (CC BY-SA 4.0)

## Relation to this dissertation — read this before planning any experiment

**PID2Graph cannot test the scalability claim.** It is a collection of *independent single pages*. `border-node` marks a line crossing a **patch** boundary inside one page during training — it is not an off-page connector, and there is **no cross-page ground truth anywhere in the dataset.**

What it is genuinely good for:
1. **Digitization-error modelling** — realistic corruption rates for the error-propagation study (ADR-0004)
2. **Front-end validation** if we run a detector at all
3. **Source material for inversion** — pages and symbol libraries to build synthetic multi-sheet plants from

**Resolved 2026-08-25 by direct inspection of the files — the answer is YES.**

> ⚠ An earlier entry here recorded "the 12 sheets are unrelated." That was **wrong** and was never verified. It has been replaced by the inspection below. Retained as a note because the mistake propagated into ADR-0004 and the index before it was caught.

All 12 sheets are **PROJECT: OPEN 100** — one nuclear plant design by the Energy Impact Center (open-100.com), every sheet drawn by the same author ("MAJ") on the same date (09/01/2020), revision A.

| file | System | PID | Sheet |
|---|---|---|---|
| 0 | Main Steam | 140 | 1 of 1 |
| 1 | Air Cooled Condenser | 150 | 1 of 1 |
| 2 | Condensate | 160 | 1 of 1 |
| 3 | Feedwater | 170 | **1 of 2** |
| 4 | Extraction Steam | 180 | 1 of 1 |
| 5 | Reactor Coolant | 100 | **1 of 2** |
| 6 | Reactor Coolant | 100 | **2 of 2** |
| 7 | Aux Cooling Water | 210 | **1 of 2** |
| 8 | Aux Cooling Water | 210 | **2 of 2** |
| 9 | Residual Heat Removal | 120 | **2 of 2** |
| 10 | Chemical Volume Cooling Water | 110 | 1 of 1 |
| 11 | Residual Heat Removal | 120 | **1 of 2** |

### The sheets carry real, machine-resolvable off-page connectors

Confirmed on sheets 0 and 5. Incoming connectors sit on the left edge, outgoing on the right, drawn as the standard flag/arrow symbol. Each names its partner precisely:

- `PID 120-1 (D-1) RHRS` — target sheet **and grid cell**. The drawings have A–H / 1–12 grid borders on all four edges, so the coordinate resolves to a location on the partner sheet.
- `RCS-PID-100-2` — sheet 5 pointing at sheet 6, its own system's second sheet.
- Every connector also carries a **line number**: `SIZE-RCS-100007-SPEC-HC-X`, `SPEC-RHRS-121A065-SPEC-HC-X`.

References that **resolve inside the 12**: PID 100-2, 110-1, 120-1, 150-1, 170-1, 180-1.
References that **dangle** (target absent from the set): PID **190** (HP steam drains), PID **240** (turbine system), PID **290** (water sample system). PID 170 sheet 2 of 2 is also missing.

### The catch — and it is the important part

**The GraphML ground truth captures none of this.** The annotation schema is purely geometric:

- node attributes: `label`, `xmin`, `xmax`, `ymin`, `ymax`
- edge attributes: `edge_label` (only ever `solid` — no dashed lines, confirming the paper's stated limitation)
- node label vocabulary across all 12 sheets: `connector` 2408, `crossing` 734, `arrow` 451, `instrumentation` 350, `valve` 257, `general` 234, `inlet/outlet` 96, `background` 48, `tank` 35, `pump` 16

**There are no tags, no text, and no equipment identifiers anywhere in the graphs.** The 96 `inlet/outlet` nodes are the page-boundary symbols — but stripped of the label text that says *which* sheet they connect to. Per-sheet node counts (mean 386, range 181–675) match the paper's stated 382±125, confirming this is the OPEN100 the paper describes.

### What this means

The cross-sheet ground truth is **present in the images and absent from the annotations**. It is therefore *recoverable*: ~96 connector labels across 12 sheets, resolvable by OCR plus manual verification against the grid references. That is days of work, not months.

If done, it yields something that **does not currently exist publicly**: a real multi-sheet P&ID set with cross-sheet ground truth. Plus, the dangling references (PID 190/240/290) are **naturally occurring incomplete information** — abstention test cases that occur for free rather than being manufactured.

This does not replace the synthetic benchmark (12 sheets cannot sweep scale), but it makes a real validation set achievable alongside it. See ADR-0004 outcome log and `40-design/splitter.md`.

## Licence warning
**CC BY-SA 4.0 — share-alike.** Anything derived and redistributed (a benchmark built on these pages, for instance) must carry the same licence. Note this in the benchmark's own licence file. It interacts with the AGPL question in ADR-0003; both point the project toward copyleft.
