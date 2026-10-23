---
adr: 0011
title: Cut or shrink everything that is not on the path to plant-scale Q&A
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0011-scope-triage-for-deadline.md
supersedes: none
---

# ADR-0011 — What gets cut for the deadline

**Question.** Which open side items stay, shrink, or become one paragraph of future work?

**Decision (accepted as recommended, every row):**

| # | Item | Decision |
|---|---|---|
| 1 | Utilities in the generator | **Cut** — one-to-many connectors need a schema change; the scale claim does not need them |
| 2 | EXP-0003 digitization error sweep | **Minimal** — becomes label noise inside EXP-0004 (there is no digitizer to test) |
| 3 | EXP-0005 abstention | **Minimal** — one "unanswerable" question family in the ADR-0013 question set |
| 4 | Several plants per corpus | **Cut** — one plant already reaches 4,015 sheets |
| 5a | Rendering to PDF | **Cut** — nothing consumes pixels |
| 5b | Full Proteus exporter | **Cut** — ADR-0009 chose I4 (reverses the 2026-09-20 leaning) |
| 6 | Reading real PDFs | **Cut** — stretch only *"if we will have time"* (user, 2026-09-26) |
| 7 | OPEN100 grid interpolation | **Minimal** — the user ticks `verified_by_human` on the 23 pairs instead |
| 8 | `rejoin.py` speed fix | **Cut** — measured at 6 % of the pipeline |
| 9 | Full reading of the PIDQA paper | **Keep** — its method is our evaluation method; needs library access |

**Also out:** equipment datasheets — out of scope — not part of this thesis (user, 2026-09-26; ADR-0021).

**Why.** The time is short, and the whole Q&A half is unbuilt. An item stays only if it feeds the
headline, is nearly free, or protects the correctness of a method we use.

**If time frees up,** reinstate in this order: label noise → several plants → utilities → exporter →
rendering → PDF reading.

## Outcome log
- **2026-09-26** User revisions: **utilities → stretch before the deadline** (*"they can be enacted here in the future as part of this project before deadline"*), no longer future work only; **reading real PDFs stays out for now**. Equipment data: see ADR-0018 and ADR-0021 (out of scope — not part of this thesis).
