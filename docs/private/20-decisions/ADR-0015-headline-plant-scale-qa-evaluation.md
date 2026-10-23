---
adr: 0015
title: Make plant-scale Q&A the headline — one sweep whose ~100- and ~1,000-sheet points are end-to-end evaluations, plus a public benchmark release
status: accepted
accepted: 2026-09-26
date: 2026-09-26
supersedes: none
---

# ADR-0015 — Headline evaluation: plant-scale Q&A

**Question.** The user asked on 2026-09-26 for the Q&A system to be evaluated on a 100- or 1,000-sheet P&ID, not on OPEN100. What is the headline evaluation? OPEN100 was only ever the resolver's test set (EXP-0004). EXP-0002 already swept Q&A to thousands of sheets, but only as supporting evidence.

## Options
- **H1:** keep EXP-0002 as a sweep that serves as supporting evidence only (status quo).
- **H2:** add a separate end-to-end evaluation at fixed sizes (~100 and ~1,000 sheets) as the headline, next to the sweep.
- **H3:** run one frozen sweep from 1 to ~4,000 sheets. Its ~100- and ~1,000-sheet points are the headline end-to-end runs (ingest → resolve → Neo4j → answer), reported as a table of their own. Publicly release the generator, corpora, questions and harness.

## Decision
**H3.** The details are in [`40-design/qa-system.md`](../40-design/qa-system.md) §13–§15.
1. **Headline points.** ~100 sheets (one ~100-page document) and ~1,000 sheets (~10 documents, ADR-0001), plus a ~10-sheet anchor. Every row reports both sheets and nodes.
2. **Id.** Folded into EXP-0002 as rows `EXP-0002-H100` and `EXP-0002-H1000`. EXP-0006 is already named in ADR-0007.
3. **Success criteria and outcome wording** are fixed before the first reported run (§13.3).
- **Must:** EXP-0001; the headline at ~10, ~100 and ~1,000 sheets with ContextRAG, CypherRAG and Hierarchical; one pinned model; a release bundle.
- **Should:** VectorRAG and PathRAG; the ~4,000-sheet and intermediate points; 2–3 model families at the headline points; a DOI.
- **Could:** agentic multi-step retrieval; a drawing-reading demo.
4. **Claim.** Only "first multi-sheet P&ID QA evaluation with executable cross-sheet ground truth". Never claim realism (ADR-0007, §15).

## Why
- **One freeze covers both the headline and the curve** (ADR-0014). H2 would mean building and freezing twice inside five weeks.
- **It answers the demand directly and visibly.** The ~100- and ~1,000-sheet rows do that, and the sweep still carries the crossover claim.
- **Interconnected sheets at scale are what prior work lacks.** ChatP&ID has one sheet. PIDQA has 500 unrelated sheets. The release makes our corpus reusable.
- **End-to-end runs put the resolver on the headline data** (ADR-0010 decision 3).

## Costs
- **Unmeasured at ~1,000 sheets:** the Neo4j load and the resolver. The fallback is the networkx view for the non-Cypher strategies (qa-system §5).
- **Generated sheets are sparse.** SMOKE-01 gives about 10.7 nodes per sheet; OPEN100 averages 386. So ~1,000 sheets is roughly 10,700 nodes (a linear estimate). Only the ~4,000-sheet point (43,043 nodes, SMOKE-02) reaches ADR-0001's estimate of ~38,000 nodes for a real 100-page document.
- **Schedule risk.** There are 17 must-have coder tasks (qa-system §18), one coder, and little time. Nobody has measured how fast a coder gets through tasks like these.

## Revisit if
- **The pilot is not frozen by 2026-10-11.** Cut per qa-system §14.3.
- **The pilot's budget estimate exceeds the OpenRouter credit.** Collapse k-bins before dropping a size.
- **A paper publishes multi-sheet P&ID Q&A.** `/lit-gap-check` is next due 2026-10-10.

## Outcome log
- **2026-09-26** Accepted by the user as recommended (H3). ADR-0017 (accepted the same day) changes the sheet density: at budget 16, ~1,000 sheets ≈ SMOKE-02's size (~43,000 nodes), so the "generated sheets are sparse" cost above no longer holds for the headline corpora — re-measured under a new SMOKE id after the splitter fix.
- **2026-09-26** Clarification (main session): with sheets calibrated to a real DEXPI sheet (ADR-0017), H1000 ≈ 1,000 pages ≈ ten ~100-page documents. ADR-0001's ~38,000-nodes-per-100-pages figure uses PID2Graph's image-level node counts and is not comparable to our conceptual nodes.
