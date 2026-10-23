---
adr: 0020
title: Keep the data attributes that real DEXPI files carry; generated plants stay without them
status: superseded
superseded_by: ADR-0021
date: 2026-09-26
accepted: 2026-09-26
supersedes: none
---

# ADR-0020 — Data attributes of imported DEXPI files

**Question.** Should the importer keep the real data inside a DEXPI file? EX01 has tank lengths, pump powers
and valve diameters, and **10 of ChatP&ID's 19 questions ask for exactly those values** (ADR-0013 outcome log).
Today the importer keeps only class, tag and plant id, and `localize` strips everything else, so those 10
questions are unanswerable (`kg-construction.md` open question 1d; `qa-system.md` OQ2).

**Options**
- **K1** Keep the attributes of imported files as visible node properties. All 19 questions become
  answerable, and the comparison with ChatP&ID's 0.91 is complete.
- **K2** Drop them everywhere. EXP-0001 compares only the 9 topology questions; stated as a limitation.

**Decision: K1** (user, 2026-09-26: *"Keep it for real files"*).
1. It applies to **imported files only**. Generated plants still carry no equipment data (ADR-0018, A1).
2. The kept attributes are whatever the file itself states. None are invented or filled in.
3. They are *visible* properties, so `localize` keeps them and the contract check accepts them. Which pyDEXPI
   attribute names become visible, and with what units, is fixed in `kg-construction.md` (task T1c).

**Why.** The comparison with ChatP&ID is the thesis's anchor. Without the attributes, more than half of it
would be unanswerable for a reason that has nothing to do with retrieval.

**Costs.** Nodes from imported files have more properties than generated ones, so EX01's serialized graph is
larger per node. That is fine, because EX01 is never part of the scale sweep.

**Revisit if** datasheet data is ever merged: the same visible-property path should carry it.

## Outcome log
- **2026-09-26** **Superseded by ADR-0021** the same day: the user decided no equipment data at all, not even from real files. The T1c code was removed before any commit.
