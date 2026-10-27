---
adr: 0060
title: Re-measure on v2 with F1 identified by an unchanged system-side path set plus byte-identical replays, one freeze commit for R4 and R5, ContextRAG at high effort only, caps written from a pilot before the first call
status: accepted
date: 2026-10-27
supersedes: none. Applies ADR-0053 (sealed protocol) to R5 and ADR-0054 (ladder protocol) to R4 on v2 corpora, with the deviations named here. Replaces, for v2 runs only, ADR-0053 decision 5's allowed-paths diff by the check in point 1. Settles ADR-0054 decision 5 (stage C) for v2 as not applicable. ADR-0028 (rate 0.25, required d0/d50 points), ADR-0029, ADR-0035, ADR-0038, ADR-0045, ADR-0057 Q2–Q5, ADR-0058 point 5 and ADR-0059 carry over unchanged.
design: 30-experiments/EXP-0007-v2-remeasurement-plan.md
---

# ADR-0060 — The v2 re-measurement protocol (R1–R5)

## Context

ADR-0057 Q3 = B makes v2 the headline. R4 (the EXP-0001 ladder) and R5 (the EXP-0002 sealed test) must run the
system frozen at F1 (`07d4029`) on v2 corpora, so that any change against v1 comes from the data. Measured today at
HEAD `917b4c3` (plan note §2):

- **The ADR-0053 freeze check would refuse.** `git diff --name-only 07d4029 HEAD -- src` lists about 60 files
  outside its allow-list. Nearly all of them build data: the generator, the adapters, `graph/`, `ingest/`,
  `qa/corpus.py`, and `qa/harness/gold.py` on the scoring side.
- **The system side is unchanged except one file.** On 25 system-side paths (strategies, agent, plant API, prompts,
  cascade, need, llm, store, serializer, schema text, Neo4j view, final answer, harness), only
  `qa/final_answer.py` differs. Its CLASS_NAME list is pinned to `V1_NODE_CLASSES`. The other three changed files
  are gold-side: `gold.py`, plus `family_meta.py` and `need_gold.py`, which were already allowed.
- **Behaviour is identical on v1.** Cache-only replays at HEAD reproduce ST-AG-H100 (580 rows), E1-CTXH-H1,
  E1-CTXH-H30, E1-AG-H1 and E1-AG-H30 byte for byte, with F1's eight prompt hashes.
- **One accepted decision is not built.** ADR-0058 point 5 (Q3 = B) says that on v2 corpora the CLASS_NAME
  instruction lists the classes present in the corpus. At HEAD it lists the 21 v1 classes on every corpus, so a v2
  LOOKUP_TYPE item such as a `GateValve` cannot be answered in the allowed vocabulary.
- **`sealed_set` refuses v2 test ids.** Its guard is `H\d+`, so `H100g2` and `H1g2` are rejected.
- **R3 changes the money.** v2 sheets serialize to 33–42k chars against v1's 16.4k. At H30g2 the prompt
  (≈ 429–510k tokens) crosses the 272,000-token price step, and H100g2 (≈ 1.46–1.58M tokens) does not fit Luna's
  922,000-token window. The ContextRAG arm of R4 is estimated at $10.1–14.9 at high effort alone (plan §8),
  against $2.4 for v1's H30 ctx-high run (EXP-0001).

## Options considered

**1 — How F1 is identified on v2 runs**
- **A. ADR-0053's allowed-paths diff, with the data-side paths added to the allow-list.** Mechanical, but the list
  has about 60 entries and grows with every generator change. It says nothing about the paths that matter.
- **B. An unchanged-path check on the system side, plus replays (chosen).** A fixed list of system-side paths must
  show no diff since F1. The one named exception is `qa/final_answer.py` (CLASS_NAME, point 2). Pins, params and
  cascade policies are compared with F1's files. Cache-only replays of one v1 run per arm must be byte-identical at
  the freeze commit: agent ST-AG-H100, ContextRAG E1-CTXH-H1 and E1-CTXH-H30, and Cypher E1-CYP-H1 with EXP-0001's
  H1 loaded alone. The check states what is frozen, and the replays prove behaviour rather than file identity.
- **C. A new freeze F2 with a re-run of the v1 dev selection.** It is paid, it duplicates EXP-0002, and it would
  make v1 and v2 numbers come from two systems.

**2 — The CLASS_NAME list on v2**
- **A. Build ADR-0058 point 5 before any v2 run (chosen).** v1 corpora keep the exact pinned text, and the replays
  of option 1B prove it. Each v2 corpus's instruction sha256 goes into the pre-registration.
- **B. Run with the v1 list and report LOOKUP_TYPE as an artefact.** This contradicts an accepted ADR, and it
  measures the prompt rather than the data.

**3 — Freeze commits**
- **A. Two commits, E for R4 and T for R5** (as EXP-0001 / EXP-0002). R5 needs no question-side change, so a
  second commit adds nothing to check.
- **B. One user commit E7 for both (chosen).** It holds the scripts, the cap rules, the plan note and this ADR. R4
  data are generated after E7 (`E7.sha256`). R5 data are generated at R5 time at the same commit (`T7.sha256`). No
  `src` change is allowed between R4 and R5.

**4 — ContextRAG arms in R4**
- **A. ADR-0054 as accepted: high effort at all four sizes, plus low at H1g2 and H10g2.** The low runs add an
  estimated $1.6–2.3, which is the X6 sensitivity check.
- **B. High effort only (chosen).** X6 was measured on v1: low effort is worse by 2.9 points at H1 and 15.4 points
  at H10. That makes high effort the steelman. On v2, X6 is reported as "not run (ADR-0060), see EXP-0001".
- **C. B, with H30g2 cut to 2 questions per family** (saves an estimated $4–6). Rejected: X1 is a slope over
  sizes, and its scope and power assume the same n per size.

**5 — Stage C (ContextRAG at H100) on v2**
- **A. Keep the conditional trigger.** It cannot fire: H100g2 does not fit the window.
- **B. Not applicable on v2 (chosen).** ADR-0038's "did not fit" becomes a measured fact at about 100 sheets on
  v2. The fit check refuses before any call, at zero cost.

**6 — The baseline for the token correction t_v2 / t_v1**
- **A. Fresh v1 pilot calls** (10 questions on D100).
- **B. The existing v1 dev tier runs AGL3-D100 and CYPL2-D100 (chosen).** They carry F1's eight prompt hashes and
  the Luna pins, with 10 questions per family. No spend, and a larger v1 n.

**7 — Caps**
- **A. Fixed caps now, from pre-pilot ranges.** Generous, but they rest on an assumed correction range of 1–3.
- **B. Cap formulas fixed now; values computed after the pilot (R4) and after R4 (R5), written to `caps_r4.json` /
  `caps_r5.json`, hashed, and shown to the user before the first call of the stage (chosen).** The harness
  writes `max_spend_usd` into every `run_config.json` at its start.

## Decision

1B, 2A, 3B, 4B, 5B, 6B, 7B. R4 and R5 otherwise follow ADR-0054 and ADR-0053 exactly: arms, n per family,
seeds of the question draw, cutoff, concurrency, claims, report code, abort rules and violations. The H100g2
duplication points d0 and d50 run both Luna tiers on the R5 recipe. They are descriptive (ADR-0028 sets no claim).
FIRST_MEETING_POINT is pre-registered as unavailable on v2 (ADR-0059 point 6). The held-out scope is therefore
the five remaining held-out families.

## Rationale

- **Thesis claim.** The v2 numbers are the headline. They are worth something only if the system that produced
  v1's numbers is provably the one measured on v2. The replays prove that directly, and the unchanged-path list
  says where a change would have to hide.
- **Boring where possible.** The scripts, cache, harness flags, health rules and report code are those of
  EXP-0001 and EXP-0002. New code is limited to the CLASS_NAME list (already decided), one regex, report
  parameters and the run scripts.
- **Spend follows evidence.** The expensive cell (ContextRAG at H30g2) gets a two-question smoke that measures the
  billed above-step price before the full run. The cap formulas use measured inputs only.

## Consequences

- **Makes easy:** a reviewer checks one path list, four replay files, the pin comparisons and two sha256 files.
- **Makes hard:** any change to a system-side path after E7 makes every v2 number post hoc (ADR-0053 §10 rules).
  A v2-aware legend (ADR-0057 Q2) can only be a separately labelled system after R5.
- **Money (estimates, plan §8):** R4 ≈ $10.4–16.0, R5 incl. d0/d50 ≈ $2.4–7.2. The pre-pilot caps total about
  $30 (R4 $20.8 incl. the pilot, R5 $9.5). The R4 gate stops at a projected ContextRAG remainder above $15.
- **Revisit if:** a replay is not byte-identical; Luna's listing differs on the run day; the pilot correction
  exceeds 3.0; the ContextRAG smoke at H30g2 bills above $0.25 per million prompt tokens; or R2 finds a dev family
  with fewer than 4 candidates on the ladder corpora or fewer than 20 at H100g2.

## Status

**Accepted 2026-10-27 (user, in chat)**, with these answers and one change of order:

| # | Question (plan §12) | Answer |
|---|---|---|
| 1 | The protocol as a whole | accepted, with the path-list exception below |
| 2 | OpenRouter balance | $31 on 2026-10-27 (user) |
| 3 | The $15 gate for the R4 ContextRAG remainder | **changed by the user**: ContextRAG is the reference arm; no money goes to it until the quality of the frozen system on v2 is known. ContextRAG runs last (stage 5 below) |
| 4 | d0 / d50 points | full R5 recipe |
| 5 | EX01 on the v2 vocabulary | not run |

**Path-list exception (S0-a).** RM-T1 had to carry the corpus's class list to the final step, so besides
`qa/final_answer.py` it touched `qa/class_vocabulary.py` (new), `qa/strategies/base.py`,
`qa/harness/attempt.py`, `qa/harness/attempt_models.py` and `qa/harness/runner.py` (commit `dc19941`). These
six files are named exceptions to the unchanged-path check. F1 identity rests on the replays: ST-AG-H100,
E1-AG-H1/H30 and E1-CTXH-H1/H30 are byte-identical at `dc19941` with all eight prompt hashes equal (cache-only,
2026-10-27); the Cypher replay (S0-d) is still required before the first paid call.

**Order of the paid stages (user, 2026-10-27).** Each stage is estimated, capped and shown to the user before it
starts; a stage starts only if the balance covers its cap.

1. Free gates S0 (incl. the Cypher replay) and R1/R2.
2. Pilot on D100g2: 10 families, both tiers, cap $0.10 (plan §7).
3. **Dev quality check on D100g2**: the dev question set, both frozen tiers. Diagnostic only; nothing is tuned
   on it (F1). It answers "is the frozen system roughly right on v2" before any sealed or reference spend.
4. R4 tiers on the ladder (Cypher and agent at H1g2–H30g2), then R5 (tiers on H100g2, H1000g2, d0, d50, the
   concurrency-1 control).
5. R4 ContextRAG reference arm (H1g2–H30g2, high effort), last, and only on the user's go after stages 3–4.

**Amended later the same day (user):** the ContextRAG reference arm is **not run for now** (cost), and the
system will probably be tuned on v2 before the headline runs. Consequences:

- Stages 2–3 (pilot, dev quality check on D100g2) run first, on dev data only.
- If the dev check shows failures worth fixing, tuning happens on dev and tuning seeds only (D/X corpora, never a
  seed in 5000–5999). The tuned system is a **new, separately labelled system**, not F1 (ADR-0057 Q2); F1's v1
  numbers stay as they are.
- R4 and R5 (both use registered test seeds) wait until that system is frozen at E7. They run once, on it.
- The ContextRAG reference arm stays deferred until the user asks for it.
