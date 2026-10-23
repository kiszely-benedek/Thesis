---
adr: 0023
title: The headline corpora use drawing-only connector labels, like real P&ID flags
status: accepted
date: 2026-09-29
accepted: 2026-09-29
supersedes: none
---

# ADR-0023 — Connector labels in the headline corpora

**Question.** The splitter can write off-page connector flags in two styles. Which one do the headline corpora
(ADR-0015) use?

**Options**
- **FULL** (the `SplitConfig` default so far): the flag also names the partner connector's own number. Easier than
  reality — a real flag does not carry it.
- **DRAWING_ONLY**: the flag names the target drawing, the line number and the fluid only.
- **Both**: run the headline twice and compare; doubles the runs.

**Decision: DRAWING_ONLY** (user, 2026-09-29).

**Why.** Real flags look like this. OPEN100 pair 1/24 ↔ 2/13 (crops in `30-experiments/open100-stage1/recheck_2026-09-05/`):
sheet 1 reads "PID 160-1 (F-1) / CND RECEIVER TANK VENT", sheet 2 reads "ACC PID 150-1 / ACC VACUUM PMPS", and the
line carries `SIZE-ACC-160090-SPEC-HC-X` on both — target drawing, description and line number, no partner
connector number (and its grid reference F-1 is even wrong). On a 4-unit plant the resolver still pairs all
15 connectors at DRAWING_ONLY (14 by line number, 1 by service and direction; main-session run, 2026-09-27).

**Costs.** The ingest CLI needs a `--label-detail` flag; the resolver gate (G1) must hold at DRAWING_ONLY on every
headline corpus, and SMOKE-04 is re-run in that style before the headline.

**Revisit if** the resolver leaves connectors unresolved at a headline size in this style.
