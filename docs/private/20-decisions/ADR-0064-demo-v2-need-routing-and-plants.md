---
adr: 0064
title: Upgrade the demo to V2T-A by a demo-side need router over two label-free derived policies run by the unchanged frozen live cascade, and show the sealed test plants H1000g2 and H100g2
status: accepted (user, 2026-11-05: routing 1A "ok"; Neo4j ends on H1000g2 "JA EZ JÓ HA átáll"; every other open question "maradék mind az ajánlás szerint")
date: 2026-11-05
supersedes: in part — ADR-0049 line 109 ("the demo refuses a label-routing policy"); ADR-0056 point 2 ("D1000 now" as the plant Neo4j holds). The rest of ADR-0049 and ADR-0056 carries over unchanged.
design: 40-design/demo-v2.md
---

# ADR-0064 — Demo v2: need routing without touching the freeze, and which plants

## Context

The thesis now reports V2T-A: `cascade_v4_iso`, GPT-6 Luna on both tiers, setting A, frozen at E7 (`fdad31f`) and
re-identified as E8 (`4dfad69`, ADR-0063). The demo still runs v1 (`cascade_v3` on D100 / D1000). The user approved
the upgrade on 2026-11-05 ("Frissítsük v2-re, mehet a felmérés").

Two facts make this non-obvious (design note §2):

- The frozen live cascade refuses any policy with `start_tier_by_label` (`qa/cascade/live.py:157-163`, called at
  `live_build.py:165`). `cascade_v4_iso` routes the labels UPSTREAM_TO_FIRST_VALVE and DOWNSTREAM_TO_FIRST_VALVE
  straight to the agent tier; that routing is its only difference from `cascade_v4`. Run today, the frozen code
  refuses it. Both files are frozen (`tune_lib.sh:105`, hashed in `E8.sha256`).
- R5 took each label from the rules classifier `classify_need(text, anchor_finder(view))`
  (`qa/cascade/labels.py:25-33`, `join.py:121-140`, `report.py:102-111`). The classifier is free and reads only the
  question text and the tags and units in it.

Separately, a v2 demo needs a v2 plant, and the user's Neo4j database holds one plant (user rule; today v1 D1000).

## Options considered

### 1. How the demo runs V2T-A's need routing

**A. Demo-side router (recommended).** The demo classifies the question with the same frozen function R5 used,
then asks one of two derived policies built in memory from `cascade_v4_iso`: start 0 (both tiers, labels removed)
or start 1 (the agent tier alone, fallback off). Each runs in the unchanged frozen `LiveCascade`. The decisions are
identical for every label and every signal combination (`accept.py:66-74`, `:106-107`; `policy.py:73-80`; proof in
design note §2.2, pinned by an exhaustive offline test). No frozen file changes; E8 stays valid. Cost: one small
module, a second opened cascade per corpus (memory, measured in check F4).

**B. Teach the frozen live cascade a need label.** Add `need_label` to `LiveCascade.ask` and drop the refusal. The
cleanest code, but it edits two E8-frozen files. The freeze would need a new identification (replays with Neo4j),
and demo work would be mixed into the system the thesis reports, while EXP-0004 is running on E8.

**C. Run `cascade_v4` live instead.** Needs no code: it has no label routing. It is not V2T-A, though. `tune_select.py`
chose `cascade_v4_iso` before the test, and the two differ on R5 (headline 0.907 vs 0.911 at H100g2). The demo would
show a system that the thesis does not report as its own.

**D. Run `cascade_v4_iso` with its routing removed.** A one-line policy copy. It answers isolation questions
differently from the evaluated system and is labelled as if it were V2T-A. Rejected as misleading.

### 2. Which plants the v2 demo shows

**A. The sealed test plants H1000g2 (main) and H100g2 (small) (recommended).** These are the plants R5's headline
numbers were measured on. R5's tier runs give each tier's settings, the cost evidence and a recorded answer for
every example, all from the same plant. The `plant_lines` ingest records are ready. The sealed questions become
public, but the test ran once on 2026-10-31 and the system is frozen, so this does not contaminate R5. The thesis
states it (below).

**B. The validation plant X1000g2s213.** A dev plant, run once in V2T-VAL. It has only 163 dev-family questions, its
ingest record has the `plant` profile (a new `plant_lines` ingest is needed), and there are no R5 numbers on it.

**C. A fresh dev plant built from the dev seed.** Untouched. It needs a new ingest (INFRA-2: 456.2 s at 1,000
sheets) and has no questions or recorded runs. The demo would not show the plant the numbers come from.

## Decision

1. Option 1A. A demo-side need router over two label-free derived policies, each run by the unchanged frozen
   `LiveCascade`. Every change lives in `src/plantgraph/demo/**`, `tests/test_demo_*.py` and
   `data/runs/exp0007/demo/`. The derived policies keep the name `cascade_v4_iso`. The answer card shows the need
   label and the tier it started at.
2. Option 2A. H1000g2 and H100g2. The v1 plants leave the v2 demo, and the v1 config stays runnable. At the end of a
   session, the user's `neo4j` database holds H1000g2 (`plant_lines`) instead of v1 D1000 (needs the user's yes,
   because it changes the standing rule).

## Rationale

- **Freeze first.** The thesis claim rests on R4 / R5 numbers from a frozen system. A demo that edits the freeze
  (1B), or shows a neighbouring system (1C, 1D), would weaken the one-sentence answer to "is this what you
  measured?". Option 1A answers yes, and offline replays (task T6, check F5) can test that answer at no cost.
- **Boring option.** 1A only calls frozen functions. Its single new idea, slicing the tiers by start index, is
  proved exhaustively on a toy model.
- **Plants.** The claim is about scale. Showing R5's 100- and 1,000-sheet plants side by side, with the Results
  tab's numbers measured on those same plants, is the most direct way to show it.

## Consequences

- The demo answers with V2T-A as evaluated. One difference from the offline walk was already there in v1: an
  escalated question gives the agent what is left of the 120 s, while R5's agent row ran with the full 120 s
  (`live.py:97-113`, `attempt.py:85-91`). T6 measures how often this changes an answer.
- Found during this work: the classifier files `qa/need/` and `qa/anchors.py` decide V2T-A's routing but are not
  in `V2T_FROZEN_FILES` or the E7/E8 hashes. They are unchanged since E7, so R5 stands. The thesis lists them with
  the frozen system, and T6 records their diff on every run.
- **Thesis statement.** The demo shows the sealed test plants after the single test run, on the frozen V2T-A, with
  no system file changed. Its live answers are new model calls, not measurements. The sealed questions are spent:
  any later system change needs a new sealed set (ADR-0053).
- Each live ask costs about $0.0014–0.0025 (R5 $/question). An upper bound per question at H1000g2 is
  $0.03123 (the worst Cypher cost plus the worst agent cost seen in R5). The $5 session cap needs no change.
- Startup at H1000g2 rebuilds the plant (INFRA-2 `startup.total` 408.34 s): start the server early.
- **Revisit if** T6 shows disagreement on fully cached walks (the router is then wrong), if memory with two opened
  cascades does not fit (check F4), or if a later freeze changes `cascade_v4_iso`.
