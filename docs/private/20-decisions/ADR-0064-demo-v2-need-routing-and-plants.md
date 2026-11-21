---
adr: 0064
title: Upgrade the demo to V2T-A by a demo-side need router over two label-free derived policies run by the unchanged frozen live cascade, and show the sealed test plants H1000g2 and H100g2
status: accepted (user, 2026-11-05: routing 1A "ok"; Neo4j ends on H1000g2 "JA EZ JÓ HA átáll"; every other open question "maradék mind az ajánlás szerint"); amended 2026-11-20 (EXP-0008 plants, freeze E9, sources; user decisions 2026-11-20 in chat; see "Amendment 2026-11-20" at the end)
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

## Amendment 2026-11-20 — EXP-0008 plants, freeze E9, sources

**Why.** The decision above was written against EXP-0007 (plants H1000g2 / H100g2, freeze E8 `4dfad69`). ADR-0065
then fixed the code-review findings, and EXP-0008, the clean v2 re-run, finished on 2026-11-17 (`e54546e`, notes
`e54a495`). Its numbers supersede EXP-0007 R4 / R5 / INFRA-2 and EXP-0004 P4 (ADR-0065 line 6). ADR-0065 line 6
already says "Amends ADR-0064 (the demo's plant becomes H1000g21p1)"; this section records what that means. The
user decided points 2 and 4 below in the chat on 2026-11-20. The design note `40-design/demo-v2.md` is updated to
revision 2.

**What changes.**

1. **System name and freeze.** The demo runs **V2T-A2**: `cascade_v4_iso` as frozen at **E9**
   (`data/runs/exp0008/prereg/E9.commit` = `5d31cbb94620645ee018771735edae37f49e7ef8`, `E9.sha256` 515 lines).
   The policy file is unchanged since `ee8e164`; V2T-A2 is V2T-A plus the review fixes, with no new tuning
   (`40-design/review-fixes.md:128`). E9 hashes every tracked file under `src` except `src/plantgraph/demo`, plus
   `pyproject.toml` and `uv.lock` (`stages/m3_freeze.sh:14-16`). This now includes `qa/need/*` and `qa/anchors.py`,
   so the freeze gap noted under Consequences is closed. The live code still refuses label routing
   (`qa/cascade/live.py:157-163`, called at `:178` and `live_build.py:165`), so option 1A is still needed and still
   sufficient. The demo adds no dependency, because `pyproject.toml` and `uv.lock` are frozen.
2. **Plants (user, 2026-11-20).**
   - **H1000g21p1** is the main plant: 1,000 sheets, 93,171 nodes, 312,868 relationships, `plant_lines`
     (`data/runs/exp0008/neo4jplant/H1000g21p1/ingest.json`).
   - **H100g21p1** is the small plant: 100 sheets, 9,449 nodes, 31,666 relationships, `plant_lines`.
   - Both are plant 1 of their scale in EXP-0008. They are also the INFRA pair (`infra/report.json` `growth`).
   - The user's `neo4j` database already holds H1000g21p1: the launcher's last line before DONE is "the database
     ends on H1000g21p1 (plant_lines)" (`data/runs/exp0008/run_all.log`). So the demo needs **no plant switch**
     to reach its end state. The standing rule becomes "end on H1000g21p1".
   - The v1 config (`data/runs/cv1/demo/demo_config.json`) stays runnable.
3. **Sources.** Every input comes from EXP-0008:
   - questions: `data/runs/exp0008/questions/<c>/questions.jsonl`, 280 per plant;
   - ingest records: `neo4jplant/<c>/ingest.json`;
   - tier runs: `m6a/runs/S7-CYP-<c>`, `S7-AG-<c>`; recorded F1 runs: `m6b/runs/S7F1-CYP-<c>`, `S7F1-AG-<c>`;
   - cache: `m6a/cache.sqlite`, used only as a copy, in the replay check;
   - reports: `reports/sealed`, `reports/f1_baseline`, `reports/ladder`, `infra/report.json`, `reports/e2e`.
   The demo shows two kinds of EXP-0008 row:
   - the **pooled** five-plant rows (`S100`, `S1000`, with two-stage bootstrap intervals): these are the thesis's
     headline numbers;
   - the demo plants' **own** rows (Wilson intervals) beside them.
4. **Results tab gains a small tag-identity end-to-end table (user, 2026-11-20).**
   - It shows the arms R5 / V-d0 / V-d2 / V-d4 and the claims E1–E4, read from
     `data/runs/exp0008/reports/e2e/report.json`.
   - The report's own title reads "EXP-0004". That title is a mislabel in the shared report code. The demo cites
     the file and the EXP-0008 results row, never the title.
   - The report's `spend_usd` column is not shown, because the report's own note says it "is not a cost per arm".
5. **Data directory.** Every new demo file goes to `data/runs/exp0008/demo/`: config, examples, drawings and
   calls log. No E9-hashed path is under it. `data/runs/exp0007/demo/` is not created.
6. **Thesis statement (replaces the one under Consequences).**
   - The demo shows two sealed EXP-0008 test plants, H1000g21p1 and H100g21p1, after the single sealed test run
     (EXP-0008 M6, finished 2026-11-17), on the frozen V2T-A2 (E9 `5d31cbb`). No file hashed in E9 changed for
     the demo.
   - The sealed questions of these two plants become public when shown. Any later system change needs a new
     sealed set (ADR-0053).
   - Live demo answers are new model calls, not measurements, and they change no EXP-0008 number.
7. **Cost (replaces the cost bullet under Consequences).** The figures were recomputed with the demo's own
   `estimate_cost` on the EXP-0008 tier runs (design note §6).
   - The upper bound per question at H1000g21p1 is $0.03074: the worst Cypher cost, $0.01132, plus the worst agent
     cost, $0.01943.
   - The reservation is $0.0461, so the $5 session cap holds 108 reservations. It needs no change.
8. **Startup (replaces the startup bullet).** At H1000g21p1, startup with a rebuild takes 390.64 s and startup
   without one takes 5.53 s (`infra/report.json` `growth` `startup.total`, `startup.without_rebuild`).
9. **Ladder scope follows the report (refines design §10.4).** The demo's ladder uses the **common** families,
   because EXP-0008 reports its ladder and its claims X1 / X2 on that scope (`reports/ladder/report.json` `claims`,
   `EXP-0008-v2-rerun.md` "Ladder"). EXP-0007 R4 reported on all families. The scope stays a config value.
10. **Isolation pick (refines design §10.5).** Only 10 of the 15 UPSTREAM_ISOLATION questions per plant are routed
    to the agent: the five wording variants ("Before maintenance on …") do not match the isolation rule
    (`qa/need/rules.py:53`). So the isolation step of the presentation takes the first UPSTREAM_ISOLATION example
    that the router sends to the agent. The route is decided by the free classifier before any answer exists, so
    the pick still does not depend on the outcome. With the declared seed 20261105, both drawn UPSTREAM_ISOLATION
    examples are routed on both plants (computed 2026-11-20 with `examples.select_per_family` and the rule
    pattern). So today the pick is the same as the plain first-of-family pick. The refinement only matters if the
    examples are redrawn.

**What stays unchanged.** These parts of the decision stand as accepted:
- Option 1A: a demo-side need router over two label-free derived policies, each run by the unchanged frozen
  `LiveCascade`, with the need label and start tier shown on the answer card.
- Option 2A in substance: the sealed test plants, main at 1,000 sheets and small at 100.
- The rationale.
- The live-deadline consequence and its measurement by T6.
- The revisit triggers. "A later freeze" now means any freeze after E9.
- Every other open question of design note §10: Results v2 only, the declared first-of-family presentation rule
  (refined only by point 10), v1 runnable, accept the startup time, a paid smoke only after the free checks.
