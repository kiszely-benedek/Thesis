---
adr: 0013
title: Score answers against computed ground truth at scale; use an LLM judge only for the ChatP&ID reproduction
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0013-qa-evaluation-method.md
supersedes: none
---

# ADR-0013 — How answers are scored

**Question.** How do we decide whether an answer is right — at 19 questions, and at thousands?

**Options**
- **E1** An LLM judges each answer 1–5 on four criteria (ChatP&ID's method). Comparable to their 0.91, but
  noisy, it costs a call per answer, and the judge's own accuracy is unknown.
- **E2** Computed ground truth (PIDQA's method). Each question template comes with a small program that
  computes the true answer from the plant graph; scoring is exact or set match. Cheap, deterministic, and
  scales to thousands. Cannot score open-ended questions.
- **E3** Both: E1 only for EXP-0001, E2 for everything at scale.

**Decision: E3.** Key rules:
1. True answers are computed in plain Python over the **ground-truth** graph, never with the system's own
   Neo4j. A linking error therefore shows up as a wrong answer.
2. Every question is tagged with **k = how many sheet boundaries its answer crosses**. k = 0 is the
   single-sheet control, and the crossover should show along k.
3. All strategies share one final answer step with JSON output. An unparseable answer counts as wrong, and the
   failure rate is reported separately.
4. The judge comes from a different model family than the answerer. On a sample, the judge is also checked
   against E2's computed answers, so it reports its own accuracy.

**Why.** A ranking that changes with scale must not drown in judge noise. E2 is also what makes the benchmark
publishable and re-scorable without any API.

**Costs.** Open-ended questions (inference, summaries) appear only in EXP-0001.

## Outcome log
- **2026-09-26** Accepted (user). **ChatP&ID's 19 questions are in the paper:** Appendix B, App. Table 1,
  pp. 28–36. All 8 single-lookup questions ask for equipment data values, which generated plants do not carry,
  so they exist in EXP-0001 only.
- **2026-09-26** Correction (main session, re-read of App. Table 1): the 8 single graph queries ask for attribute values of **6 equipment items and 2 valves** (66KL21 nominal diameter, SV 104.01 set pressure); the 2 multi queries list all valves / pipe fittings **with their specifications**. So **10 of 19** questions need data attributes, not 8.
