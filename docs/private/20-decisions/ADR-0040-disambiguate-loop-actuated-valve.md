---
adr: 0040
title: Reword LOOP_ACTUATED_VALVE (template version 2) so it asks for the valve the loop's actuator moves, not "the valve of the loop"
status: superseded
date: 2026-10-03
supersedes: none — amends one dev-old template (qa-system.md §9 table; ADR-0013 scoring unchanged)
design: 40-design/plant-graph-first-and-effort-routing.md §B.3
---

# ADR-0040 — LOOP_ACTUATED_VALVE is ambiguous under instrument-tag conventions

## Context

Template v1: "Which valve is actuated by control loop {loop_tag}?" Reference: the tag of the valve at the end of
controller `-send_signal_to->` actuator `-control->` valve (`qa/questions/families_loop.py`).

Measured (free probe on H100 rebuilt in memory, design note §2 F2): the actuator node (`ActuatingFunction`) carries the
tag `FV-30-6` and `loop_tag` `FIC-30-6`; the valve body is `GV-30-4` and carries no loop tag. All 254 actuators in H100
carry a tag starting PV, FV, LV or TV. Under the instrument tag convention the repo already cites
(`pid-structural-rules.md` L17: function letters per ISA-5.1 plus a loop number, "FIC045 … The same loop may have
FT045"), "FV-30-6" reads as the flow valve of loop 30-6 — the final control element itself.

PAID-02/03 (`answers.jsonl`): every wrong answer that named a tag named the actuator — `FV-30-6` three times,
`TV-27-1` once; the other misses were `not_present` (Hierarchical on TIC-27-1, whose evidence-node recall was 0.333)
or CypherRAG retrieval errors. A P&ID-literate reader can defend that answer. A primer written from the cited tag convention (ADR-0041) would
push models further toward it.

## Options considered

**A. Leave v1.** No work. Every LOOP_ACTUATED_VALVE question keeps two defensible answers, one scored wrong.

**B. Accept the actuator's tag as correct too.** Free re-scoring. The answer stops being unique, and a model that
never follows `control` is rewarded.

**C. Template v2:** "Control loop {loop_tag} drives an actuator. Which valve does that actuator move? Answer with the
valve's own tag, not the actuator's." Reference unchanged. The same text reaches every strategy, so fairness holds.

**D. Change the generator** so the valve body carries the loop's tag and the actuator none (closer to common practice).
Every corpus and every measurement so far (SMOKE, ROUTE, NEED, API) would have to be re-run.

## Decision

**C.**
1. `template_version` "2" for LOOP_ACTUATED_VALVE; reference, evidence, `k` and `u` unchanged.
2. The rules classifier's pattern for this family is updated from the v2 template (a dev template, before F1).
3. Question sets are regenerated; `question_set_sha256` changes. PAID-01…04 were never reported, so nothing reported
   changes.
4. LOOP_MEASURED_EQUIPMENT is not affected (its answer is an equipment tag, with no competing instrument tag).

## Rationale

- A benchmark question with two defensible answers measures the scorer, not the system. C removes the ambiguity
  without touching the data, the reference function or the scoring rule.
- It must land before the primer (ADR-0041), or the ablation would show the primer "hurting" for a benchmark reason.

## Consequences

- The sealed held-out file may contain a held-out wording of this family. Nobody designing strategies may open it to
  check. If that wording carries the same ambiguity, it is reported as it stands, with this ADR cited — never patched
  after the unseal (ADR-0035).
- **Revisit if** after v2 the low-effort answers still name the actuator in most cases (then the wording is still not
  clear, and D becomes the honest fix in a later phase).

**Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet")** Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet") with the main session's recommendations. Reword the question.

**Rejected by the user 2026-10-04 after implementation (QB-T1, never committed, reverted):** the v2 wording ("Control loop X drives an actuator. Which valve does that actuator move? Answer with the valve's own tag, not the actuator's.") is unnaturally mechanical — a real engineer asks "Which valve is actuated by control loop X?". Questions must read like real users' questions; do not engineer the wording around a model failure. The ambiguity stays a property of the task and is to be solved by the system (representation, primer, or generator naming realism), not by the question text. LOOP_ACTUATED_VALVE stays at template version 1.
