---
component: review fixes and the final v2 measurement (EXP-0008)
status: draft — awaiting review (revised 2026-11-07 after the user's direction)
adr: ADR-0065 (proposed)
supersedes in effect: the first v2 measurement (EXP-0007 V2T-VAL, R4, R5, INFRA-2; EXP-0004 P1–P4), kept on file as the first measurement
---

# Review fixes and the final v2 measurement

## 1. What this is, and the user's direction

A read-only review of the frozen code (2026-11-06/07) listed about 45 findings. On 2026-11-07 the user decided:
fix everything, then re-run the v2 measurements end to end on regenerated plants. No corrected numbers are bolted
on beside old ones. The first v2 measurement stays on file as a record, labelled
"first measurement, superseded because of defects 1, 2, 5, 10" (section 3.3). The user writes a note in the thesis
saying so.

**Thesis tie.** The claim is that the best retrieval strategy depends on corpus scale. The re-run measures it again
with every known defect removed. The single-sheet end is R4 with ContextRAG, plant scale is R5, machine cost is
INFRA, and cross-sheet identity is EXP-0004. The claims and thresholds stay the ones already registered.

**Accepted by the user (2026-11-07):**
- D1: VALVES_ON_PATH counts hops at item level (section 4).
- D2 in spirit.
- D4: re-run EX01 after the adapter fix.
- D5: τ₂ from exact scores (now tuned afresh by the same rule).
- D6: the identity rule order is fixed.
- The per-finding fixes.

**Rejected:** the CR1 "registered + corrected beside it" scheme, and D3 (do not fix the generator).

**Also accepted (2026-11-07):**
- U1: fresh seeds under the new generator.
- U2: gate G1, no re-tuning by default.
- U3: v1 left with a note.
- The direction of ADR-0065.

**Added by the user (2026-11-07):**
- several independently seeded test plants per scale, aggregated (section 5.1–5.2, the number left to us);
- an independent scorer audit with a reasoning LLM judge (section 5.3);
- a budget: EXP-0008 under $40 hard, estimate about $30–32 (variant B, sections 5.1 and 6);
- nothing of EXP-0008 runs before the user's "mehet", given after reading the study map. One detached launcher then
  runs everything (section 5.4).

## 2. How the findings were checked (2026-11-07, read-only, no Neo4j, no paid calls)

Scratch scripts outside the repo. They rebuilt plants from `ingest.json`, re-parsed stored `trace.raw_reply` fields
and read `calls.jsonl`, `timings.jsonl`, logs and P3 decision files. Each figure below comes from those reads or from
the cited file.

## 3. Findings: every one is fixed

### 3.1 Result-affecting findings (with their measured size in the first measurement)

| # | Finding | Measured in the first measurement | Fix (task) |
|---|---|---|---|
| 1 | `qa/questions/families_heldout_paths.py:205` VALVES_ON_PATH gold counts raw nodes, fittings included | gold ≠ item-level count on 5/20 (H100g2), 8/20 (H1000g2), 4/20 (H100g2d0), 4/20 (H100g2d50), 0/15 (R4 ladder); every agent "wrong" answer there equals the item-level count (3/3, 6/6, 3/3, 4/4) | item-level gold and candidacy (F2) |
| 2 | `qa/final_answer.py:209` JSON numbers in UNIT_SET/SHEET_SET (and a bare number for UNIT_ID) become PARSE_FAILURE | 20 rows in 15 scored runs, v1 and v2; the 18 checked all correct once parsed | parser (F1) |
| 3 | `qa/final_answer.py:233` BOOLEAN 1/0 rejected | latent, 0 rows | F1 |
| 4 | `llm/client.py:352` HTTP 200 with `finish_reason: "error"` cached, not retried | 4 live calls; 1 dev row lost (`DEV10-D1000`); 0 sealed rows | F3 |
| 5 | `infra/cypher_replay.py:84` DB-only replay re-runs only the last query | 74 (H1000g2) and 28 (H100g2) timed-out first attempts skipped. Estimate at 30 s each: DB share ≈ 49 % rather than 29.8 %, p90 ≈ 30 s rather than 7.54 s at H1000g2 | F6 |
| 5b | `qa/cypher_guard.py:68` timer lost in the worker thread | `db_client_s = 0` on 560/560 rows of `S7-CYP-H1000g2` | F4 |
| 5c, 5d | `infra/report_checks.py:22` M1 passes after a fallback; `infra/report.py:77` "coarse clock" (R5 used `perf_counter` on 560/560 rows) | wording and check | F6 |
| 6 | `exp0004/tuning.py:40` τ grid rounded to 12 places | registered τ₂ 0.857142857143 means "> 6/7". Exact scores give 8/9 (dev F1 0.984 vs 0.979 at 6/7); no test decision differed | exact scores (F9) |
| 7a | `qa/harness/usage_meter.py:96` abandoned-call time missing from ANSWERED rows | dev runs only (`CV2-*`, `BO2-C-D100`) | F3 |
| 7b | `llm/client.py:354` back-off not in `latency_s`, retries only in the log | R5 headline 0 retries; `S7F1-CYP-H1000g2` 3 (4 s back-off); R4 `E7-CYP-H3g2`/`H10g2` 8 (8 s); E2E d4 1 (1 s); v1 `ST-*` 18 (38 s) | F3 |
| 7c | `llm/client.py:265` tombstone latency over the remaining budget on replay | replay only | F3 |
| 7d | `qa/harness/summary.py:106` late-after-timeout cost not in rows | `S7F1-AG-H1000g2` 1 call, $0.00608 (1.1 %); dev up to 26.1 % | F3 |
| 8 | `qa/cascade/evaluate.py:226` first-tier recall over all rows, not the scope | `report.json` only | F5 |
| 9 | `resolution/identity_links.py:158` one-to-one before the same-sheet check | 0 identity conflicts in every P3 decision file, so no effect | F9 |
| 10 | generator v2 realism (list in F8a–c) | the topology is less realistic; no gold answer wrong on a plant as generated | F8a–c, generator v2.1 |
| 10b | `benchmark/v2/sheet_stats.py:125` wired cross-unit out-ports counted as open stubs as well | inflates the stub and symbol figures behind ADR-0059's bands (the reviewer's 6.92 vs 6.32 stubs per sheet is not re-checked) | F8b |

### 3.2 Low findings: fixed too

| Finding | Fix (task) |
|---|---|
| `qa/cascade/cli.py:145` `report --setting` skips `limits.run_problems` | F5 |
| `qa/cascade/evaluate.py:378` offline acc@C stricter than the live fallback | F5: offline follows the live rule |
| `qa/harness/freeze.py:125` run freeze hashes neither prompt-building Python nor corpus content | F7: new optional fields; old `run_config.json` still loads |
| `llm/client.py:237` ContextOverflow not cached | F3: cached as an overflow record, replayed as the same error |
| `qa/harness/fill.py:309` order of retried ProviderError rows | F3 |
| `qa/harness/fill.py:159` resume spend guard counts cache hits | F3 |
| `qa/harness/line_view_fidelity.py:86` LINE-01 cannot see split identities | F11 |
| `qa/strategies/cypher_rag_lines.py:372` repair prompt carries live memory numbers | F4: volatile numbers masked before the prompt. This is a prompt change, so it is covered by the re-validation (section 5) |
| `qa/cypher.py:188` keyword write filter | F4: token-aware filter; the read-only session stays the guard |
| `resolution/pairing.py:84` duplicate outgoing connector numbers | F9: refused as ambiguous and counted |
| `ingest/headline_v2.py:155` corpus id ignores `--tag-variants` | F9 |
| `exp0004/report.py:99` P3 spent column after a resume | F9: from the call records |
| `exp0004/rehome.py:144` tautological proof check | F9 |
| `adapters/pydexpi_loop_tags.py:64` carrier removal not gated to v2 | F10 |
| `adapters/pydexpi_adapter.py:272` bubble tag ignores the function letters (confirmed on EX01: `P-4712.02`, `H-4750.01`) | F10 |
| `graph/validation.py:226`, `:160`; `adapters/pydexpi_generic.py:179`; `adapters/pydexpi_proteus_import.py:138`; `benchmark/open100/crops.py:97` (reviewer: PLAUSIBLE) | F10: first a failing test that shows the defect, then the fix |

**What may stay unfixed.** Only a PLAUSIBLE finding for which no failing test can be written. It is then recorded as
"not reproduced", with the test that tried. Nothing is left unfixed by choice.

**Not a finding, kept as registered:** FIRST_MEETING_POINT stays out of every v2 set (ADR-0062). The family only sees
joins that happen at an item, and the item-level fix to VALVES_ON_PATH does not change that.

### 3.3 The first measurement's record

Nothing is deleted. `data/runs/exp0007/**`, `data/runs/exp0004/**`, E7, E8, T7, PREREG and the run notes stay as
they are. Each run note and `_results.md` row gets one appended status line:
"superseded by EXP-0008 (ADR-0065): defects 1, 2, 5, 10". Each line names the sizes of section 3.1 that apply to it.
`00-index.md` points to EXP-0008 as the current result. The first system stays reproducible from `E7.commit` /
`E8.commit`.

## 4. VALVES_ON_PATH, item level (D1, accepted)

The answer is the number of valves strictly between A and B on a shortest route **in the line view**. Hops are
equipment and valves; untagged fittings and tagged inline parts are passed through, as `next_path_items` does. A
pair is a candidate only if every item-level shortest route gives the same count. The registered rule is unchanged,
only the hop is redefined. Ambiguous pairs therefore never enter a question set. The item-level walk stays on the
gold side (`qa/questions/common.py`) and never imports the plant API, so gold and system remain independent.

## 5. The final v2 measurement (EXP-0008): steps in order

**Budget (user, 2026-11-07): EXP-0008 as a whole stays under $40, hard, estimate about $30–32.** This is variant B
of the plant design: multi-plant where the headline claims live, single plant for the descriptive and single-sheet
arms.

**Names.**
- Generator version `v2.1` (the default for new plants). A `v2` config is refused with "built by the superseded
  generator; check out E8.commit".
- Corpus ids with `g21` and a plant index: `H100g21p1` … `H100g21p5`, `H1000g21p1` … `H1000g21p5`, `H1000g21p3V`
  and so on. No id collides with a first-measurement record.
- System **V2T-A2**: V2T-A plus the review fixes, no new tuning.
- Freeze **E9**.
- Records under `data/runs/exp0008/`.

**Seeds (U1 accepted: fresh seeds under the new generator).**
- Dev and tuning seeds are reused: dev 1, tuning 211, the ladder's 600–899 dev searches.
- **Every test-role plant gets a fresh seed:** validation, the ladder, every sealed plant, EXP-0004 test. Seeds are
  drawn once by a recorded script and written into the pre-registration before any test plant exists.
- `qa/exp0007/hygiene.py` retires 5100/5001/5002/5003 and the validation seeds 212/213.

| Step | What | Paid? | Gate before the next step |
|---|---|---|---|
| M0 | Regenerate the dev plants (D100g21, D1000g21, X100g21s211, EXP-0004 dev D100g21d100Vf). Composition report with the fixed stats; ADR-0059 bands re-judged. v1 and EX01 golden re-ingest. **Feasibility probe:** build time and peak memory of a 1,000-sheet dev question pool | no | bands as ADR-0059 states them (else U4); the pool finishes on the 15.4 GiB machine |
| M1 | **Re-validation** as EXP-0007 V2T-VAL: V2T-A2 and F1 on two fresh validation plants (100 and 1,000 sheets), 163 dev questions each, run once | yes | gate G1 |
| M2 | EXP-0004 P1/P2 on the dev corpus: τ₁, τ₂ by the registered rule with exact scores; D4 prompt unchanged | yes, small | parse failures 0, or the prompt rule of ADR-0063 |
| M2b | **Judge pilot** (section 5.3) on first-measurement rows with known truth; measures the per-call cost | yes, small | gate G2 |
| M3 | **E9 freeze + pre-registration part B, inside the launcher** (section 5.4; part A with the seeds is committed before the button): claims and thresholds of ADR-0053 (Q4 primary, K1, K2, K3, Q5), ADR-0054 (X1, X2), ADR-0063 (I0–I4, E1–E4), ADR-0051 (M1–M7); the plant design and aggregation (5.1–5.2); the audit (5.3) with its judge prompt hash, priority order and sample sizes; seeds, run order, caps and the $40 ledger rule; `E9.sha256`, `E9.commit`, `PREREG.sha256` | no | committed before M4 |
| M4 | Generate the test plants (1 ladder, 5 + 5 sealed plants, d0/d50 of `H100g21p1`, the EXP-0004 V corpora of section 5.1), draw the question sets, hash them (`T9.sha256`); free gates (prompt size, availability, blocking completeness I0) | no | as in R4/R5/P3 |
| M5 | **R4 ladder**, one ladder: tiers on 1–30 sheets, ContextRAG high on 1/3/10 | yes | — |
| M6 | **R5 sealed** on 5 + 5 plants: V2T-A2 and the F1 baseline on all ten; duplication d0/d50 on `H100g21p1`; concurrency-1 control on `H1000g21p1` | yes | — |
| M7 | **INFRA** (ADR-0051 v2): ingest ×3, probe and memory on plant 1 per scale; cache-only agent replays and database-only Cypher timing of every attempt on all ten plants | no, Neo4j | M1–M7 checks |
| M8 | **EXP-0004 P3** (section 5.1) and **P4** on the five 1,000-sheet plants (D0/D2/D4, both tiers, paired with M6; the M6 cache reused where a prompt is unchanged) | yes | P4 caps from free dry runs |
| M9 | **EX01** with the fixed adapter, registered arms | yes, small | — |
| M10 | **Scorer audit** (5.3), fixes by the audit rule; then reports, records, superseded lines (3.3), demo data (8) | yes | — |

**Gate G1, re-validation (registered here, before M1).** V2T-A2 passes if, on both validation plants:
- cascade_v4_iso ≥ F1's cascade_v3;
- no dev family is below 50 % on both plants at once.

If G1 passes: no tuning. If it fails (U2 accepted): one tuning round on X100g21s211 under ADR-0061's rules, then
validation on a second fresh pair.

**Over-tuning risk.** We now know where the first sealed run was weak (isolation families, VALVES_ON_PATH).
Re-tuning could fit those spots. Therefore:
- no tuning by default;
- tuning only on dev families of the tuning plant;
- held-out families are never tuned on;
- validation on fresh plants;
- test plants are generated only after the freeze.

F4's repair-prompt change is a reproducibility fix that G1 covers. A defect found after M3 is reported, not fixed,
except through the pre-registered audit rule (5.3). Before M3, one more free read-only review of the changed files
is done.

### 5.1 Which arms run on how many plants (variant B)

| Arm | Plants | Questions per plant | Why |
|---|---|---|---|
| V2T-A2 sealed (Q4 primary, K1, K2, K3, Q5) | 5 at 100 + 5 at 1,000 sheets | 280 (10 per family; 220 headline) | the headline claims; plant-to-plant variation is part of what Q4 asserts |
| F1 baseline (V2T − F1, F1's own claims) | the same ten | the same 280 | paired with V2T-A2 on every question |
| EXP-0004 P4 (E1–E4) | the five 1,000-sheet plants (`H1000g21pkV`) | the same 280, rehomed | paired with M6 on the same plants |
| EXP-0004 P3 (I0–I4) | the four-corpus set on plant 1 (`H100g21p1V`, `H100g21p1d100V`, `H1000g21p1V`, `H1000g21p1d100V`), as registered; plus `H1000g21p2V` … `p5V` | all candidates | the set covers I0–I4 as before. P4 needs D2 and D4 links on every 1,000-sheet V corpus anyway, so the extra four corpora are nearly free (D4 cost ≈ candidates × $0.000088: the first P3 spent $0.254 on 2,886 candidates). They are reported descriptively (pair P/R/F1 per plant), not judged |
| R4 ladder (X1, X2) | 1 ladder (1/3/10/30 sheets) | full sets, 70–92 per size, as registered | ContextRAG high on 1/3/10 is the most expensive arm per question |
| Duplication d0/d50 (descriptive) | `H100g21p1` and its d0/d50 variants | 280 | descriptive arm |
| Concurrency-1 control (descriptive) | `H1000g21p1` | 46 | descriptive arm |
| INFRA | footprint on plant 1 per scale; per-question replays on all ten | — | free |
| Re-validation (gate) | 2 | 163 | a gate, not a claim |

**What five plants buy for the headline:**
- **Scope.** The claim covers "plants of this kind", not "this plant". With one plant, every interval covers only
  question sampling.
- **More questions per family:** 50 per scale instead of 20. This matters most for the held-out families, where the
  first gap sat (DOWNSTREAM_ISOLATION 2/20).
- **Variance.** On dev families V2T-A scored 0.945, 0.957, 0.953 and 0.935 on four untuned v2 plants
  (`EXP-0007-V2T-validation.md`; R5 dev splits in `EXP-0007-R5-sealed.md`; different question sets).
  - That spread (SD ≈ 0.010) is below the question noise, so plant variance on dev families looks small; on held-out
    families it is unknown.
  - Expected Q4 interval half-width ≈ 0.025, against 0.039 before, if plant variance is small.
- **Stated risk.** Q4 passes if its interval contains 0 or lies above, and a narrower interval makes that stricter.
  A real two-point loss that passed with one plant could fail with five. The pre-registration says so.

**Why five:**
- three plants give a cluster bootstrap 10 distinct resamples;
- five give 126;
- ten would double the sealed machine time.

**What the cuts cost (single-plant arms):**
- **R4:** X1/X2 are again single-plant, question-sampling intervals, as in the first measurement. The single-sheet
  end gets no plant replication.
- **Duplication:** the paired n falls from 440 to 220 headline questions, so its interval is about √2 wider
  (first measurement ±0.012 → about ±0.017). Still descriptive.
- **P3:** I0–I4 stay single-plant, as registered.
- **C1:** unchanged.

### 5.2 Aggregation over plants (the ten sealed plants and the five P4 plants)

- **Per plant:** every table first shows each plant's own result (accuracy with Wilson interval, $/q, latency).
- **Pooled estimate:** mean over plants of the per-plant statistic (equal weight; equal n per plant makes it the
  question-pooled value too).
- **Interval:** two-stage cluster bootstrap. Resample plants with replacement, then questions within each drawn
  plant. The resample count and seed are those of the EXP-0007 claims code, fixed in the pre-registration; that code
  is generalised to two stages.
  - With 5 clusters the bootstrap understates between-plant variance by about a factor 4/5. This is stated as a
    limitation.
- **Paired claims** (K1, K2, Q5, V2T − F1, E1–E4): both arms are scored on the same questions. Plants are drawn first,
  then questions, and every arm is evaluated on the same draw.
- **Q4 (1,000 vs 100 sheets):** not paired. The plants at the two scales are independent seeds, and no question
  exists at both scales. The pooled 1,000-sheet accuracy minus the pooled 100-sheet accuracy, with independent
  two-stage bootstraps per scale. Elasticity `e = ln(c1000/c100)/ln(10)` on pooled $/q, same bootstrap. Thresholds
  unchanged.
- **Single-plant arms** (R4 X1/X2, P3 I0–I4, duplication, C1) use the registered single-corpus computations unchanged.
- **Descriptive robustness:** the number of plants on which each claim's per-plant point estimate has the pooled sign.
  It is reported, not judged.

### 5.3 Scorer audit (independent check of the deterministic scorer), hard cap $10 including the pilot

The deterministic scorer over typed JSON answers stays primary. The audit asks a second, independent judge whether
the scorer's verdicts are right. A gold definition that does not match the question, like VALVES_ON_PATH, shows up as
a cluster of "the system is right, the scorer says wrong".

**Judge.**
- `anthropic/claude-sonnet-5.5`: not the system's model (GPT-6 Luna); used in this project before (PAID-04).
- Pinned; reasoning effort low; `max_output_tokens` 2,048.
- Prompt hash and pin hash go into the pre-registration.

**What it sees, per row:**
- the question text and answer type;
- the system's raw reply and its parsed answer;
- a compact rendering of the plant around the gold evidence. Gold-side code renders it, with the evidence nodes,
  their neighbours, and fittings shown as untagged parts. It is capped at 24,000 characters;
- the gold reference, labelled "the benchmark's reference, which may be wrong".

**What it does not see:** the scorer's verdict (it judges blind), and the family's generator definition.

**Output:** JSON `{"verdict": "correct" | "incorrect" | "ambiguous_question", "reference_ok": true|false, "reason": "…"}`.

**Per-call cost.**
- Price basis: the PAID-04 rows (`30-experiments/paid04/answers.jsonl`, 36 Sonnet 5.5 calls, 2026-10-03) fit
  exactly $2.00 per million prompt tokens and $10.00 per million completion tokens. That run's text ran at 2.19
  characters per token.
- Planned prompt: about 2,500 characters of instructions + question and reply + an excerpt of typically ≤ 5,000
  characters. That is ≈ 8,000 characters, ≈ 3,650 tokens, ≈ $0.0073.
- Completion with low reasoning: assumed ≈ 800 tokens (not measured; PAID-04 ran without reasoning at a median of
  175), ≈ $0.008.
- **Estimate ≈ $0.015 per call; worst case at the 24,000-character cap and the full 2,048 output tokens ≈ $0.042.**
  The price may have changed since 2026-10-03, so the pilot measures the real figure.

**Budget order** (registered; the runner stops at the cap):
1. **Pilot, gate G2** (M2b, before the freeze): 45 first-measurement rows with known truth. These are the 13
   VALVES_ON_PATH agent rows where gold and item level differ (H100g2 5, H1000g2 8), the 12 numeric-list parse
   failures of the v2 runs (the three E2E rows are one question), and 20 rows correct under both definitions.
   - G2 passes if at least 80 % of the known-defect rows are judged "correct" or "ambiguous_question" and at least
     80 % of the controls "correct".
   - If it fails, the prompt is revised and re-piloted on these old rows only.
   - Estimate ≈ $0.68; pilot cap $1.50.
2. **Every wrong row on the ten sealed plants:** ANSWERED or PARSE_FAILURE rows scored wrong in either V2T-A2 tier on
   the headline questions, deduplicated by (question, parsed answer), since two tiers giving the same wrong answer
   need one verdict. RETRIEVAL_ERROR rows carry no answer and are only counted. Expected ≤ 450 rows before
   deduplication (R5's wrong-answer rates: Cypher 8–10 %, agent 9–13 % of the headline), ≈ $6.75.
3. **Random right sample, minimum** 2 per family per scale = 88 rows, pre-registered seed, ≈ $1.32. This gives the
   unbiased agreement rate on right rows; at 95 % agreement its interval is about ±5 points.
4. **ContextRAG-high wrong rows of the ladder** (≈ 83, from R4's 0.686/0.654/0.614 at n 70/78/88), ≈ $1.25. Only if
   the budget allows.
5. **More right samples**, up to 5 per family per scale, only if the budget allows.

After the pilot the sample is sized to the remaining budget at the measured per-call cost, in this order, and written
into the pre-registration. Expected total ≈ $9 at the estimated cost: steps 1–3 certain, step 4 about half covered.
At the worst-case cost, step 2 alone could exhaust the budget; then step 2 is cut to a pre-registered random subset
stratified by family, and the audit reports that it covers only part of the wrong rows.

**Disagreement handling (registered, so nothing is tuned to the test).**
1. The main session checks every disagreement against the graph with a script. Each is classified as a
   **scorer/gold defect**, a **judge error**, or an **ambiguous question**.
2. A scorer/gold defect is fixed **only in the scorer or the gold, never in the system, its prompts or the question
   selection**. The fix:
   - is a rule from the question text or answer type, written down before re-scoring;
   - is applied family-wide, on every plant and every arm (V2T-A2, F1, ContextRAG, EXP-0004), by code with a test;
   - takes effect through a free, deterministic re-score of the stored rows.
3. An ambiguous question is scored by accepting every defensible answer (section 4 rule). No question is removed or
   reworded.
4. The reported result is the post-audit score; the audit is part of the registered scoring procedure. The
   pre-audit score and every changed row (count per family and arm) go in one table of the same report. A claim
   whose verdict differs before and after the audit is named.
5. Judge errors change nothing; they are counted.

**Reported:**
- agreement rate on the random right sample;
- agreement rate on the wrong rows;
- Cohen's κ;
- disagreements by class and by family;
- the share of wrong rows the budget covered.

**Would it have caught defect 1?** The six "wrong" VALVES_ON_PATH agent answers at H1000g2 all equal the item-level
count. A judge counting valves on the rendered route calls them correct. The pilot tests exactly this before the
audit is relied on.

### 5.4 The red button: one launcher, nothing before "mehet"

**Rule (user, 2026-11-07).** No part of EXP-0008 runs before the user says "mehet". This includes the free steps:
plant regeneration, question pools, gates. The user says it only after reading the study map. Until then everything
is prepared, and one detached launch then runs M0 → M10 end to end.

**Pre-registration and freeze: split so that both precede every test plant.**
- **Part A, before the button (committed on the user's order with the last F-task):**
  `data/runs/exp0008/prereg/PREREG_A.md` holds everything decidable now:
  - claims and thresholds;
  - the plant design and aggregation (5.1–5.2);
  - gates G1/G2 and the audit protocol (5.3), the judge prompt and pin hashes;
  - the ledger rule (§6);
  - **the test seeds**, drawn now by `draw_seeds.py` (F12). Drawing a seed is not generating a plant, and the seeds
    are then fixed before any plant exists.
- **Part B, inside the launcher at M3, after M2b and before M4:** `PREREG_B.md`, filled mechanically from the
  stage outputs:
  - G1 verdict and numbers;
  - τ₁, τ₂ from M2;
  - the pilot's per-call cost and G2 verdict;
  - the audit sample sizes that follow from it;
  - the step caps.
- **The freeze, also at M3.** The launcher:
  1. refuses a dirty working tree under `src/` and `data/runs/exp0008/*.sh`, and a HEAD other than the one named in
     `PREREG_A.md`;
  2. writes `E9.commit` (= that HEAD), `E9.sha256` and `PREREG.sha256` (over part A + part B + every frozen file);
  3. timestamps them in the log;
  4. only then starts M4.
- The launcher never commits. The user commits part B and the hashes afterwards, on their order. The hash and the
  log timestamp before the first test-plant build are the evidence.

**Launcher `data/runs/exp0008/run_all.sh`.**
- **Start:** `nohup sh data/runs/exp0008/run_all.sh > data/runs/exp0008/run_all.log 2>&1 &`.
  - `--from <stage>` resumes; the default resumes after the last completed stage.
  - `--smoke` runs the whole chain on a tiny plant with the fake transport.
- **Stages:** M0, M1, M2, M2b, M3, M4, M5, M6a (V2T-A2), M6b (F1), M6c (d0/d50, C1), M7, M8a (P3), M8b (P4), M9, M10a
  (audit), M10b (reports). Each stage writes `state/<stage>.done` with the sha256 of its outputs. A rerun skips a
  done stage after re-checking its hashes. Inside a stage the harness's own row-level resume applies.
- **Monitoring:** one line per event, `=== <UTC time> <stage> <START|DONE|STOP|GATE PASS|GATE FAIL|CAP> <detail>`,
  plus the per-run harness logs under `logs/`.
- **Gates enforced in order:**
  - M0: composition bands (a failed band stops: U4) and the pool memory probe;
  - G1 after M1; G2 after M2b;
  - the M3 freeze checks;
  - the free gates of M4 (prompt size, availability, I0, question-set hashes);
  - replay gates where the first measurement had them.
- **Money:**
  - before every paid stage, a dry run over a copy of the cache counts the misses and sets the step cap;
  - the ledger (§6) applies: runs ≤ $30 cumulative, audit ≤ $10, EXP-0008 ≤ $40;
  - the OpenRouter balance is read before each paid stage and must cover that stage's cap. If the endpoint cannot be
    read, the stage stops; F15 verifies the endpoint in smoke mode;
  - a run that reaches its cap stops with `=== … CAP …` and the resume point.
- **Neo4j:** every stage that needs the store wipes and loads its corpus (`--fresh-database`) on the user's
  `neo4j` database, one corpus at a time; the final load is `H1000g21p1`.
- **Clean stop:**
  - **Designed stops that need the user:** U4 (a composition band) and G1 or G2 failing (their remedies are design
    work). All three fall before M3, so no test plant exists yet. A remedy that changes part A (a revised judge
    prompt after G2, for example) is committed as a new part A before the resume.
  - **Stops that need only a top-up or a restart:** the ledger or a step cap, an unreadable balance, an
    infrastructure error (Neo4j down, network).
  - Every stop writes `state/STOPPED` with the stage, the reason and the exact resume command.
  - Nothing else asks a human. The audit's sample size follows from the pilot by rule, so no audit-cap question
    arises unless the ledger is hit.
- **Never:** a commit, a push, a paid call outside a capped stage, a write into a first-measurement folder, a run on
  a retired seed.

**Readiness checklist (all true before the user's "mehet"):**
1. F1–F15 committed (on the user's order); `pytest`, `ruff`, `mypy --strict` green on that commit.
2. The second read-only review of the changed files done; its findings fixed or recorded.
3. `PREREG_A.md` with the drawn seeds, the judge prompt and pin committed. HEAD equals the commit it names; the
   working tree is clean.
4. `run_all.sh --smoke` has passed end to end on a tiny plant with the fake transport:
   - zero paid calls;
   - every stage reached;
   - a forced G1 fail, G2 fail, cap hit and band fail each stop with a resume point;
   - one resume completes.
5. Neo4j is up and the `neo4j` database reachable; `e7tune` dropped; free disk ≥ 10 GB (a generous margin; the
   1,000-sheet store was 55 MiB plus 34 MiB of logs in INFRA-2).
6. OpenRouter balance ≥ $40, read by the launcher's own check.
7. The laptop is plugged in, sleep is off, and no other heavy job runs (the latency claims depend on it).
8. The user has read the study map and says "mehet".

## 6. Cost and time

**Ledger rule.**
- EXP-0008 has a hard program cap of **$40**, with $10 of it reserved for the audit, so the runs may spend at most
  $30.
- Each runner reads the spend so far from every EXP-0008 `calls.jsonl` (calls not served from the cache) and runs
  with cap = min(its own cap, $30 − runs spent so far). The audit runs with min($10, $40 − all spent).
- A step that would need more stops and asks.
- Step caps are the basis × 1.5, as the registered cap rules do; the real cap of each step comes from its free dry
  run.

| Step | Basis (source) | Estimate | Step cap |
|---|---|---|---|
| M1 re-validation, 2 plants | $1.32 (`30-experiments/EXP-0007-V2T-validation.md`) | $1.32 | $2.00 |
| M2 EXP-0004 dev | ≈ $0.02 (EXP-0004 ≈ $0.275 minus P3 $0.254, `50-progress/2026-W45.md`) | $0.02 | $0.05 |
| M5 R4, one ladder | $3.25, ContextRAG $2.67 of it (`EXP-0007-R4-ladder.md`) | $3.25 | $4.90 |
| M6 V2T-A2, 10 plants × 280 | per 560 questions: $1.374 at 1,000 sheets (agent $0.954 + Cypher $0.420), $1.293 at 100 (`EXP-0007-R5-sealed.md`); halved, × 5 each | $6.67 | $10.00 |
| M6 F1 baseline, 10 plants × 280 | $1.67 for two 560-question plants (`EXP-0007-R5-sealed.md`) | $4.18 | $6.27 |
| M6 d0/d50, `H100g21p1` × 280 each | $1.78 for two 560-question plants (`EXP-0007-R5-sealed.md`); halved | $0.89 | $1.34 |
| M6 concurrency-1 control | $0.055 (`EXP-0007-R5-sealed.md`) | $0.06 | $0.10 |
| M7 INFRA | $0, zero paid calls (`EXP-0007-INFRA-2.md`) | $0 | $0 |
| M8 P3, plant-1 set + four 1,000-sheet V corpora | $0.254 for the set (`2026-W45.md`); + 4 × 794 candidates × $0.000088 | $0.53 | $0.80 |
| M8 P4, 5 plants × 280 | $1.94 per 560-question plant (`EXP-0004-E2E.md`); halved × 5 | $4.85 | $7.28 |
| M9 EX01 | $0.0973, 185 calls (`exp0001/ex01/calls.jsonl`) | $0.10 | $0.25 |
| smokes | R5 $0.002, EXP-0002 $0.02 (run notes) | $0.10 | $0.15 |
| **Runs** | | **$21.97** | **ledger: ≤ $30** |
| M2b + M10 scorer audit (pilot ≈ $0.68 + ≈ 550 calls) | $0.015 per call estimated from PAID-04's per-token price and the planned prompt size; pilot measures | ≈ $9 | **$10 hard** |
| **EXP-0008 total** | | **≈ $31** | **$40 hard** |
| contingency if G1 fails (one tuning round + second validation) | $0.43 per round + $1.32 (`EXP-0007-V2T-validation.md`) | +$1.75 | inside the $30 runs ledger |

The 1.5× step caps sum to $33.14 for the runs. The ledger, not the sum, is binding, which leaves about $8 of headroom
over the runs estimate.

**Machine time.** Recorded per-unit figures:
- H1000 generation 421.6 s (INFRA-2);
- H1000 question pool 8,585 s, H100 pool 35 s (`sealed/qpool/*/availability.json`);
- R5 headline at 1,000 sheets: Cypher 1.44 h + agent 1.70 h per 560 questions; at 100 sheets 0.38 h + 0.50 h (call
  timestamps);
- F1 agent at 1,000 sheets 0.59 h;
- P4 7.9 h per plant at 560 questions;
- INFRA-2 2.4 h.

| Block | Estimate |
|---|---|
| question pools: 5 sealed + 1 validation at 1,000 sheets × 2.4 h; the rest minutes | 14.5 h |
| plant builds (sealed, validation, EXP-0004 V corpora) | ≈ 2 h |
| M1 re-validation runs | ≈ 3 h |
| M5 one ladder | ≈ 3 h |
| M6 V2T-A2, 10 plants × 280 | ≈ 10 h |
| M6 F1, 10 plants × 280 | ≈ 6.5 h (F1 Cypher time not recorded separately; estimate) |
| M6 d0/d50 + C1 | ≈ 1.1 h |
| M7 INFRA | ≈ 7 h (footprint 3.3 h + replays on ten plants) |
| M8 P3 + P4 | ≈ 2.5 h + 20 h |
| M9 EX01, M10 audit | ≈ 2 h |
| **Total** | **≈ 72 h** |

Feasibility:
- 72 h is about 3 days of continuous machine time, about 6–7 calendar days with gates and approvals.
- Nothing runs in parallel during a timed run, since that would distort the latency claims K1 and K3.
- The M0 probe confirms that a 1,000-sheet pool fits in memory before five are scheduled.

**Neo4j.**
- One corpus at a time: each step wipes the database and loads its own plant. The temporary database `e7tune` is
  dropped first.
- A 1,000-sheet load took 26.8 s (INFRA-2), so the ten plants' sequential loads add minutes.
- The last load is `H1000g21p1` (`plant_lines`) for the demo. ADR-0064 gets an amendment.

## 7. v1 (EXP-0001 ladder, EXP-0002, frozen F1) — U3 accepted: leave with a note

- v1 is the first system and history. The thesis emphasis is the v2 line and the tuned system.
- The note on the two v1 run notes: the parse defect touches 4 EXP-0002 rows (`ST-AG-H100` 3, `ST-AG-H1000` 1) and 2
  EXP-0001 rows (`E1-CTXH-H10`, `E1-CTXH-H30`). All 6 are correct once parsed.
- Expected effect: EXP-0002 cascade_v3 unchanged (the Cypher tier answered those questions correctly), agent-only
  +3 / +1; EXP-0001 ContextRAG high +1 at H10 and at H30.
- Defect 1 cannot occur on v1 (no fittings).
- Only EX01 is re-run (M9).

## 8. Demo v2

- **T1, T2, T4, T5** (code independent of the plant) are done by a coder while the launcher runs, after F1–F15. They
  touch no frozen file, and the launcher's M3 hash check guards that.
- **T3** after the M6 report exists.
- **T6 and T7** after the launcher finishes: replay agreement against the M6 cache, config, examples, and the
  drawing export of the demo plants.
- Demo plants: plant 1 at 1,000 sheets (main) and plant 1 at 100 sheets (small). The thesis states that the demo
  shows sealed plants after their test ran, as ADR-0064 already says.

## 9. Coder tasks, in order, one at a time

Every task: tests pass (`pytest`, `ruff`, `mypy --strict` as the repo runs them), coder style, one commit proposal.
Paths are under `src/plantgraph/` unless they start with `data/` or `tests/`. No task runs any EXP-0008 stage. Done
checks run on first-measurement data, dev fixtures or the smoke plant.

| # | Task | Files | Done-check |
|---|---|---|---|
| F1 | Answer parser: integer lists → strings in UNIT_SET/SHEET_SET, a bare integer → string for UNIT_ID, BOOLEAN 1/0 → yes/no; floats and bools still refused | `qa/final_answer.py`, `tests/test_final_answer*.py` | re-parsing every stored `raw_reply` in `data/runs/**` changes only the 20 rows of §3.1 (and their replays and dry runs); no ANSWERED row's parsed answer changes |
| F2 | VALVES_ON_PATH at item level: `item_valve_counts(plant, source) -> dict[str, frozenset[int]]` on `next_path_items`; candidacy and reference from it | `qa/questions/families_heldout_paths.py`, tests | small graphs: raw path longer in items than the item path; ambiguous pair refused; v1-style graph unchanged. On the first-measurement sealed plants it reproduces 5/20, 8/20, 4/20, 4/20 and 0/15 |
| F3 | Client and harness: `finish_reason: "error"` → ProviderError (retried, not cached); back-off and failed attempts in the call latency; retries in `calls.jsonl`; ContextOverflow cached and replayed; tombstone spend capped at the remaining budget; abandoned time in an optional row field the signals add; late-after-timeout cost in the run summary; resume spend guard counts only calls not served from the cache; deterministic row order after a retried ProviderError | `llm/client.py`, `llm/models.py`, `qa/harness/usage_meter.py`, `qa/harness/summary.py`, `qa/harness/fill.py`, `qa/cascade/signals.py`, tests with a fake transport | each behaviour has a test; old `calls.jsonl` and `answers.jsonl` still load |
| F4 | Cypher tier: guard worker in `contextvars.copy_context().run`; repair prompt masks volatile numbers; token-aware write filter | `qa/cypher_guard.py`, `qa/strategies/cypher_rag_lines.py`, `qa/cypher.py`, tests | DB split non-zero through the guard; two repair prompts from errors with different memory numbers are byte-identical; filter cases (`CREATE` inside a string literal, a property named `set_point`) |
| F5 | Cascade and report: recall over the scope; `--setting` runs `run_problems`; offline acc@C follows the live fallback | `qa/cascade/evaluate.py`, `qa/cascade/cli.py`, tests | on a toy join, recall uses scope rows; offline equals live on the fallback case |
| F6 | INFRA: DB-only replay runs every recorded attempt plus the tag check; M1 flags old-run fallbacks; the notice names the source clock | `infra/cypher_replay.py`, `infra/report_checks.py`, `infra/report.py`, tests | fake source: queries = attempts + tag checks; M1 flag on a fallback fixture |
| F7 | Run freeze: optional hashes of the prompt-building modules and of the corpus `ingest.json`; a resume compares them when present | `qa/harness/freeze.py`, `qa/models.py`, tests | an old `run_config.json` loads; a changed prompt module refuses a resume |
| F8a | Generator v2.1, flowsheet: wire the column distillate and side draws; the combined-column fallback obeys the sheet cap; `p_split_range` wired or removed; `generator_version` "v2.1", "v2" refused | `benchmark/v2/flowsheet.py`, `benchmark/v2/patterns/column*.py`, `benchmark/v2/config.py`, `benchmark/v2/instruments_extra.py`, tests | on a dev-seed test plant (seed 1, 300 units): every distillate and side draw has a consumer; no sheet above its cap; "v2" refused |
| F8b | Generator v2.1, sheets and stats: tank-farm inlet chains and own-sheet pump suction trims on their equipment's sheet; trim heater grouped as a heater; a wired cross-unit out-port counted once in `sheet_stats` | `benchmark/v2/sheets.py`, `benchmark/v2/split_by_sheet_group.py`, `benchmark/v2/patterns/heat.py`, `benchmark/v2/sheet_stats.py`, tests | 0 tank-inlet valves off their tank's sheet on the dev-seed test plant; a wired port counts 1 stub |
| F8c | Generator v2.1, instruments and tags: fuel-gas sensors on the fuel-gas line; reactor code R; UC inputs with their real measured variable; branch lines with their own service code; spec-break numbering and rating step-up; `tagNameSequenceNumber` without the spare suffix | `benchmark/v2/patterns/reaction_parts.py`, `benchmark/v2/tags.py`, `benchmark/v2/instruments_extra.py`, `adapters/pydexpi_builder_v2*.py`, tests | each rule a test on a pattern instance; LOOP_MEASURED_EQUIPMENT on a furnace fuel loop names the line item |
| F9 | Resolution and EXP-0004: exact τ scores; a one-to-one slot only for a merged link; duplicate outgoing connector numbers refused and counted; rehoming proof against the corpus; P3 spend from call records; corpus id with `--tag-variants`; the P3 runner takes the plant-1 set plus extra V corpora (descriptive) | `exp0004/tuning.py`, `resolution/identity_links.py`, `resolution/pairing.py`, `exp0004/rehome.py`, `exp0004/report.py`, `exp0004/commands.py`, `ingest/headline_v2.py`, tests | on the first-measurement dev corpus τ₂ = 8/9, F1 0.984; first-measurement P3 link sets unchanged; the proof fails on a tampered fixture; extra corpora appear only in a descriptive table |
| F10 | Adapters and validation: bubble tag with the function letters on a Proteus import; carrier removal only for v2; the PLAUSIBLE items, each first as a failing test | `adapters/pydexpi_adapter.py`, `adapters/pydexpi_loop_tags.py`, `graph/validation.py`, `adapters/pydexpi_generic.py`, `adapters/pydexpi_proteus_import.py`, `benchmark/open100/crops.py`, tests | EX01 bubbles carry their letters; v1 synthetic golden unchanged; each PLAUSIBLE item fixed or recorded "not reproduced" with its test |
| F11 | LINE-01 also catches an identity split across line items | `qa/harness/line_view_fidelity.py`, tests | a split-identity fixture fails |
| F12 | Hygiene, seeds, naming: retire first-measurement test seeds; `draw_seeds.py` writes the test seeds into `PREREG_A.md`; ids with `g21` and the plant index | `qa/exp0008/hygiene.py`, `ingest/headline_v2.py`, `data/runs/exp0008/draw_seeds.py`, tests | a retired seed is refused for a test role; ids composed as specified; the seed draw is reproducible and generates no plant |
| F13 | Multi-plant statistics: two-stage cluster bootstrap (plants, then questions) for the sealed claims, V2T − F1 and E1–E4; per-plant tables; the robustness count. Single-plant arms keep the registered code path | `qa/cascade/stats.py`, `qa/cascade/report_claims.py`, `qa/cascade/report_sealed*.py`, `exp0004/e2e_report.py`, tests | with one plant the new code reproduces the first measurement's registered intervals exactly (same seed); on a synthetic two-level fixture the interval covers the true mean at the expected rate |
| F14 | Scorer audit: gold-side plant excerpt (≤ 24,000 chars), judge prompt and pin, selection in the budget order of §5.3 with deduplication by (question, parsed answer), sizing from the pilot's measured cost, a runner behind the audit ledger, the disagreement sheet, agreement / κ report, the 45-row pilot set | new `qa/audit/` (`select.py`, `excerpt.py`, `judge.py`, `budget.py`, `report.py`, `cli.py`), `qa/prompts/audit_judge.txt`, tests with a fake transport | selection reproducible from its seed; the judge never receives the scorer's verdict (test); sizing never exceeds the remaining audit budget; the pilot set holds 45 rows |
| F15 | **The launcher** `data/runs/exp0008/run_all.sh` (+ `lib.sh`, `stages/*.sh`, `ledger.py`, `balance.py`, `PREREG_A.md` template, `PREREG_B` writer, `freeze.sh`): the stages, gates, ledger, balance check, state files, `===` log lines, resume and `--smoke` of §5.4 | `data/runs/exp0008/**`, tests for `ledger.py` / `balance.py` / the PREREG_B writer | `--smoke` passes end to end with zero paid calls; forced G1, G2, cap and band fails each stop with `state/STOPPED` and a resume command, and one resume completes; M3 refuses a dirty tree and a wrong HEAD; no stage writes outside `data/runs/exp0008/` |

Then the readiness checklist (§5.4). Nothing runs before the user's "mehet". The launcher runs M0–M10 detached; the
main session watches the `===` lines and reports each gate and each stop in the chat.

## 10. Decisions still open for the user

U1–U3 are answered (fresh seeds; G1 without re-tuning by default; v1 with a note). Plant counts, aggregation, the
audit design, the budget variant B and the launcher are decided here as the user asked.

- **U4 (only if it happens):** if the fixed generator breaks an ADR-0059 composition band at M0, the launcher stops.
  The choice is then to adjust generator settings (recorded as a generator change) or to report the band as missed.

## 11. Implementation notes carried forward (main session)

- F2: ambiguous VALVES_ON_PATH pairs are refused at generation (§4), so D1's "accept any count" no longer applies to EXP-0008 question sets.
- F2: the "0/15 ladder" figure in §3.1 does not match the ladder pool (55 VALVES_ON_PATH questions, one ambiguous on H30g2 P-601A→H-701); check which were run before quoting it.
- F5: offline acc@C now follows the live late-fallback rule (also in tune_report secondary cutoffs); a dev D100 cascade_v1 number moved 160 → 165.
- F7: configs built by hand (exp0007, exp0004 E2E paths) leave `code_hashes` / `corpus_ingest_sha256` empty, so F15 must make every EXP-0008 run fill them; the prompt-module list was chosen by reading module headers, not by import tracing — the second review (readiness item 2) should confirm it.
- F8a: the product farm takes every liquid stream its own train left open (the "later Separation" option of the grammar is not built); `p_split_range` and the split-range template were removed, not wired.
- F8b: tank-inlet valves off their tank's sheet 24/87 → 0/87 (seed 1, 60 units; the reviewer's 12/72 used a narrower definition); own-sheet pump suction parts 162 → 0.
- F8c: the U5 outlet TIC of both the steam and the bypass loop moved to the outlet tee (main-session decision, consistent with the fuel-gas fix); fuel-gas loops now sense line items, so LOOP_MEASURED_EQUIPMENT no longer asks about 62 furnace loops (seed 1, 300 units); spec break: downstream class lighter, upstream heavier; `trims_utility.ejector_discharge_silencer` kept (used by trim tests).
- F9: τ grid now exact (the "8/9, F1 0.984" figure in §3.1 was computed by the architect on the first-measurement dev corpus, which v2.1 cannot rebuild; the v2.1 τ comes from M2). There is no P3 runner script yet: F15 must drive P3 over the plant-1 set plus the extra V corpora through the existing `exp0004 build/decide/score/report` CLI. `ingest synthetic` refuses `--tag-variants`/`--identity-links` without `--corpus-id`.
- F11: LINE-01, API-01 and PLANT-01 part b report split tags; untagged items are named by their sorted (direction, relation, neighbour tag) signature; edge properties are compared as per-name multisets, because two look-alike untagged ends (same signature) exist on a correct v2 plant (E-403 on the v2 fixture). API-01 passes on the v2 fixture plant (precision = recall = 1.0, no split tags); PLANT-01 on a real Neo4j load is untested until EXP-0008's free gates.
- F12: ids `D{n}g21`, `X{n}g21s{seed}`, `H{n}g21p{k}` (+`d0|d50|d100`, +`V|Vf` for EXP-0004), ladder `H1g21`/`H3g21`/`H10g21`/`H30g21`, validation `VAL100g21`/`VAL1000g21`. Seed tool `python -m plantgraph.qa.exp0008.draw_seeds --draw-seed N` writes `data/runs/exp0008/prereg/seeds.json` (mode "x"); its printed table goes into PREREG part A (F15). Retired seeds {5100, 5001, 5002, 5003, 212, 213}.
- F12 → F13/F15 MUST parameterise these first-measurement constants for EXP-0008: `tune_select.TUNING_CORPUS_ID`, `rehome.DEFAULT_SEALED_CORPUS_ID`, `e2e_report.R5_CORPUS`, `exp0001/report.LADDER_IDS_V2`, `exp0007/cap_plans` ids, the `exp0007 test-seed` CLI table, and the regex `H(\d+)(?:g2)?` in `exp0001/report_claims.py:150`, which does not parse `H30g21`.
- F13: two-stage cluster bootstrap in `qa/cascade/stats_cluster.py` (one plant ⇒ exactly the registered `paired_bootstrap`/`unpaired_bootstrap`); sealed report `--scale LABEL=C1,...`, E2E report `--plant R5:V` (repeatable) + `--headline-n 220`; ladder and P3 statistics unchanged (one plant, §5.1). K3 pooled latency resamples questions only (descriptive). F15 must set the ladder `--run-prefix` (default guess `E8`) and parameterise `e2e_caps.COST_PER_QUESTION_USD` for EXP-0008. One-plant reproduction on stored first-measurement rows: Q4 scale rows and Q5 identical; T1 acceptance and K2 differ only by the F5 changes; `cascade_v4_iso`, K1 and E1–E4 not reproducible under v2.1 (need the v2 corpus graph).
- F14: `python -m plantgraph.qa.audit {pilot-set,judge,select,report}`; judge prompt `src/plantgraph/qa/audit/audit_judge.txt` (kept out of `qa/prompts`, whose hash set guards every stored run's resume), hash from `judge.template_sha256()` for PREREG part B; verdicts `correct`/`incorrect`/`ambiguous_question` + `reference_ok`; ledger $10 hard ($1.50 pilot), worst-case pre-call check $0.042; typical prompt ≈ 2.3–2.8k chars on v2.1 fixtures. G2 pilot: run `scripts/audit_export_subgraphs.py` on a `git archive 4dfad69` copy (`PYTHONPATH=<copy>/src`); the main session supplies `--valves-ids` (the 13 first-measurement VALVES_ON_PATH ids from §3.1 / F2 recompute). ANSWERED rows carry no `raw_reply`, so the judge sees the parsed answer there.
- F14 pilot set (2026-11-08): the pilot takes every known defect row of each group (at least `MIN_DEFECTS_PER_GROUP` = 8, else `ValueError`) plus exactly 20 controls, instead of 13 + 12 + 20; the first-measurement data holds 16 distinct wrong V2T-A VALVES_ON_PATH rows and only about 9 numeric-list parse failures, so exactly 12 was impossible. G2's percentage thresholds are unchanged.
- 2026-11-08 G2 pilot inputs prepared in `data/runs/exp0008/inputs/pilot/` (runs.txt: 8 first-measurement agent runs; valves_ids.txt: the 21 item-level-differing VALVES_ON_PATH ids of H100g2, H1000g2, H100g2d0, H100g2d50 from the F2 recompute; questions/; subgraphs.json: 45 excerpts cut with the E8 copy). Pilot set: 49 rows (21 valves defects, 8 parse defects, 20 controls). Free cache-only pass: judge prompt sha256 091e5863…, prompt chars median 18,420, max 27,584 (larger than the 8k planned; ≈ $0.025 per call at the PAID-04 price, so the pilot ≈ $1.2 under its $1.50 cap and the audit's wrong-row cut does more work). One control (H1000g2 FLOW_PATH GTV-61003|GTV-177004, 1,108 evidence parts) cannot fit the 24,000-char excerpt and is listed as unjudgeable; G2 is computed over judged rows, so it holds 19 controls.
- 2026-11-10 R1: F5 late-fallback rule reverted (the F5 line above is superseded): offline acc@C is the conservative rule again (correct and summed tier latency <= C), because live the stopped agent tier still answers from partial evidence and the accept rule takes it, which a stored run cannot reproduce; so offline acc@C is a lower bound of the live cascade. The scope-recall denominator and `--setting` stay; the dev D100 cascade_v1 pin is back at 160.
- 2026-11-10 R1: `PROMPT_BUILDING_MODULES` completed by import tracing from the Cypher, context and agent strategies: agent loop/actions/models/strategies, tool registry, primitives, traversal, item graph, line graph, contraction, plant-API model, `cypher.py`, `cypher_guard.py`, `tag_check.py`, `class_vocabulary.py`, `anchors.py`, `sheet_selection.py`, `routing.py`, `graph_view.py`, `need/{context,programs,rules,labels}.py`. Not covered: `graph/line_view.py` lies outside `qa/` (the list is relative to `qa/`), yet it shapes the line-view tool text.
- 2026-11-10 R1: the judge is blind to how a reply was read: `JudgeInput` holds one `raw_reply` that is always the model's text (an ANSWERED row, which stores none, gets the canonical `{"answer": ..., "not_present": ...}`); the "answer read from the reply" section and the "no usable answer is incorrect" wording left `audit_judge.txt`, so its sha256 changed (091e5863... is stale for PREREG part B).
- 2026-11-10 R1: audit cap guard is per call: `worst_case_call_usd(prompt_chars)` = chars / 2.19 x $2/M + 2,048 x $10/M (PAID-04 basis); a call is refused if spent + that > cap (the longest measured pilot prompt, 27,584 chars, costs up to $0.0457, above the old fixed $0.042). Provider-error calls that reported usage are booked (`ProviderError.paid_usd`). Verdicts carry `template_sha256`; a revised prompt re-judges, and `read_records` returns the newest verdict per row. Pilot stage cap $1.50 -> $2.50 (inside the $10). Judging order: `right_min` before the wrong rows (the cut still follows the budget order). `parse_failure_candidates` keeps only rows whose re-read answer scores correct.
- 2026-11-10 R1: `RunDir.spent_usd` and `ledger.paid_usd_of_calls` skip a truncated last `calls.jsonl` line with a warning (`qa/harness/jsonl_tail.py`) and still raise on a bad line elsewhere.
- 2026-11-10 R1: a 200 reply with `finish_reason` "error" is a failure whatever its text (retried, never cached, `ProviderError` after retries); every discarded error attempt that reports usage or cost is logged in `calls.jsonl` (`error_kind` provider_error, with its response) and summed in `ProviderError.paid_usd`. Gap: the audit ledger books `paid_usd` only on a final failure; discarded attempts before a later success are in `calls.jsonl` but not in the audit ledger.
- 2026-11-10 R1: `infra/cypher_replay.py`: a row with no recorded query replays as a row with zero queries (outcome `no_query`, tag check only if recorded; counted in `n_without_query`, not in `n_replay_errors`) instead of raising; attempts replay through `GuardedCypherSource` (live timeout + 30 s hang grace); the `measures` text and the report notice say "recorded queries sent again"; M1 with every replay fallen back says so instead of "no replay was given".
- 2026-11-10 R2: product farm (`patterns/storage.py`): no shared receipt header any more; receipt line k fills its own group of tanks (tank i belongs to receipt i mod receipts), the tank count is raised to the receipt count when the deck card is smaller, and the variant label shows the raised count. Seed 1, 300 units, measured on the HEAD plant: 52 of 60 farms had two receipt lines and all 52 shared a header (45 with two wired product streams; the reviewer's 32 used a narrower definition) -> 0 farms with a tank fed by two receipts. The draw order is unchanged (52 two-receipt farms before and after); battery-limit draws now happen once per receipt, so the later draws of a farm shift.
- 2026-11-10 R2: composition bands can be judged on the pooled plants of a scale: `composition --pool --seeds ...` (new `benchmark/v2/composition_pool.py`) judges every band on the plain mean over the plants and prints the per-plant values unjudged; the exit code follows the pooled verdicts; without `--pool` the per-plant judging for tuning is unchanged. The pooled mean of a min or max quantity is the mean of the per-plant min or max, and an exact band (`= 1`) holds only if every plant reaches 1. R3 wires the launcher; plants are named by seeds (corpus ids follow from `--target-sheets` and the seeds), plan files are not read.
- 2026-11-10 R2: `sheet_stats.wired_out_ends` counts an open-line end as wired only when a line of ANOTHER unit starts from it: seed 1, 300 units, 386 -> 370 wired ends (16 wrongly wired -> 0); seed 1, 60 units 80 -> 76 and the stub total 612 -> 611 (the latter also moved by the other R2 fixes).
- 2026-11-10 R2: spec break (`trim_plan.py`): branches (drains, vents, bypass, taps) off the stretch before a break take that stretch's heavier class (`TrimPlan.with_branches_on_break_class`, run by `with_stream_kinds` at the end of every pattern, so branches planned apart from the main line are covered); only the class field of their line number changes. Seed 1, 300 units, measured: 73 of 73 such branches were in the lighter class -> 0.
- 2026-11-10 R2: tap branches take their parent line's service code: the tap helpers (`thermometer_tap`, `pressure_gauge_tap`) take the parent line's style, and the column's dp tap, the compressor's inlet/cooler-outlet/discharge taps and the intercondenser TI pass it. Seed 1, 60 units, measured by tap role: 20 taps (13 dp roots, 4 intercondenser TI, 1 inlet TI, 1 cooler outlet TI, 1 discharge PI root; the main session counted 21) -> 0; the relief lines to the flare stay `FL` on purpose.
- 2026-11-10 R2: `require_drawn_test_seed` refuses every retired seed, 212 and 213 included, before looking at the 5000-5999 range; `DEFAULT_SEED_PLAN_PATH` is built from the repository root found from the package location, so `load_seed_plan()` no longer depends on the working directory. Side effect: `ingest synthetic` and `composition` now refuse `--seed 212/213` (the retired exp0007 validation seeds).
- 2026-11-10 R3: P3 report (`m8_identity.sh`): `exp0004 report` gets the scored test corpora only; the dev corpus has no `score.json` (M2 writes taus, not scores) and the design keeps P3 on the test set.
- 2026-11-10 R3: cap cost per question (`qa/exp0008/caps.py`) is now per cost key: P4 arms use the first measurement's real spend per missed question (Cypher d0 0.0741/148 = 0.000501, d2 0.0347/102 = 0.000340, d4 0.0938/83 = 0.001130; agent d0 0.00195, d2 0.00266, d4 0.00431; `EXP-0004-E2E.md` Spend table) and ContextRAG uses the R4 ladder's size-specific $/q (H1 0.00274, H3 0.00600, H10 0.02172) instead of the 2.67/236 average; the 1.5 factor and the step ceilings stay. Stages pick the key through `TIER_SUFFIX` in `paid_run`.
- 2026-11-10 R3: frozen paths (`m3_freeze.sh`, `readiness.py`) exclude `src/plantgraph/demo` (git pathspec `:!`) and add `scripts/audit_export_subgraphs.py`, `data/runs/exp0001/inputs` and `data/external/C01V04-VER.EX01.xml`; `qa/harness/freeze.py` hashes `graph/line_view.py` too (`PROMPT_BUILDING_MODULES_OUTSIDE_QA`, key `plantgraph/graph/line_view.py`).
- 2026-11-10 R3: `replay_run` marks a passed replay (`replays/INF-<run>.replayed`) and skips it on a resume, so a Cypher-tier replay never runs against whichever plant is loaded by then.
- 2026-11-10 R3: M5 calls `require_frozen`; the ladder's ContextRAG wrong rows get excerpts (`audit_subgraphs` also cuts the ladder plants) and the judge gets `--run` for the three `E8-CTXH-*` runs.
- 2026-11-10 R3: M10b reports: added the F1-baseline sealed report (`--claims f1 --cutoff-s 120`, policies as `exp0007/run_sealed.sh`, with `--scale`), per-plant `tune-report`s and the concurrency-1 report (new `qa/exp0008/c1_report.py`: correct counts, verdict agreement, latency median/p90, as R5 quoted them by hand). A failed report is noted in `reports/FAILED.txt`, the next report still runs, the final `H1000g21p1` `plant_lines` load always runs, and the stage stops last naming the failed reports; `demo_load.sh` loads the demo plant alone.
- 2026-11-10 R3: `launch.sh` sets `E9_NEO4J_HOME` (environment, else `.env`, else the Neo4j Desktop folder already named in `exp0007/run_infra_v2.sh`), `run_all.sh` refuses a real start without an existing folder, readiness checks it, and `neo4j_load` passes the path as a positional parameter so a space in it stays one word.
- 2026-11-10 R3: `check_loaded_matches` stops when the sheet-count read fails; `band_check` told a crash from a band failure by the JSON the report writes before it exits (exit 1 alone means both); `mv`/`cp` inside `once()` (`infra_footprint`, `assemble_roots`) are checked.
- 2026-11-10 R3: composition bands are judged pooled per scale (`composition --pool`): M0 over the dev plants (scale 100: seeds 1 and 211; scale 1000: seed 1, a pool of one) and, new, M4 over the sealed plants as a report only (not a gate: the freeze is done, a failed band is noted, not a U4 stop; your call whether it should stop).
- 2026-11-10 R3: pilot cap wording $1.50 -> $2.50 in `PREREG_A.template.md`, README and `m2b_pilot.sh`; `.gitattributes` holds `src/plantgraph/qa/audit/*.txt text eol=lf` (the judge prompt was already LF in the working tree).
- 2026-11-10 R3: readiness reports a leftover `e7tune` as `[INFO]` (M0 drops it), and checks `E9_NEO4J_HOME`.
- 2026-11-10 R3: audit ledger gap closed: with `RunContext.calls_log_path` set, error attempts the client discarded before a successful judge call (lines `error_kind` provider_error with a billed response in the judge's `calls.jsonl`, read from the byte mark taken before the call) are booked as `<row>|discarded attempts`; a final failure still books `ProviderError.paid_usd`, so nothing is counted twice.
- 2026-11-10 R3: found by the smoke: the harness reserves one question's cost per item in flight, so a cap below about 4 questions' cost stops even a pure replay (it stopped `E2E-AG-...-d2`, cost 0.00266, at the 0.01 floor); `caps.run_cap_usd` now floors the cap at `RESERVED_QUESTIONS` = 5 questions' cost (the 5 x 0.02172 for ContextRAG H10 also covers what was already a latent problem).
- 2026-11-10 R3: M2b no longer lists `audit/ledger.jsonl` among its outputs (M10a appends to it, so `--from M10a` or later saw M2b as not done).
- 2026-11-10 R3: smoke results: the full `run_all.sh --smoke` ran M0 to M10b and ended with `SMOKE PASSED` (zero real calls); forced band, g1, g2 and cap each stopped with `state/STOPPED` and a resume command, and dirty-tree and wrong-head stopped M3. The full run was made before the M2b-outputs edit and the forced dirty-tree/wrong-head runs after it (to M3 only); no full re-run followed.
- 2026-11-11 G2 first pilot (EXP-0008 M2b, real run): the gate printed PASS (defects 1/1, controls 7/7) on 8 of 49 rows and was wrong. Three defects, all fixed before any test plant was measured (the run was stopped in M4 after the 1-sheet ladder plant; nothing was measured on it). (1) `judge.parse_reply` wanted the reply to be the JSON object alone; the pinned judge wrote its working first and the object last in all 48 replies, so 41 were refused. It now reads the last JSON object that holds the three fields. (2) `report.g2_verdict` counted judged rows only; it now counts every row of the pilot set (`g2 --plan`), a row without a verdict as a miss. Recomputed from the 48 stored replies under both fixes: VALVES_ON_PATH defects 1/21, parse defects 7/8, controls 19/20, so G2 fails (8/29 = 28 %). (3) Why the judge missed the valve rows: the routes run through 100 to 490 parts, the 24,000-character excerpt left out hundreds of them and gave no order, so the judge could not follow the route and fell back on the reference. Registered failure path taken (revise what the judge reads, new part A, re-pilot on the old rows only): `scripts/audit_export_subgraphs.py` writes out the routes of a VALVES_ON_PATH question (`anchor_routes`: the route with the fewest parts of any kind, and the route with the fewest items, fittings not counted; when item-level routes tie but differ in valves, the fewest-valves and the most-valves one), and `excerpt.render_excerpt` prints them first, one tagged part a line under unit headings; the routes must fit, the parts and connections fill the rest. The judge prompt file and pin are unchanged (same hashes). Limit to state in the thesis: for this family the judge checks the count along the routes it is given and whether the readings differ; it does not find the routes itself.
- 2026-11-11 G2 pilot set corrected: `pilot.build_pilot_set` took every wrong VALVES_ON_PATH row of the named questions (21 rows). In 5 of them the system's answer is wrong under every reading ("not present" four times, 38 where the item-level counts are 41 and 42), so they are not scorer defects and no sound judge accepts them. A row is now a defect only if the system's count is one of the question's item-level counts; `inputs/pilot/valves_counts.txt` (replacing `valves_ids.txt`) lists them, taken from the exported fewest-items routes, and they equal the F2 recompute. The set is 16 valves defects (the number the pilot module's docstring already named), 8 parse defects, 20 controls: 44 rows. One control (H1000g2 FLOW_PATH GTV-61003|GTV-177004, 1,108 evidence parts) still cannot fit an excerpt and now counts as a miss, so the controls can reach 19/20 at most. Cache-only dry run after the fixes: 27 rows served from the first pilot's cache (parse 7/8, controls 19/20), 16 valve rows are new prompts (about 25,700 characters each, worst case $0.70 in all, pilot spend so far $0.99 of $2.50). G2 then needs 13 of the 16 valve rows judged correct or ambiguous_question.
- 2026-11-11 Launcher note: `run_all.sh --from <stage>` reruns the stage but keeps its `state/steps/<stage>_*.ok` markers, so a rerun of M2b after changed inputs needs `state/steps/M2b_*.ok` removed by hand first.
- 2026-11-13 M6b, one run re-measured after the machine slept during it: `S7F1-AG-H1000g21p3` (F1 agent tier, third 1,000-sheet plant) ran while the laptop slept twice for a few seconds (11:04:36 to 11:06:41 UTC, after a power source change). The run finished with 280 answered rows, but its replay differed in one row and the launcher stopped (M6b STOP, infrastructure): the answer call of `H1000g21p3:UPSTREAM_ISOLATION:E-26104` spanned the sleep and was stored with a latency of 167 s, above the 120 s question deadline, so the replay records TIMED_OUT where the live run recorded an answer. Six more calls of the same two minutes carry stretched latencies (40 to 78 s). No call failed. Decision (user, in the chat): re-measure the whole run cleanly, no correction of single rows. Done by hand, no frozen file touched: the first attempt (run, replay, dry-run files, logs, the stop file, a copy of the cache as it was) is kept under `data/runs/exp0008/m6b/superseded/S7F1-AG-H1000g21p3_sleep_20261113/` and its `calls.jsonl` still counts in the spend ledger; the run's 1,313 paid replies were deleted from `m6b/cache.sqlite` (14,741 to 13,428 rows) so the rerun calls the model again; the launcher was restarted with no arguments at 15:05 UTC. No other paid run overlapped a sleep: the sleeps of 2026-11-12 (17:16 and 18:24 to 19:27 UTC) fell on a replay and on a free dry run. To state with the results: this run is a second measurement, the first is superseded.
- 2026-11-13 The re-measurement of `S7F1-AG-H1000g21p3` was itself interrupted: it started at 15:14 UTC and its processes were ended by hand by mistake at about 15:38 UTC, with 203 of 280 rows written (no stop file, no sleep). The launcher was restarted with no arguments at 15:40 UTC; the harness resumes the run and measures the remaining rows. The 203 written rows are kept as measured.
- 2026-11-15 M8b, per-run spend caps overridden by hand (user's order in the chat, 2026-11-15): `E2E-CYP-H1000g21p1V-d2` reached its cap at 14:41 UTC on 2026-11-14 with 149 of 280 rows and could not finish by restarting. Cause: the cap is misses x the cost key x 1.5 (key `cyp-d2` = $0.00034 a question, from the first P4 measurement), but the 23 paid calls of the first attempt cost $0.0009 on average and one question cost $0.00344; the harness reserves the dearest question seen for each of the 4 items in flight, cached ones included, so the new allowance of every restart covered two or three reservations. 23 restarts between 20:05 UTC on 11-14 and 06:25 UTC on 11-15 moved the run from 149 to 238 rows (3 or 4 rows each, mostly cached). No frozen file was changed. From 06:39 UTC on 11-15 a supervisor script outside the repository runs the launcher and, when it stops on an M8b run cap, finishes that run with the launcher's own harness command (same strategy, parameters, pin, corpora, questions, cache, cost key, concurrency 4, deadline 120 s) and only `--max-spend-usd` raised ($1.00 for a Cypher run, $3.00 for an agent run), then starts the launcher again; each override is a line in `data/runs/exp0008/logs/manual_cap_overrides.log`. The $30 runs ledger and the step ceiling still apply, since the launcher reads the real spend from `calls.jsonl` before every run. To state with the results: a deviation from the registered per-run cap rule, a money guard only; answers, prompts and scoring are untouched.
- 2026-11-15 M8b, one replay repeated after it ran on battery: `E2E-CYP-H1000g21p1V-d2` finished at 06:55 UTC (override above) and the launcher accepted it at 07:52 UTC. Its cache-only replay `INF-E2E-CYP-H1000g21p1V-d2` (07:52 to 08:25 UTC, 189 rows, then a cache miss) differed in two rows and the launcher stopped (M8b STOP, infrastructure): for `H1000g21p1:DOWNSTREAM_IN_UNIT:E-29201|292` and `...:D-40601|406` the first Cypher query answered in 15.1 s and 13.5 s of server time in the run, and ran into the 30 s transaction limit in the replay, so the replay took the repair path and wrote another answer. The laptop had been on battery since about 06:45 UTC (the run's last rows were written at 06:55, the replay ran wholly on battery); the slower machine is the likely cause, not shown beyond the two timings. Decision (user, in the chat): repeat the replay only, on mains power. Done by hand, no frozen file touched: the first replay, its log and the stop file are kept under `data/runs/exp0008/m8b/superseded/INF-E2E-CYP-H1000g21p1V-d2_battery_20261115/`; `state/steps/M8b_load_H1000g21p1V_d2.ok` was removed so the launcher loads the d2 plant again before the replay (the local Neo4j held another project's data in between, by the user's choice; every launcher load recreates the database). The run's rows are unchanged.
- 2026-11-15 M8b, one run re-measured after it ran on battery: `E2E-CYP-H1000g21p1V-d4` (Cypher tier, first 1,000-sheet plant, arm d4) ran from 12:40 to 13:07 UTC wholly on battery (the laptop was unplugged from about 12:25 to 13:08 UTC). Its replay (13:07 to 13:43 UTC, on mains, 193 rows, then a cache miss) differed in seven rows and the launcher stopped (M8b STOP, infrastructure): seven UPSTREAM_SOURCES questions (P-14201A, P-51101B, TK-35002, TK-34402, TK-103, P-101A, R-401) ended as RETRIEVAL_ERROR in the run, both the first and the repaired query at the 30 s transaction limit, and were answered correctly in the replay with 9.3 to 10.4 s of server time. So the machine on battery was about three times slower and the run lost questions to the limit that the system answers on mains; 49 of the run's 280 rows hold a timed-out attempt. Decision (user, in the chat, as on 2026-11-13): re-measure the whole run on mains, no correction of single rows. Done by hand, no frozen file touched: the run, its replay, logs, the dry-run miss list, the `.complete` marker and the stop file are kept under `data/runs/exp0008/m8b/superseded/E2E-CYP-H1000g21p1V-d4_battery_20261115/` (its `calls.jsonl` still counts in the spend ledger); `state/steps/M8b_load_H1000g21p1V_d4.ok` was removed so the plant is loaded again (the machine was restarted in between). The cache was left as it is: its key is the full prompt, so a reply paid for on a timed-out context is only reused for that same context. To state with the results: this run is a second measurement, the first is superseded; the machine must be on mains for every Cypher-tier run and replay.
- 2026-11-16 M8b, replay of the re-measured `E2E-CYP-H1000g21p1V-d4` repeated: the re-measurement on mains (15 November, 19:22 to 19:47 UTC, 280 rows; a cap stop at 19:38 was finished by the supervisor) was replayed in full (280 rows, 20:36 to 21:18 UTC, on mains) and differed in one row, so the launcher stopped (M8b STOP, infrastructure). `H1000g21p1:CROSS_UNIT:CROSS_UNIT_P1:510`: the first query timed out in both; the repaired query answered after 27.3 s of server time in the run (outcome PARSE_FAILURE) and ran into the 30 s transaction limit in the replay (RETRIEVAL_ERROR). The row is wrong in both, so no score depends on it; it is the near-limit case of ADR-0062, which the launcher's prefix rule does not cover. The stop stood unattended from 21:18 UTC to 06:55 UTC. Remedy as on the morning of 15 November (user's choice then, "continue" now): the replay only is repeated; the first replay, its log and the stop file are kept under `data/runs/exp0008/m8b/superseded/INF-E2E-CYP-H1000g21p1V-d4_limit_20261115/`, and the load marker was removed so the plant is loaded again first. The run's rows are unchanged.
- 2026-11-16 M8b, the repeated replay of `E2E-CYP-H1000g21p1V-d4` passed (07:46 UTC, `prefix_equal: 280 of 280 rows`), and the agent run of that round and its replay followed (identical). Standing rule for the rest of M8b (user, in the chat, 2026-11-16, after the unattended stop of the night): when a Cypher replay differs from its run only in near-limit rows and the machine is on mains, the replay is repeated once without asking; if the repeat again differs in near-limit rows only, the replay is accepted by hand (its `.replayed` marker is written by the supervisor) and the run goes on. A row is near-limit when one side holds a query that hit the 30 s transaction limit and the other side spent at least 20 s of server time on the same question (the 20 s is my threshold: it admits the 27.3 s case above and rejects the two battery cases of 15 November, 9.3 to 15.1 s). Every other difference still stops the run for the user. The supervisor (second version, outside the repository) applies the rule and writes each case, with the question ids, to `data/runs/exp0008/logs/manual_cap_overrides.log`; each superseded replay is kept under `m8b/superseded/`. To state with the results: an accepted replay is a deviation from the registered identity gate; the measured rows stay as measured, and the accepted rows are listed.
