---
adr: 0009
title: The per-sheet graph is the system's input; a DEXPI Proteus importer feeds it alongside the splitter
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0009-system-input-contract.md
supersedes: none
---

# ADR-0009 — What the system takes as input

**Question.** Given ADR-0008, what exactly does the Q&A system accept?

**Options**
- **I1** Per-sheet graphs only (today). No new work, but no DEXPI file can enter.
- **I2** One Proteus XML file per sheet. Most literal, but needs a full Proteus exporter, which pyDEXPI 1.2.0
  lacks (it exports equipment only).
- **I3** One pyDEXPI JSON per sheet. Same cost as I2, and it is not a DEXPI exchange format.
- **I4** The per-sheet graph (`SheetGraph`) is the contract, with two producers: the splitter (generated
  plants) and a **Proteus importer** (real DEXPI files).

**Decision: I4.** I2 is the upgrade path if a Proteus exporter is ever built.

**Rule for every producer.** A sheet may carry only what is **visible on that sheet**. Today the splitter
reuses a node's id on every sheet it appears on (`splitter.py:183`) — that id is the answer key. The resolver
must not be able to use it (design: `40-design/kg-construction.md`).

**Why**
- It makes "reads a DEXPI drawing" true at the lowest cost, mostly with existing code.
- EXP-0001 (one imported sheet) and the scale runs (thousands of generated sheets) share one downstream path,
  so a difference between them is a scale effect, not a pipeline difference.

**Costs.** The generated corpus never exists as DEXPI files. The importer is proven on one public file. State
that as a limitation.

**Revisit if** a Proteus exporter is accepted, or the professor asks for file input on the whole corpus.

## Outcome log
- **2026-09-26** Accepted (user). **Verified:** pyDEXPI reads `data/external/C01V04-VER.EX01.xml` (from
  pyDEXPI's GitHub) in 0.36 s → 214 nodes, 36 after condensing. ChatP&ID reports 212 → 53, a **gap that is
  unexplained**. The file is very likely ChatP&ID's `DEXPIEX01.xml`: the paper's sample questions name tags
  P4712 and T4750, and both occur in it.
