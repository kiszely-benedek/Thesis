---
adr: 0024
title: A demo application — the plant's drawing set on the left, questions on the right — after the headline
status: accepted
date: 2026-09-29
accepted: 2026-09-29
supersedes: ADR-0011 item 5a (rendering to PDF) in part
---

# ADR-0024 — Demo application

**Question.** Should the thesis include an application that shows a generated plant as a multi-page drawing set
and lets the user ask questions about it?

**Options**
- **No demo** (ADR-0011 item 5a cut rendering).
- **A demo after the headline experiment**, with a simplified drawing style.
- **A demo as early as possible**, in parallel with the Q&A system.
- **Only if time remains.**

**Decision: after the headline experiment** (user, 2026-09-29; the user's idea: *"generálunk egy nagy plantet, arról
kap a felhasználó az appon belül egy hosszú pdf-et … majd tőle jobbra tudja kérdezgetni a felépített gráfot"*).
1. **Simplified drawings**, not engineering symbols: items as labelled shapes, pipes and signal lines as lines,
   and off-page connector flags at the sheet edge in the ADR-0023 style (target drawing + line number).
2. One multi-page PDF per corpus, one page per sheet.
3. A small web UI: the PDF on the left, questions on the right; an answer shows which sheets its evidence crosses.
4. The demo answers **from the replay cache by default** (ADR-0014), so it runs without paid calls; live questions
   only with explicit approval.
5. Design note by the architect first; coder tasks after the headline runs (CP3, 2026-10-17).

**Why.** A working end-to-end demo fits the engineering framing, shows the whole pipeline in one screen at the
defence, and costs nothing to run from the cache.

**Costs.** An estimated 4–5 coder tasks (renderer, PDF assembly, UI, wiring) — an estimate, not measured. It competes
with writing time in the last two weeks; if the headline slips, the demo shrinks before the headline does.

**Revisit if** the headline runs are not done by 2026-10-17.

## Outcome log
- **2026-09-29** Scope widened by the user: *"mehet minden ki a UI-ra és onnan is lehessen akár teszteket generálni"* —
  the UI becomes the control panel for the whole system, including generating question sets. Layered so the core
  lands first:
  - **Must:** pick a saved corpus → its drawing set as PDF on the left; ask a question on the right; the answer shows
    the evidence sheets and k. Replay-cache answers by default.
  - **Should:** generate a new plant from the UI (units, sheet budget, seed, label style, duplication) and view it;
    generate a question set (families, k-bins, seed) and browse it with its computed reference answers.
  - **Could:** start an evaluation run from the UI and view the results table — **paid calls only behind an explicit
    confirmation with the estimated cost shown first** (ADR-0014 paid-call guard).
  Everything the UI does calls the same library functions as the CLI (one code path, `qa-system.md` §18.1 item 1).

