---
adr: 0047
title: Latency is a first-class criterion; the 64k tier is rejected; graph_agent is the next focus and hier_agent is dropped
status: accepted
date: 2026-10-06
amends: ADR-0046 (S1 outcome), ADR-0034 (hier_agent)
---

# ADR-0047 — Fast answers count; let the model compose the primitives

## Context
CASCADE-00 selected, by ADR-0046's pre-registered S1 (most correct on the 35 dev runaways), tier 3 =
GLM default effort with a 65,536-token cap: 21/35, but mean latency 296.9 s on those questions (CP-P2).
The user (2026-10-06): raising the reasoning limit only makes the model think longer; the system must be
accurate **and** answer fast for a good user experience — cost alone is not the bar.
The user also rejected `hier_agent`'s rule-built seed map: real questions will not arrive in the shapes we
anticipated, so a static, code-written part does not generalise. QAR-P2 (agent pilot) was already running.

## Decision
1. **Latency is a selection criterion next to accuracy and cost** for every remaining choice (user).
2. **The 64k tier is rejected** although S1 selected it. This overrides a pre-registered rule *after* its result
   was seen; the thesis reports S1's outcome and this override, with the reason (user requirement on latency).
3. **The tier-3 choice is reopened** after the agent pilot, under an explicit latency bound to be fixed before
   any further paid tier-3 run; candidates on record: mimo (19/35, mean 89.8 s), GLM-low (14/35, 16.9 s),
   or no tier 3 if `graph_agent` removes the runaways.
4. **`graph_agent` is the next build and measurement focus** (user: the LLM must compose the primitives for a
   free-text question). It is measured in tier 2's place of the cascade.
5. **`hier_agent` is dropped** from the method (user). Its code stays only because QAR-P2 measured it; it is not
   developed further and not run again.
6. The agent's step bound (6) stays until measured: if a material share of questions stops at `max_steps`, the
   bound is raised.
