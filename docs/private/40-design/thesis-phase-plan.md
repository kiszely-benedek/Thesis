---
title: Phase plan against the official title
date: 2026-09-25
revised: 2026-09-26 (revision 2 — headline = plant-scale Q&A)
status: accepted in structure (ADR-0009, 0010, 0011, 0013, 0014 accepted 2026-09-26); headline per ADR-0015 (proposed)
author: main session, Opus 5.5 (high)
---

# Phase plan

Planned against the title the professor registered on 2026-09-25:

> **Tudásgráf-építés műszaki rajzokból és P&ID diagramokból skálázható Q&A rendszerhez**
> *(Knowledge-graph construction from technical drawings and P&ID diagrams, for a scalable Q&A system.)*

**Revision 2 (2026-09-26).** Revision 1 planned to a later deadline. The user
also asked for the headline to be the Q&A system evaluated end to end on a **100- to 1,000-sheet P&ID**, not on
OPEN100: *"do not shoot so low. We have to break through the field."* Revision 1 already swept Q&A to
thousands of sheets (EXP-0002) and used OPEN100 only for the resolver (EXP-0004) — but it did not say so
loudly enough. **Revision 2 makes the plant-scale evaluation the headline** (ADR-0015).

## 0. Inputs

| Input | Value | Source |
|---|---|---|
| "Drawings" | **DEXPI/Proteus files count; P&IDs only** | professor via user, 2026-09-25 / 2026-09-26 (ADR-0008); written confirmation still open |
| Thesis | **BSc szakdolgozat**, BME VIK mérnökinformatikus, TMIT; **English**; template link to come from the user | user, 2026-09-26 |
| LLM access | **OpenRouter** credits (OpenAI leaning, many models to try) + local models for development | user, 2026-09-26 (ADR-0014) |
| Out of scope | equipment datasheets (out of scope — not part of this thesis, ADR-0021); drawing reading from images is a stretch "if we will have time" | user, 2026-09-26 (ADR-0011) |
| Exists | generator, splitter, schema; SMOKE-01…03 (4,015 sheets / 43,043 nodes in 49.42 s, 785.7 MiB; round trip holds to 4,015 sheets); EX01 imports (214 → 36 nodes); ChatP&ID's 19 QA pairs located (App. Table 1) | `_results.md`, ADR-0009/0013 outcome logs |
| Does not exist | resolver, Neo4j loader, any retrieval, question generator, evaluation | code at `b30414b` |

**Five weeks, and this is where the plan is honest about it.** The user wrote *"you will run 0-24, so do not
worry about the deadline."* Main-session hours are not the constraint. The real limits are:
1. **Review and commit throughput.** Every change enters history through the user. Code that piles up
   unreviewed is a risk, so there is a commit checkpoint after every task group below.
2. **One coder at a time** (ADR-0006).
3. **LLM wall-clock time and rate limits** at ~1,000 sheets × strategies × questions. Sized by the pilot,
   not assumed.
4. **Writing.** This runs in parallel from week 1, not after the experiments.

## 1. The branch point — closed

```
   DEXPI / Proteus XML ─┐
                        ├─► per-sheet graph ─► resolver ─► plant KG (Neo4j) ─► retrieval ─► answer
   generated sheets ────┘         ▲
                                  │  a pixels → graph front end would attach here
   scanned image / PDF ─ ─ ─ ─ ─ ─┘  NOT TAKEN (ADR-0008); stretch only if time remains after W43
```

## 2. The headline — what "breaking through the field" can honestly claim

Per ADR-0015 (proposed):
- **Claimable.** The **first Q&A evaluation over P&IDs spanning hundreds to thousands of *interconnected*
  sheets, with cross-sheet ground truth**, end to end: ingest → resolve → knowledge graph → answer.
  - Prior work: ChatP&ID, 1 sheet, 19 questions; PIDQA, 500 *unrelated* single sheets; 2609.05880, 100 test
    sheets, one sheet per question.
  - AEC-Bench has cross-sheet tasks, but over building drawings, not P&IDs (`_novelty-log.md`, 2026-09-26).
  - The evaluation is released as a public benchmark: generator, corpora, questions and harness.
- **Also claimable.** Where each retrieval strategy stops working as the plant grows (the crossover), and a
  hierarchical strategy designed for past that point.
- **Not claimable.** Realism. The plants are generated (ADR-0007), and OPEN100's 12 real sheets are only a
  resolver check.

## 3. Calendar

| Week | Dates | Build (one coder at a time) | Experiments | Writing (in parallel) |
|---|---|---|---|---|
| W39 | Sep 26–27 | design notes: `kg-construction.md`, `qa-system.md`, ADR-0015 | — | thesis skeleton in the BME template |
| W40 | Sep 28–Oct 4 | **P2**: importer → resolver (+ scoring) → Neo4j loader → `ingest` CLI | ingest gates at SMOKE sizes; Neo4j load timing | Ch. 1 Introduction, Ch. 2 Background (P&ID, DEXPI, GraphRAG) |
| W41 | Oct 5–11 | **P3**: LLM client + cache → ContextRAG / VectorRAG / CypherRAG / PathRAG → EXP-0001 harness | **EXP-0001** on EX01 (19 questions) | Ch. 3 Related work; Ch. 4 Benchmark (already built) |
| W42 | Oct 12–18 | question generator (k-stratified) → **Hierarchical** strategy | **pilot**: context wall, cost, latency, variance → fix question counts; start the sweep | Ch. 5 System design (KG construction + Q&A) |
| W43 | Oct 19–25 | fixes only; **code freeze Fri Oct 23** | **headline runs at ~100 and ~1,000 sheets**, then ~4,000 if the budget holds; **EXP-0004** (OPEN100 23 pairs + label dials) | Ch. 6 Evaluation (filled as numbers land) |
| W44 | Oct 26–30 | none | re-runs only | Ch. 7 Discussion and limitations, abstracts, proofread |

Every week's width is an estimate. The one measured pace is phase 1 (≈5 weeks, W34 → 2026-09-20), and that
included design and a history rewrite.

## 4. Must / should / could (ADR-0015 defines the final ladder)

- **Must:**
  - EXP-0001 on EX01;
  - the headline end-to-end Q&A at **~100 and ~1,000 sheets**, with at least ContextRAG (its "does not fit"
    point included), one retrieval baseline and the Hierarchical strategy, on one pinned model;
  - cross-sheet questions stratified by connectors crossed;
  - EXP-0004 on OPEN100.
- **Should:** all five strategies; the ~4,000-sheet point; two or three model families via OpenRouter; the
  label-difficulty sweep.
- **Could:** agentic multi-step retrieval; the RDF arm (ADR-0012 not accepted, so ADR-0002 stands — but it is
  last in the queue); a drawing-reading demo.

## 5. Phases

### P1 — Close the benchmark (done except the freeze)
Utilities are cut (ADR-0011). **Deliverable:** the user tags the benchmark commit; P4 corpus sizes are fixed in
`qa-system.md` / ADR-0015.

### P2 — KG construction (W40) — design: `40-design/kg-construction.md`
- **Deliverable:** Proteus importer → `SheetGraph`; resolver from sheet content only; Neo4j loader with the
  sheet hierarchy; an `ingest` CLI.
- **Validates it:**
  - `resolve(split(plant)) == plant` at defaults, with the manifest withheld;
  - a renaming test that closes the node-id leak (`splitter.py:183`);
  - load time at 4,015 sheets, against a threshold set before the first measurement.
- **Depends on:** a Neo4j DBMS (**user creates it in Neo4j Desktop 2; none exists today**).
- **Fails if:** the load is too slow → run non-Cypher strategies on in-memory networkx.

### P3 — Q&A system + EXP-0001 (W41) — design: `40-design/qa-system.md`
- **Deliverable:** OpenRouter client with a replay cache; the four ChatP&ID strategies; the 19 questions
  transcribed from App. Table 1.
- **Validates it:** EXP-0001 — reproduce the **ranking** (ContextRAG 0.91 > CypherRAG 0.86 > PathRAG 0.83 >
  VectorRAG 0.82 with GPT-5-mini), judged with ChatP&ID's rubric (ADR-0013).
- **Fails if:**
  - the ranking does not reproduce → report it, do not tune toward it;
  - the 214 → 36 vs 212 → 53 node-count gap turns out to matter → note it in the threats.

### P4 — The headline: plant-scale Q&A (W42–W43)
- **Deliverable:** the question generator (programmatic ground truth over networkx, stratified by k
  connectors crossed); the Hierarchical strategy; results at ~100 / ~1,000 (/ ~4,000) sheets plus the sweep
  curve.
- **Validates it:** the success criteria ADR-0015 fixes **before** the runs.
- **Fails if:**
  - no crossover appears before ContextRAG's context wall. That is still a finding, but "the ranking inverts"
    may not be claimed;
  - cost or rate limits → the pilot sets question counts, and the ladder in §4 says what to drop first.

### P5 — Resolver evaluation, EXP-0004 (W43)
- **Deliverable:** precision and recall on OPEN100's 23 held-out pairs, plus the splitter's difficulty dials
  (`exact_match_tags=False`, lower `connector_label_detail`).
- **Caveat:** 23 pairs are a point, not a curve.

### P6 — Later phases — cut to future work (ADR-0011)

### P7 — Write-up (W39–W44, in parallel)
- **Deliverable:** the thesis in the BME template.
- **Depends on:** the template link (user). Also unverified: whether BME requires both a Hungarian and an
  English abstract — check the template.

## 6. Blockers — status 2026-09-26

| # | Blocker | Status |
|---|---|---|
| B1 | `DEXPIEX01.xml` | **Resolved.** `data/external/C01V04-VER.EX01.xml` (pyDEXPI GitHub, sha256 `a2b172f0…b809c`), imports cleanly. Identity supported by the paper's citation and tags, not proven. **Untracked; its licence is not stated in the file — the user decides whether to commit it.** |
| B2 | ChatP&ID's questions | **Resolved.** Appendix B, App. Table 1, pp. 28–36; PDF at `docs/Academic_papers/2603.22528-ChatPID.pdf` |
| B3 | LLM provider | **Resolved in principle:** OpenRouter. **Open:** the key in an environment variable (`OPENROUTER_API_KEY`) |
| B4 | Deadline | **Resolved** |
| B5 | Written confirmation; drawing types | Types resolved: **P&ID only**. Written confirmation still open |
| B6 | Neo4j | **Open:** Desktop 2 is installed, `dbmss/` is empty — the user creates a local DBMS and exports `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| B7 | `/lit-gap-check` | **Done 2026-09-26:** claim still open, wording narrowed to P&IDs (AEC-Bench) |
| B8 | Format | **Resolved:** BSc, English. **Open:** the template link |

## 7. Where this plan is guessing

1. **Every week's width.** Five weeks for P2–P5 plus the write-up is aggressive; nothing measured says it fits.
2. **LLM throughput and cost at ~1,000 sheets.** Unknown until the pilot in W42. That is late, so the pilot
   must not slip.
3. **That a crossover exists before the context wall.**
4. **Neo4j load time at scale.** Unmeasured.
5. **That the user can review and commit at the pace the coder produces.**
6. **EX01 is ChatP&ID's file.** Strongly supported, not proven, and its condensed size differs (36 vs 53).
