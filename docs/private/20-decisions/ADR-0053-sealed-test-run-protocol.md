---
adr: 0053
title: Run the sealed test once on H100 and H1000 with the two GPT-6 Luna tiers only, cascade_v3 as the primary policy (a recorded deviation from rule V2), 20 questions per family at a fixed n, concurrency 4 plus a concurrency-1 control, and a git-commit freeze enforced by the run script
status: accepted (user, 2026-10-11) — U1–U5 as recommended: cascade_v3 primary with the V2 deviation recorded; 20 per family + 10 per wording; concurrency 4 plus the 48-question concurrency-1 control; no GLM replication, no always_n; two user commits F1 and T
date: 2026-10-11
supersedes: in part — ADR-0035 U1 (staged 10 → 20 "if informative"), ADR-0035 Decision point 3 (how F1 is recorded and checked), ADR-0048 Decision point 6 (V2 on the Luna candidates: the user's 2026-10-11 choice replaces its literal outcome). ADR-0015, ADR-0035 claims Q4/Q5, ADR-0038, ADR-0045, ADR-0046 K1/K2, ADR-0048 K3 and LB-1…LB-3, ADR-0050, ADR-0051 and ADR-0052 carry over unchanged.
design: 40-design/sealed-test-run.md
---

# ADR-0053 — The sealed test run protocol

## Context

Development is closed. The policy the user adopted on 2026-10-11 is `cascade_v3`: tier 1 `cypher_rag_plant` on
GPT-6 Luna (effort low), tier 2 `graph_agent_low_steps` on Luna (steps low, final answer high), tier-1 answer as the
fallback, no label routing. Dev acc@120 (CASCADE-V3, re-checked with the CYPL2 Cypher runs in the architect's
2026-10-11 dry run): D100 176/180, D1000 175/180.

What is still open is how the one-shot test on the held-out corpora (H100 seed 2, ADR-0045; H1000 seed 0) is run
and recorded. Six points have a real alternative:

1. **Which policy is primary.** ADR-0048's rule V2 picks the eligible candidate with the highest acc@120 on D100.
   Among the Luna candidates that is `cascade_v3_iso` (178), not `cascade_v3` (176); on D1000, 177 vs 175. The user
   chose `cascade_v3` because label routing relies on the rules classifier, which was written from the benchmark's
   own templates.
2. **Which arms run.** Every policy and reference is an offline join of fixed per-tier runs (ADR-0046). The
   arms that would need their own paid runs are the GLM tiers, `always_n` (need_rules on GLM) and ContextRAG.
3. **How many questions.** ADR-0035 U1 said 20 per family, run in stages: 10 first, then 20 "only if the first
   half is informative". Measured dev cost per question is about $0.0004 for the Cypher tier and $0.0005–0.0006
   for the agent tier (CYPL2, AGL3), so cost no longer forces the staging.
4. **Concurrency.** It changes wall time by about ×4. It may also change per-call latency through provider
   queueing, and nobody has measured whether it does (cascade-v2 O2).
5. **How the freeze is recorded.** ADR-0035 named `data/freeze/qar-freeze.json` plus a test written in QAR-T10.
   Neither exists. The pins and params live in git-ignored `data/`, and the harness already writes the commit, a
   dirty flag, prompt hashes, the pin and the question-set hash into every `run_config.json`.
6. **Which pre-registered claims can still be tested.** Q1–Q3 (ADR-0035) need arms that ADR-0047 and ADR-0048
   dropped (`hier_agent`; need-aware Hierarchical as a test arm).

## Options considered

**Point 1 — primary policy**
- **A. `cascade_v3` (chosen by the user).** Label-free: the routing uses no knowledge of question families. On
  both dev corpora it is 2 questions behind the best, which is inside V3's own tolerance (≥ best − 2).
- **B. `cascade_v3_iso`, as V2 literally selects.** +2 dev questions on each corpus. Its gain comes entirely from
  one family (UPSTREAM_ISOLATION), routed by a classifier written from that family's template. On held-out
  families its label is unmeasured. ADR-0046 says exactly this about label variants.
- **C. Both co-primary.** Doubles the primary comparisons and leaves the reader to pick the winner after the
  fact.

**Point 2 — arms**
- **A. The two Luna tiers only (2 paid runs per corpus).** Covers `cascade_v3`, `always_g_luna`, `always_c_luna`,
  `cascade_v3_iso`, random escalation and the oracle. That is every arm K1, K2, K3, Q4 and Q5 need.
- **B. A plus the GLM tiers.** A second model family (ADR-0015 should-tier). Estimated at about $1.5 and 1.5 h more.
  GLM's unpinned routing makes its latency hard to reproduce (BAKEOFF-1: 15 hosts).
- **C. A plus `always_n`.** A serialization-type arm on unseen questions. On dev it fails LB-2 at both scales.
  Estimated at ≥ $3.5 and ≥ 2.5 h on GLM default; on Luna it was never run, so it would be a new arm added after
  dev.
- **D. A plus paid ContextRAG.** ADR-0038 already decided against it. The prompt is 1.70M / 16.65M characters
  (INFRA-1).

**Point 3 — question count**
- **A. 10 per family.** Cheapest. The 95 % half-width on a near-ceiling accuracy is about twice that of B.
- **B. 20 per family, staged as U1.** The stop depends on looking at the first half. That is optional stopping,
  and "informative" was never defined.
- **C. 20 per family, fixed in advance; each held-out wording 10.** No look before the full set is in.

**Point 4 — concurrency**
- **A. 1 everywhere.** Cleanest per-call latency. About 5–6 h of wall time.
- **B. 4 everywhere, plus a concurrency-1 control on 48 H1000 questions (agent tier).** The live dev runs behind
  the selection ran at 4: AGL3 directly, and the Cypher latencies through CYPL, whose cached latencies CYPL2
  reused. Wall time is about 1.5 h. The control bounds the queueing effect, and a fresh cache makes it a second
  draw of the same questions.
- **C. Mixed (Cypher 1, agent 4).** It looks like dev but is not: CYPL2's latencies came from the concurrency-4
  cache.

**Point 5 — freeze record**
- **A. As ADR-0035 wrote it:** a JSON of file hashes, asserted by a pytest that QAR-T10 adds. The test cannot know
  the F1 hash unless the hash is committed. The untracked inputs would still need separate handling.
- **B. The F1 commit plus a `sha256sum` file of the untracked inputs and of the pre-registration documents, plus
  an allowed-paths `git diff` check.** The run script runs all three checks and refuses to start on any mismatch.
  Git already hashes the tracked code.

**Point 6 — claims**
- **A. Carry K1, K2, K3, Q4 and Q5. Report Q1–Q3 as "not run", with the ADR that removed their arms.** Make
  Q4 for `cascade_v3` the single primary claim.
- **B. Re-word Q1–Q3 onto today's arms.** That would be inventing new claims under old names.

## Decision

1. **Primary policy `cascade_v3`** (1A). The deviation from V2's literal outcome is recorded here and in the
   thesis. `cascade_v3_iso` is reported beside it as "dev-tuned label variant". The policy files, pins and code are
   frozen at F1.
2. **Arms: the two Luna tier runs per corpus** (2A). No GLM, no `always_n`. ContextRAG at H100/H1000 stays
   `DID_NOT_FIT` by ADR-0038, evidenced by INFRA-1's prompt sizes against Luna's listed context window, read from
   OpenRouter on the run day.
3. **20 questions per family** (18 dev + 6 held-out families) **and 10 per held-out wording, fixed in advance**
   (3C). If a family has fewer candidates, all of them are used and n is reported. A family that cannot be
   generated or scored is dropped and reported, never replaced (ADR-0035).
4. **Concurrency 4 for all four primary runs**, recorded in each run's `environment.jsonl` (4B). A concurrency-1
   control `ST-AG-H1000-C1` runs on 48 H1000 questions (2 per family, wordings excluded) with a fresh cache. It is
   reported, not claimed.
5. **Freeze F1 = a user commit** with a clean working tree (5B). `data/runs/sealed/F1.sha256` covers the pins,
   params, the sealed file, the design note and this ADR. `git diff --name-only F1 HEAD -- src` may list only the
   allowed gold-side paths (design §6). Every sealed `run_config.json` must have `git_dirty: false`. Runs are not
   `--reported`: gate G2 asks for a context wall, which matters only for ContextRAG, and no Luna wall exists.
6. **Claims** (6A). **Primary: Q4 for `cascade_v3`.** Secondary: K1, K2, K3, Q4 for the other arms, and Q5. All are
   computed on the headline set (dev and held-out families, LOOP_ACTUATED_VALVE excluded per ADR-0044 U2, wordings
   excluded) and again on the held-out families alone. Q1–Q3 are reported as not run.
7. **Protocol violations and the technical-abort rule** are as in design §10.

## Rationale

- **It ties back to the thesis claim.** The claim is that the best strategy depends on scale. A label-free
  policy measured at two scales on question types nobody tuned for is the cleanest test of it. A label variant's
  test result says something only about the families its classifier was written for.
- **The primary is the most on-claim and least gameable test.** Q4 asks whether the deployed system keeps its
  accuracy and its cost from H100 to H1000. That is the title's "scalable", and it was pre-registered on
  2026-10-02, before any of today's arms existed.
- **Fixed n removes a fork.** At about $0.001 per question for both tiers together, staging saves cents and costs
  credibility.
- **The test copies the conditions the dev selection ran under,** and the control measures what concurrency does
  instead of assuming it.
- **The freeze is the boring choice.** Git already hashes the code. The script refuses to run on a mismatch, so a
  violation cannot happen silently.

## Consequences

- **Easy to audit.** A reviewer can check F1, the allowed diff, the input hashes, `git_dirty: false` in four
  run configs and the byte-identical replays.
- **Honest limits.**
  - One model family on test.
  - One repeat of a model whose host takes no temperature. The C1 control gives a 48-question view of
    run-to-run agreement.
  - No serialization arm on unseen questions; that side of the claim rests on dev runs (DEV10) and on prompt-size
    measurements.
  - EXP-0001 (single sheet, the ChatP&ID end of the claim) is not part of this run and is still open.
- **K1 is at risk.** On dev, `cascade_v3` costs about the same per question as `always_g_luna`: +$0.00004 at
  D100 and −$0.00005 at D1000 (architect dry run). K1's "cost lower, CI excludes 0" may therefore fail, and it is
  reported with its pre-registered wording. It is not re-worded now, because the change would be made with that
  forecast in view.
- **Money.** About $1.15 is estimated, with caps of $2.90 (design §8).
- **Revisit if** a frozen file must change after F1 (then every test number is post hoc); a technical abort
  happens twice on the same run; or the Luna price or host behaviour changes before the run, in which case the
  estimate and caps are re-read before anything is spent.
