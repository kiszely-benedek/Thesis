---
run: EXP-0007 R0 — v2 scale smoke (free)
date: 2026-10-27
commit: 917b4c3
status: done
plan: EXP-0007-v2-remeasurement-plan.md §0–§1
---

# R0 — v2 at ~100 and ~1,000 sheets: generation, questions, Neo4j load

**Result.** v2 is feasible on this machine at 1,000 sheets: generation and split take 478 s (kill criterion
600 s, `plant-generator.md`), the Neo4j load 135 s (K-NEO 600 s). Question generation at D1000g2 took
16,440 s of build time, far over ADR-0029's 600 s; the figure is not a clean measurement (see Caveats). The plant
database `neo4j` (D1000) was identical before and after (37,124 nodes, 111,668 relationships, corpus D1000).

## Runs

Dev seed 1, `--headline-v2`, duplication 0.25, `--check` on the no-Neo4j ingests. Script:
`$TEMP/claude_r0v2/r0.py` (session scratch, not in the repo); child output to files; peak RSS = the child
process tree, sampled every 0.2 s. Neo4j loads went into a throwaway database `r0tmp`
(`NEO4J_DATABASE=r0tmp`, `--fresh-database`), dropped at the end.

| Step | Corpus | Wall (s) | Peak RSS (MB) | Notes |
|---|---|---|---|---|
| ingest, no Neo4j | D100g2 | 10.9 | 329 | |
| question set (`--n-per-bin 20 --n-unanswerable 20`) | D100g2 | 31.8 | 340 | build 22.2 s; 33,858 candidates; no bin underpowered |
| ingest, no Neo4j | D1000g2 | 478.2 | 1,746 | |
| question set | D1000g2 | 16,890.8 | 2,485 | build 16,439.8 s; 343,641 candidates; no bin underpowered |
| ingest + load | D100g2 | 54.3 | 336 | load_total 22.44 s (nodes 9.63, relationships 10.61, verify 1.78) |
| ingest + load | D1000g2 | 1,125.9 | 1,740 | load_total 134.85 s (nodes 29.76, relationships 97.18, verify 7.55) |

Store sizes: D100g2 19,180 nodes / 67,340 relationships, 173 connector pairs; D1000g2 188,947 nodes / 663,516
relationships, 1,723 connector pairs; 0 unresolved in both.

## Caveats

- **Contention and sleep.** An architect agent and a coder ran on the same machine during the run. The D1000g2
  question-generation process had used about 2,100 s of CPU after about 15,300 s of wall time (checked
  17:16), so it was idle or descheduled most of the time (the machine probably slept). Its wall and build times
  are an upper bound, not a measurement of the code.
- The D1000g2 ingest (478 s) is about 2× the pre-T13 figure (245.9 s), with all eight patterns now in the
  generator and the same contention.

## Consequences

- Question generation at D1000g2 must be re-timed on a quiet machine, and profiled per family, before the
  R5 H1000g2 draw. Exceeding ADR-0029's 600 s is a deviation to report; it blocks no run (plan §12 item 6).
