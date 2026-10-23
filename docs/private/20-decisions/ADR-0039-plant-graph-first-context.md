---
adr: 0039
title: Build the Hierarchical family's context from the merged plant graph (the in-memory ItemGraph), keep the selection unchanged, and keep the occurrence-graph arms only as a baseline sample
status: accepted
date: 2026-10-03
supersedes: in part — ADR-0022 decision S1 for Hierarchical and every need-aware variant (ContextRAG keeps S1 on EX01 under ADR-0038). Amends ADR-0036 Decision point 6 and its design note §A.8 (who reads what). Amends ADR-0035 before F1 (claims read on the plant arms; Q5 re-pointed; new Q7). ADR-0030's selection rule and the ROUTE-01 outcome stand unchanged.
design: 40-design/plant-graph-first-and-effort-routing.md Part A, Part B
---

# ADR-0039 — The plant graph first, for every arm that serializes a graph

## Context

The user (2026-10-03): "csak az üzemgráfon kellene teljes egészében tesztelnünk" — test on the plant graph throughout.
ADR-0036's outcome log already made the plant layer the primary target, but only CypherRAG has a plant arm planned
(`cypher_rag_plant`, MP-T4). Hierarchical and the need-aware variant still serialize the **occurrence** graph
(ADR-0022 S1): every drawn symbol, off-page connector stubs, `continues_as`, `same_tagged_item_as`.

Evidence that this costs answers, not just characters:
- PAID-04 (`_results.md`): NEIGHBOURS_DOWNSTREAM T-11-1 — GLM and Sonnet both answered `[]` with evidence-node recall
  1.0. A free probe on H100 rebuilt in memory (design note §2 F1) shows why: both of T-11-1's outgoing edges end at
  off-page stubs, so its neighbours appear only as `T-11-1 → stub → continues_as → stub → CHV-11-3`. The shared final
  prompt never says what a stub or `continues_as` is (`qa/prompts/final_answer.txt`), although CypherRAG's query writer
  is told (`qa/schema_text.py`).
- LOOP_ACTUATED_VALVE FIC-30-6: the controller is on sheet 70, the actuator and valve on sheet 69, joined by two signal
  stubs (same probe).

The plant API already walks the merged graph (`ItemGraph`, QAR-T2): API-01 matched 38,286 of 38,286 gold edges by tag
at H1000. The equality "Neo4j plant layer = `ItemGraph`" is **designed (PLANT-01 part e) but not yet run** — it waits
for MP-T3.

## Options considered

**A. Status quo.** Hierarchical family on the occurrence graph; plant only for CypherRAG and the agents. Contradicts
the user's instruction and leaves the stub-chain failure in the primary arms.

**B. Same selection, plant rendering from the in-memory `ItemGraph`.** The sheet selection (ADR-0030 pair) and the
need programs (ADR-0033) stay exactly as built; a new renderer maps the selected drawings to plant items and writes
items with direct item-to-item edges. The difference between `hierarchical` and `hierarchical_plant` is then the
representation alone, and ROUTE-01's selection numbers still hold. No database in free runs.

**C. As B, but read the Neo4j plant layer at question time.** "The KG is the system" in the most literal sense. But
free reports (route, need, API) would need a database; a run mixing an occurrence arm (`cypher_rag`) with a plant arm
would need two profiles at once, which ADR-0036 refuses; and the equality it relies on is not yet measured.

**D. Re-implement the selection over items** (routes and rings computed on `ItemGraph`). Cleaner on paper; changes two
things at once (selection and representation), duplicates tested code, and voids ROUTE-01 for the new arms.

**E. Both representations as equal primary arms everywhere.** Doubles every paid Hierarchical run under the $25
budget for a comparison a sample answers.

## Decision

**B.**
1. **Source.** The in-memory `ItemGraph`, built only from the resolver's occurrence view (import ban unchanged), gains
   the visible node properties of each item's home drawing and the visible edge properties of each item edge, plus a
   drawing-key → item index (PG-T1). The Neo4j plant layer serves `cypher_rag_plant`, `cypher_agent` and the demo;
   PLANT-01 part (e), extended to the new properties, checks that the two are equal before any reported run.
2. **Selection unchanged.** Sheets, routes, rings, through-lines and need programs are computed as today. Only the
   rendering changes: the selected drawings (full sheets and through-line keys) map to their items; the context holds
   those items, every item edge between them, and the **frontier** — items one edge outside the selection, with that
   edge — so a line leaving the excerpt still says where it goes (the plant analogue of a stub's drawing reference).
3. **What the model sees.** One node per item with its visible properties and `sheets` (every sheet it is drawn on);
   one edge per item edge with its visible properties and `crossed_sheets` when no sheet draws it whole. No stub
   nodes, no `continues_as`, no `same_tagged_item_as`. Same GraphML writer, opaque item ids (one change at a time).
4. **Legend.** Each representation carries a short fixed legend at the top of its context (the plant one explains items,
   `sheets` and `crossed_sheets`; the occurrence one explains stubs, `continues_as` and identity links, from the text
   CypherRAG already receives). Both live under `qa/prompts/`, so F1 hashes them.
5. **Names.** `hierarchical_plant` and `hierarchical_need_rules_plant` (later `_labelprob_plant`, `_jev_plant`) are the
   primary arms. The unsuffixed names are the occurrence baseline and, with default parameters, produce today's
   contexts byte for byte (PAID-01…04 replay). The occurrence arms take `legend: bool` (default false); baseline runs
   in EXP-0006 set it true.
6. **Baseline sample.** At H100 and H1000, the occurrence `hierarchical_need_rules` and `cypher_rag` run on the
   first-stage slice only (5 questions per family per corpus), at the EXP-0006 pin, legend on.
7. **Free metrics on the plant graph** (design note §A.8): evidence-item recall (an evidence node counts if its item
   is in the context); evidence-edge hops (serialized edges between the two ends of each evidence edge — 1 means
   readable in one step); path in context (FLOW_PATH, CONNECTED-yes); context items, sheets and characters. Strict and
   relaxed sheet routing stay as built and equal across representations by construction (a test).
8. **ADR-0022.** S1 is superseded for the Hierarchical family. ContextRAG keeps S1 on EX01 (ADR-0038), where there are
   no connector pairs or identity groups, so the two representations differ only in the sheet attribute; its
   H100/H1000 "did not fit" line records both prompt sizes (free).
9. **ADR-0035, before F1** (nothing has been measured under it): Q1–Q4 are read on the `_plant` arms; Q5 becomes
   `graph_agent` − `cypher_rag_plant` (typed vs free-form on one graph); new claim **Q7**: at H1000, on the baseline
   sample, `hierarchical_need_rules_plant` − `hierarchical_need_rules` > 0 with a paired 95 % CI excluding 0, reported
   per k-bin. Wording if not: "the merged representation does not help the serializing arm".

## Rationale

- The registered title is knowledge-graph construction for a scalable Q&A system; the constructed graph is the plant
  graph, so the primary arms should read it. It also restores ADR-0022's own principle at the plant level: every
  primary arm (Hierarchical family, agents, `cypher_rag_plant`) now reads the same merged resolver output.
- Holding the selection fixed makes the representation effect measurable on its own (Q7, and free metrics such as
  evidence-edge hops), which is what the T-11-1 failure points at. Option D would blur it.
- In-memory is the boring choice: the plant API already uses it, free runs stay database-free and re-runnable by the
  professor, and the store equality becomes a check instead of a dependency.

## Consequences

- Easy: one plant object behind every non-Cypher arm; SHEETS_OF_TAG is answered from one attribute; a cross-sheet
  neighbour is one edge.
- Harder: `ItemGraph` grows two fields and an index (PG-T1, after MP-T1 is committed, because `plant_api/model.py` is
  in MP-T1's diff); the budget fitter and the need context take a renderer (PG-T2).
- The frontier gives the plant arms the far item's identity where a stub gave only a sheet number. That is the merged
  representation's information, stated as part of what Q7 measures.
- Context size of the plant rendering is unmeasured; PROMPT-02 measured whole-plant GraphML at about 1.35× larger for
  the occurrence graph, an estimate only for a selected excerpt. PG-01 measures it.
- **Revisit if** PLANT-01 (e) finds any difference between the stored layer and the extended `ItemGraph`; PG-01 shows
  plant contexts larger than occurrence contexts for the same selection on most questions (then the frontier rule is
  wrong); or Q7's baseline sample is cut by the budget (then Q7 is reported as not run, not weakened).

**Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet")** Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet") with the main session's recommendations. Source: in-memory item graph; frontier items: yes; a short legend on both representations: yes (the T-11-1 failure showed an unexplained representation is a confound).

**Outcome log 2026-10-03 (main session, free inspection after PG-P1):** the suspected merged parallel relation (`a|b`) did not occur in the inspected INSTRUMENTS_OF_ITEM plant context (relations: send_to 27, send_signal_to 6, control 3, measured_by 3; `E-42-2 -measured_by-> PT-42-5` present). Neither legend states the direction of `measured_by` (an edge X → Y reads "X is measured by Y") or of `control`. Fix for both legends alike (fairness), bundled with PR-T1: one sentence per instrument relation stating its reading direction.
