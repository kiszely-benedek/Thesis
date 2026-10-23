---
adr: 0010
title: Build a thin sheet-linking resolver early; evaluate it after the scale experiment
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0010-phase-ordering.md
supersedes: none
---

# ADR-0010 — Phase ordering

**Question.** Should cross-sheet entity resolution (linking sheets into one plant graph) move ahead of the
single-sheet baseline?

**Options**
- **O1** Keep the old order: baseline → scale → resolution. The scale experiment would then run on the unsplit
  graph, so it never exercises the sheet linking.
- **O2** Resolution entirely first. It follows the pipeline order, but leaves the risky Q&A half until last.
- **O3** Split it. Build a **thin resolver** early, as a pipeline stage. **Evaluate** it (EXP-0004) after the
  scale experiment.

**Decision: O3.** New phase order:
1. benchmark;
2. **KG construction** — importer, thin resolver, Neo4j loader;
3. Q&A system + EXP-0001;
4. **plant-scale Q&A** (headline, ADR-0015);
5. resolver evaluation;
6. future work;
7. write-up.

**Two rules**
- The resolver sees only what is on the sheets, never the answer key. `rejoin()` reads the answer key, so it is
  a test for the splitter, not a resolver.
- `resolve(split(plant)) == plant` is a **correctness gate, not a result**. At default labels it is trivial by
  construction. The scale runs use the resolved graph; if the gate fails, report the oracle-graph run beside it.

**Why**
- The title leads with KG construction.
- The scale experiment then runs through the real pipeline.
- The Q&A unknowns were cleared in week 1 anyway — the DEXPI file, the 19 questions, LLM access.

**Costs.** The resolver's real test comes late. The oracle fallback covers that.

**Revisit if** the gate fails on contract-clean sheets.

## Outcome log
- **2026-09-26** Accepted (user). The ordering still stands; the calendar
  is in `40-design/thesis-phase-plan.md` revision 2.
