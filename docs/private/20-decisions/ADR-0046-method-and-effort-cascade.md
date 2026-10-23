---
adr: 0046
title: Route each question through a label-free self-flag cascade — a cheap Cypher query first, the need-aware plant context on a flag, a runaway remedy last — with effort and model fixed per tier, evaluated offline by joining fixed runs, and selected on dev corpora by rules fixed before the data
status: accepted
date: 2026-10-04
supersedes: in part — ADR-0042 Decision points 2 (wrapped strategy), 3 (primary arm effort_routed_<decider>), 4 (escalated arm), 7 (pre-registered claims E1, E2, M1′) and 8 (futility stop). ADR-0042 points 1 (configurations are pins), 5 (deciders, now an optional tier-1 skip) and 6 (offline condition, refined to a per-question join) carry over. ADR-0037 as already amended by ADR-0042. ADR-0014 point 4 (one pin per fixed run) unchanged.
design: 40-design/method-and-effort-cascade.md
---

# ADR-0046 — A method-and-effort cascade instead of per-question effort routing

## Context

ADR-0042 made the routed arm "choose glm-low or glm-default for `hierarchical_need_rules_plant`, per question,
before answering". The 2026-10-04 dev runs (D100, D1000; 18 families × 10; `_results.md` DEV10, PG-P1b, MIMO36)
changed the picture:

- `need_rules_plant` @ glm-default answers well when it answers (157/165, 151/160) but **runs away** on 15 / 20
  questions (16,384 output tokens, no answer; ≈ $0.0106 and 166–245 s each).
- `cypher_rag_plant` @ glm-low scores 141/180 on D100 at **$0.0420 total** (≈ 11× cheaper; the reported $0.0127
  omits the query-writing call) and median 1.5 s, and it **flags its own failures**: of 125 answers that are
  ANSWERED, non-empty and non-abstaining, 118 are correct; on the other 55 it is right 23 times, need_rules 45.
- Low vs default effort on `need_rules_plant` was measured only on a 36-question test-corpus slice: ≈ 30 % cheaper,
  9 questions worse (PG-P1). The cost lever ADR-0042 bet on is small; the method lever is large and measured.

Signals must come from the question text (rules need label, anchors) or from a tier's own output (outcome, Cypher
rows, abstention, runaway, latency) — never from gold. The $25 budget (≈ $21.5 left) and the sealed held-out
families (ADR-0035) bound what can be selected and how.

## Options considered

**A. Keep ADR-0042: per-question effort choice on `need_rules_plant`.** Same model, same context. Needs a full
need @ low run per dev corpus (≈ $0.36 each, estimate) before anything can be evaluated; measured upside ≈ 30 % of
cost at an accuracy loss; does nothing about runaways or about the cheaper method.

**B. Label router: pick the method per rules need label.** Free signal, no extra calls. On D100 the best per-label
choice reaches 167/180 at $0.146 — but that is 9 choices fitted on the same 180 questions; held-out families arrive
with labels whose method preference nobody measured.

**C. Label-free self-flag cascade (chosen).** Tier 1 Cypher @ low, accepted iff ANSWERED ∧ rows > 0 ∧ not
abstaining; else tier 2 need @ default, accepted iff ANSWERED; else tier 3 (need @ mimo or @ glm-low, chosen by a
fixed dev rule); else the tier-1 answer. On D100, tiers 1–2 with the fallback: **167/180 at $0.2425** (always-N
157 at $0.4692), median 2.3 s vs 7.8 s; paired bootstrap vs always-N: accuracy +0.056 [+0.006, +0.106], cost per
question −$0.00126 [−0.00161, −0.00093], latency −15.6 s [−20.8, −10.9]. Random escalation of the same 55 questions:
145.8 on average (95 % range 139–152). No parameter was fitted to the data; the acceptance rule is the plain
"trust only a non-empty, non-abstaining answer".

**D. Run both methods on every question and pick by rule.** Same answers as C, but always pays tier 2: dominated by
C on cost; only its latency could be lower (parallel calls).

**E. Live per-question pins in the harness.** Pays tier 2 only on escalations, but needs runner changes and gives the
same answers as an offline join over cached fixed runs (ADR-0037's key fact). Kept for the demo, not for measurement.

**F. Escalate to a stronger model (Sonnet) instead of a second method.** ≈ $0.034 per question (PAID-04); the
measured failure mode of the cheap tier is a missing query result, which a second method fixes at ≈ $0.0026.

## Decision

**C, evaluated offline (not E), with B kept as a reported dev-tuned variant.**
1. **Tiers and configurations** — tier 1 `cypher_rag_plant` @ glm-5.3-flash effort low (`CYP-D100-low` pin); tier 2
   `hierarchical_need_rules_plant` @ glm-5.3-flash default (`DEV10` pin); tier 3 `hierarchical_need_rules_plant` @
   T3 ∈ {xiaomi/mimo-v2.6-pro, glm-5.3-flash low}. Effort and model are properties of a tier, not per-question
   decisions. Sonnet is a reference only (optional, user decision).
2. **Acceptance rules** as above; runaway = PARSE_FAILURE or completion tokens ≥ the pin's cap. The policy reads a
   gold-free `Signals` object; a metamorphic test (flip every `correct`, decisions unchanged) guards it.
3. **Selection, fixed before any new paid call** (design note §7): S1 — T3 is the candidate with more correct answers
   on the 35 dev runaways (D100 + D1000), tie → cheaper; S2 — `cascade_v1` is confirmed if on D1000 its accuracy is
   ≥ always-N − 2 questions at a lower mean cost, else the primary becomes `n_first_v1` (need @ default, runaway →
   T3); S3 — a label variant replaces the primary only if on D1000 it beats `cascade_v1` by ≥ 2 questions at ≤ 1.25×
   its cost. D100 selects, D1000 confirms; the selected policy file and `qa/cascade/` enter the F1 manifest; the
   held-out families are opened only after F1 (ADR-0035).
4. **Pre-registered test claims** (H1000, all families and held-out families reported separately, paired 95 %
   bootstrap CIs over questions), replacing ADR-0042's E1/E2 before any test data exist:
   - **K1** cascade − always-N (same tier-2 configuration): accuracy CI contains 0 or lies above, **and** mean total
     cost and mean latency per question both lower (CIs exclude 0). Wording if not: "the cascade loses accuracy" /
     "the cascade saves nothing".
   - **K2** cascade − random escalation at the same tier-2 share > 0, CI excludes 0. Wording if not: "the self-flags
     route no better than chance".
   - Reported, not claimed: tier-1 acceptance share and precision per corpus and per k-bin (the scale reading),
     oracle-cascade regret, the label variants, Sonnet if run.
5. **Stop rule:** if S2 fails, the cascade is reported as a negative dev result and `n_first_v1` goes to test instead.

## Rationale

- The thesis claim is that the best retrieval strategy depends on scale. The cascade makes that a number per corpus:
  how many questions a cheap structured query settles on its own, and how well. On D100 Cypher already leads at
  k ≥ 3 (34/39 vs 28/39) and trails at k = 0 (44/68 vs 66/68); whether its share grows at H1000 is the scale question.
- Label-free acceptance is the only routing rule here that carries no knowledge of the benchmark's families, so it is
  the one whose held-out result means something (ADR-0035's Q2 logic applied to routing).
- Boring where it can be: self-verification cascades are standard (FrugalGPT-style); the novelty is spent on the
  domain and the scale axis, not on the router.
- Offline evaluation keeps every number a deterministic join of cached runs, re-runnable without API access, with no
  answer paid twice.

## Consequences

- Money (estimates): dev CP-P1 Cypher on D1000 ≈ $0.042 (cap $0.10); CP-P2 mimo and CP-P3 glm-low on the 35
  runaways ≈ $0.45 + $0.07 (caps $0.70 + $0.15); Sonnet optional ≈ $1.19 (cap $1.80). Test ≈ $0.75 beyond the
  need-aware runs EXP-0006 makes anyway, if those run at default effort.
- The always-N comparator and tier 2 must be the same configuration, so the need-aware test run moves to default
  effort — a revision of ADR-0042's accepted U6 for this one strategy (user decision).
- ER-T1 becomes CR-T1…T4 (new package `qa/cascade/`, no harness change); it no longer waits for J-T1. Jev becomes an
  optional "skip tier 1" decider (CR-T5), reported, not claimed.
- Two `_results.md` totals undercount: PG-P1b ($0.0127 → $0.0420 with the query call) and DEV10-D1000 ($0.484 →
  $0.580 with unit-router calls); a dated correction note is owed.
- The 7 accepted-but-wrong Cypher answers on D100 (5 UPSTREAM_ISOLATION) are a blind spot no self-flag sees; only a
  label variant or a better query prompt addresses them.
- **Revisit if** S2 fails on D1000; the Cypher acceptance precision on a test corpus falls below need_rules' accuracy
  on the same accepted questions (then tier 1 is harmful there — report it as a scale effect); GLM's default effort
  changes at the provider (ADR-0042 trigger); or a frozen prompt must change after F1.

## Acceptance (2026-10-05)

Accepted by the user in chat: **U1 yes** (the cascade supersedes ADR-0042's per-question effort routing, points 2, 3, 4, 7, 8), **U3 yes** (tier 2 and its always-N comparator run at default effort on the test corpora). U2, U4–U6 taken as recommended under the user's instruction to proceed; the user allowed a budget top-up if needed, "ésszel".

**Added before any tier-3 answer existed (2026-10-06):** a third T3 candidate, `need_rules_plant` on GLM-5.3-flash at default effort with `max_output_tokens` 65,536 (the user asked whether the cheap model's thinking budget can simply be raised; OpenRouter lists 943,717 as its max completion tokens). S1 now picks among three candidates by correct answers on the 35 dev runaways; ties go to the cheaper; latency is reported beside it.
