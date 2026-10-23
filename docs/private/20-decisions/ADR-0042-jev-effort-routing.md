---
adr: 0042
title: Make Jev's router choose the reasoning effort of one cheap model (low vs default) as the primary routed arm, with escalation to the strong model as a secondary tier; every effort level is its own pinned configuration, so the arm stays computable offline from fixed runs
status: accepted
date: 2026-10-03
supersedes: in part — ADR-0037 Decision points 1 (candidates are pinned configurations, not only models), 2 (the wrapped strategy becomes hierarchical_need_rules_plant, ADR-0039) and 6 (M1/M2 move to the secondary tier; E1/E2 are the primary claims). ADR-0037 points 3–5 and 7 (deciders, free comparisons, offline condition, futility stop) carry over with "model" read as "configuration". ADR-0014 point 4 (one pin per sweep) unchanged.
design: 40-design/plant-graph-first-and-effort-routing.md Part D
---

# ADR-0042 — Jev picks how hard the cheap model thinks, before it picks a bigger model

## Context

The user (2026-10-03) refines ADR-0037: Jev should predict difficulty from the question text (plus the corpus-size
line) and route to `low` or default reasoning effort on the same cheap model; the strong model is for questions the
cheap one fails even at full effort.

Measured on the same 36-question H100 slice, `hierarchical_need_rules` (`_results.md`):

| Configuration | Correct | Total cost | Median latency | Run |
|---|---|---|---|---|
| glm-5.3-flash, effort low | 27/36 | $0.050 | 3.8 s | PAID-03 |
| glm-5.3-flash, default effort | 31/36 | $0.0795 | 18.5 s | PAID-02 |
| claude-sonnet-5.5 | 33/36 | $1.211 | 3.7 s | PAID-04 |

So effort moves accuracy by 4 questions at about 5× the latency and 1.6× the cost; the strong model adds 2 more
questions at about 15× the cost of default effort. Two questions per family: anecdotal, but enough to say the effort
axis is not empty. An effort level is a pin parameter (`ModelPin.extra = {reasoning: {effort: low}}`, PAID-03), so
each level already has its own pin hash and cache keys.

## Options considered

**A. Keep ADR-0037 as accepted:** cheap vs strong model as the routed choice. The cheapest lever (effort, same model)
stays unused, and every routing error costs a strong-model call.

**B. Effort routing primary, model escalation secondary, offline over fixed configurations.** Fixed runs at `low` and
default on the slice, plus the strong model only where escalation could happen; the routed arms are per-question
selections among cached answers.

**C. Live per-question effort switching in the harness.** Closer to deployment; needs per-question pins in the runner
and new paid calls wherever a combination was not cached, and gives the same answers as B when the cache holds them.

**D. No routing: one effort for everything.** Simple; leaves the user's question (cheap and good) unanswered.

## Decision

**B.**
1. **Configurations.** `glm-low` (PAID-03 pin), `glm-default` (PAID-02 pin), `sonnet` (PAID-04 pin). `high` effort is
   not a candidate: never measured, and default effort already let the query-writing call run to the 16,384-token
   limit 14 times (PAID-02).
2. **Wrapped strategy:** `hierarchical_need_rules_plant` (ADR-0039), the best-measured cheap arm.
3. **Primary arm `effort_routed_<decider>`.** The decider scores p = "will `glm-low` answer this correctly?" from the
   question text and "The plant has N sheets and M units."; `glm-low` if p ≥ 0.5, else `glm-default`. τ = 0.5 fixed.
4. **Secondary arm `escalated_<decider>`.** Start where the primary arm routes; when that answer is self-flagged
   (`not_present`, PARSE_FAILURE, DID_NOT_FIT, RETRIEVAL_ERROR), move one tier up (`glm-low` → `glm-default` →
   `sonnet`). The user's "escalate only what the cheap model fails" is reported as the **oracle cascade** (gold-flagged),
   an upper bound, never as a deployable arm.
5. **Deciders** (ADR-0037 point 3, re-targeted): Jev `noul`, label-probability on the classifier pin, the free rules
   proxy (need label `ITEM`, neighbour labels, `UNIT_SCOPE` → easy); plus the free comparisons always-low,
   always-default, oracle, and random routing at the same low share (1,000 seeded draws).
6. **Offline condition** as ADR-0037 point 5, per configuration: same F1 hashes, strategy parameters, question set,
   primer setting and repeat index; the join refuses otherwise and prints the missing question ids per configuration.
7. **Pre-registered claims** (H1000 routed slice, paired 95 % bootstrap CIs over questions):
   - **E1** `effort_routed_jev` − always-default accuracy: CI contains 0 or lies above, **and** mean total cost and
     mean latency per question are both lower than always-default's (paired CIs excluding 0). Wording if not:
     "effort routing loses accuracy" / "effort routing saves nothing".
   - **E2** `effort_routed_jev` − random routing at the same low share > 0, CI excludes 0. Wording if not: "Jev routes
     effort no better than chance at the same cost".
   - **M1′** (secondary, reported, not claimed): `escalated_jev` vs always-default accuracy and cost; against
     always-sonnet only on the random sub-slice where a full Sonnet run exists.
8. **Futility stop.** After the slice's two GLM runs: if always-default beats always-low by less than 0.02, the effort
   axis has nothing to win; stop the primary arm and report.

## Rationale

- Effort is the cheapest lever the user owns: same model, same context wall, same pin family; ADR-0014 point 4 holds
  for every fixed run. Latency, not only cost, is where the measured gap is largest, so E1 claims both.
- Offline routing keeps every number a deterministic function of cached runs and cached decisions, re-runnable without
  API access, and no answer call is paid twice.
- Escalating only self-flagged answers bounds the strong-model spend to the flagged set, which is what the user's
  sequencing asks for, and keeps the always-strong comparison honest by limiting it to where it was really run.

## Consequences

- Runs and money (design note §D.7, estimates from the PAID-02/03/04 per-question means): `glm-low` and `glm-default`
  on a 120-question H1000 slice ≈ $0.17 + $0.27; Sonnet on at most 40 escalated questions ≤ $1.35; an optional random
  36-question always-Sonnet sub-slice ≈ $1.21; decisions a few cents.
- MR-T1 becomes ER-T1: candidates are named configurations, the join is per configuration, the cascade is tiered.
  The free deciders (rules, oracle, random, self-signal) can be built before J-T1; Jev and label-probability wait for it.
- Model routing for cost is prior work (ADR-0037's owed novelty check still applies; effort routing is newer and
  needs the same check). The defensible point remains the domain and the scale axis.
- **Revisit if** GLM's `default` effort is changed by the provider (the pin then no longer reproduces; record and
  re-pin); the J-P2 repeatability probe flips more than 5 % of decisions (ADR-0032); or the futility stop fires.

**Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet")** Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet") with the main session's recommendations. Fixed runs at low effort everywhere; default effort only for the router. **User addition:** besides Sonnet, try a cheaper mid-tier model that is stronger than glm-5.3-flash — candidates from the 2026-10-02 listing: `xiaomi/mimo-v2.6-pro` ($0.435 / $0.87 per M; seed and temperature supported) and `z-ai/glm-5.3` ($1.40 / $4.40); Sonnet 5.5 is $2 / $10.
