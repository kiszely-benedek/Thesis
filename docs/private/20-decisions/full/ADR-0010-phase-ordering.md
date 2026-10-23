---
adr: 0010
title: Split cross-sheet entity resolution — a thin resolver in ingest before retrieval, its evaluation after the crossover
status: accepted
date: 2026-09-25
accepted: 2026-09-26
supersedes: none
---

# ADR-0010 — Phase ordering: where entity resolution goes

## Context

The roadmap (`00-index.md`, "Roadmap") orders the remaining work: **2** single-sheet baseline (reproduce
ChatP&ID) → **3** scale-out, find the crossover → **4** cross-sheet entity resolution → 5 later phases →
6 write-up. Three things changed on 2026-09-20 and 2026-09-25:

- **The title leads with construction.** "Tudásgráf-építés … skálázható Q&A rendszerhez" — knowledge-graph
  construction first, Q&A second (`00-index.md`, "Official title"). The framing decision of 2026-09-20 says
  the pipeline leads and the crossover is supporting evidence.
- **Input is settled** (ADR-0008 R1; ADR-0009 I4): per-sheet graphs, from the splitter or a Proteus importer.
- **The Q&A half does not exist.** No retrieval, no QA, no Neo4j loader. Neo4j Desktop 2 is installed on the
  development machine; nothing in the repo uses it.

Time: limited; the exact date was not yet known on 2026-09-25.

**The technical fact that shapes the options.** `rejoin()` (`src/plantgraph/benchmark/rejoin.py`) reconstructs
the plant **from the `SplitManifest`** — it reads `connector_pairs[*].original_edge` and `identity_groups` —
that is, from the answer key. It is a round-trip test for the splitter, not a resolver. A resolver may use
**only what is on the sheets**: each `OffPageConnector`'s `partner_sheet_id`, `partner_tag`, `direction`,
`line_number`, and equipment tags. On synthetic sheets those labels are clean and structured, so resolution is
expected to be **near-trivial**: pairing is a lookup, identity is tag equality. The hard cases are real labels
— OPEN100's `raw_text`, three `MatchRule` confidence levels, sheet references written three ways (`SheetRef`
docstring) — and tag variants (the `RCS-PU-102A` / `RC-P102A` example in the `IdentityGroup` docstring,
`src/plantgraph/benchmark/models.py`).

## Options considered

**O1. Keep the current order** (baseline → scale-out → ER). Q&A risk is attacked first. But the crossover
experiment then runs on the **unsplit plant graph** (nothing else joins the sheets), so the multi-sheet
benchmark contributes nothing to the headline experiment, and the pipeline is not end-to-end
(ingest → resolve → answer) until the last technical phase. Poor fit for a title that leads with construction.

**O2. Move ER entirely first** (resolver and its evaluation, then baseline, then scale-out). Matches the
pipeline order. But ER *evaluation* needs OPEN100 label parsing held out under ADR-0007 decision 3 and a
noise-injection harness — real work — while every Q&A unknown waits behind it. The biggest risk is attacked
last.

**O3. Split ER in two.**
- **(i) A thin resolver as a pipeline stage** in a new "KG construction / ingest" phase, before retrieval:
  sheets → resolved plant graph, using only on-sheet information. Its gate is `resolve(split(plant)) == plant`
  under the equality the splitter's round-trip test already uses (`splitter.md` §4, cited in `rejoin.py`).
- **(ii) ER evaluation** — EXP-0004 on **OPEN100's 23 held-out cross-sheet pairs** (ADR-0007, Context and
  decision 3) plus injected label noise — **after** the crossover experiment.

### The two arguments, stated fairly

- **Engineering / title argument → resolver first.** The title's first half is KG construction. A Q&A system
  over a plant region must stitch sheets before it can answer across them; the pipeline order is
  ingest → resolve → answer. Building in that order yields a working end-to-end system early.
- **Risk argument → Q&A first.** The Q&A half is the biggest unknown: the EX01 file (not in the repo; which
  public file ChatP&ID used is unverified — ADR-0009), **whether ChatP&ID's 19 QA pairs are published**
  (unverified; `2603.22528.md` gives the categories, not the questions), LLM access and budget (unknown),
  Neo4j (installed, unused). A resolver over clean synthetic labels is low-risk. Spending the first weeks on
  the low-risk part is the classic scheduling mistake.

**O3 reconciles them.** The thin resolver is small precisely because synthetic labels are clean, so it costs
little calendar time; the de-risking spikes run **in the first week alongside it**. Coders run one at a time
(`CLAUDE.md`, ADR-0006 as amended), so "alongside" means: the non-code spikes (question-set availability, LLM
access, identifying the EX01 file) go to the `researcher` agent and the main session in parallel; the code
spikes (EX01 import, a Neo4j load of one sheet) queue with the resolver on the single coder.

## Decision

**O3.**

1. **New Phase 2, "KG construction / ingest":** the ADR-0009 Proteus importer, a thin resolver, a Neo4j
   loader, and the week-1 spikes. The resolver's gate is the equality above. It must pass on sheets that obey
   the ADR-0009 contract rule (no shared cross-sheet node ids), or the gate proves nothing.
2. **The gate is a correctness gate, not a thesis result.** On clean synthetic labels the equality is
   expected to hold; reporting it as "ER accuracy 100 %" would be wrong. The evaluation value comes from
   OPEN100 and from noise.
3. **EXP-0002 runs on the resolved graph, with the equality asserted.** If the equality fails on a corpus,
   EXP-0002 runs on the oracle (unsplit) graph for that corpus **and reports both**, so a resolver defect can
   never silently shape the crossover.
4. **ER evaluation (EXP-0004 + noise) comes after the crossover experiment.** OPEN100 stays held out
   (ADR-0007 decision 3): its 23 pairs are never used to develop label parsing.

## Rationale

- **Serves the title and the claim together.** The crossover (EXP-0002) runs over a graph the pipeline built
  from sheets, so the benchmark's cross-sheet structure is exercised by the headline experiment, not bypassed.
- **Early partial result.** After Phase 2 the system ingests a DEXPI file and a multi-sheet corpus and holds
  both in Neo4j — a demonstrable pipeline even if later phases slip.
- **Risk is still front-loaded.** Every Q&A unknown is touched in week 1; if one fails (no question set, no LLM
  budget), it surfaces while there is time to re-plan.
- **Honest measurement.** Splitting "resolver exists" from "resolver is evaluated" stops the trivially clean
  synthetic case being passed off as an ER result.

## Consequences

**Proposed roadmap** (phases renumbered; the user edits the index):

| Phase | Goal | Notes |
|---|---|---|
| 0 | Repo, docs, agents, benchmark generator design | closing |
| 1 | Synthetic multi-page benchmark with known cross-page ground truth | in progress; utilities deferred per ADR-0007 |
| 2 | **KG construction / ingest** — Proteus importer (ADR-0009), thin resolver with the `resolve(split(plant)) == plant` gate, Neo4j loader; week-1 spikes: EX01 file, ChatP&ID question set, LLM access, Neo4j | new |
| 3 | Single-sheet baseline — reproduce ChatP&ID on the EX01 file (EXP-0001) | was 2 |
| 4 | Scale-out — hierarchical retrieval, find the crossover (EXP-0002) on the resolved graph | was 3 |
| 5 | Cross-sheet ER evaluation — EXP-0004 on OPEN100's 23 held-out pairs, plus injected label noise | was 4, now evaluation only |
| 6 | Later phases per ADR-0007: rule-grounded realism, utilities, several plants per corpus, rendering | was 5 |
| 7 | Write-up | was 6 |

**Makes easy** — an end-to-end demonstration early; one code path from ingest to answer for both EXP-0001
and EXP-0002.

**Makes hard** — the resolver's real test (Phase 5) comes late; if it exposes a design flaw, the crossover
numbers were produced by the thin version. Mitigated by decision 3 (oracle fallback, both reported) and by the
gate.

**Needs** — a design note in `40-design/` for the resolver. It must fix:
- the resolver's input type. Synthetic sheets carry `OffPageConnector`; OPEN100 carries
  `ConnectorObservation`. `models.py` says both feed the same `SplitManifest` so later code cannot tell them
  apart; the resolver needs a common connector view to be scored on both;
- its output: predicted `ConnectorPair`s and `IdentityGroup`s, scored against the manifest;
- the noise model for Phase 5 (which label fields are corrupted, at what swept rates — rates to be taken from
  a source, not invented).

**Revisit if:**
- a week-1 spike fails (no EX01 route, no question set, no LLM access) — re-plan Phases 3–4 before building
  the loader further;
- the thin resolver does not pass its gate on contract-clean sheets — then EXP-0002 runs on the oracle graph
  per decision 3 and this ordering is reconsidered;
- the exact deadline turns out earlier than December 2026.

## Outcome log

- **2026-09-26:** Accepted by the user 2026-09-26 as recommended (O3). The deadline was corrected the same day; the week counts in this ADR's context are stale, the ordering is not. See `40-design/thesis-phase-plan.md` revision 2.
