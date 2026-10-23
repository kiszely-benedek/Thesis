---
component: per-question routing across method (cypher_rag_plant / hierarchical_need_rules_plant), effort (low / default) and model (GLM / mimo / Sonnet) — a self-flag cascade evaluated offline by joining fixed runs
status: draft — awaiting review
related: [ADR-0046 (proposed); ADR-0042 (accepted, superseded in part by 0046); ADR-0037, ADR-0033, ADR-0034, ADR-0035, ADR-0036, ADR-0039; plant-graph-first-and-effort-routing.md Part D, §8–§11]
date: 2026-10-04
author: architect (Opus 5.5)
replaces: plant-graph-first-and-effort-routing.md Part D (D.2–D.4) and task ER-T1 in its §8. Parts A–C and E of that note are unchanged.
---

# Design — the method-and-effort cascade (replaces Part D / ER-T1)

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | Routed arm | **`cascade_v1`**, label-free: tier 1 `cypher_rag_plant` @ glm-low; accept iff the answer is ANSWERED, the query returned ≥ 1 row and the answer does not abstain. Else tier 2 `hierarchical_need_rules_plant` @ glm-default; accept iff ANSWERED (no runaway). Else tier 3 (`need_rules_plant` @ mimo or @ glm-low, chosen on dev by rule S1). Else the tier-1 answer if there is one. |
| R2 | Effort | fixed **per tier**, not decided per question: low for tier 1 (query writing), default for tier 2; low effort survives as a tier-3 candidate (runaway remedy) |
| R3 | Model | GLM for tiers 1–2; mimo-v2.6-pro or glm-low as tier 3, decided by rule S1 on the dev runaway set; Sonnet not in the cascade (optional reference only) |
| R4 | Evaluation | offline join of fixed runs (ADR-0037/0042 principle), per question, gap refusal; no live per-question pins in the harness |
| R5 | Overfitting guard | candidate set and selection rules S1–S3 fixed **in this note, before** any new paid call; D100 selects, D1000 confirms, then F1 freeze, then the sealed test run |
| R6 | Claims | K1 (cascade ≥ always-N accuracy at lower cost and latency) and K2 (self-flags beat random escalation) replace ADR-0042's E1/E2 before any test data exist |

Coder tasks: 3 now (CR-T1…T3) + 1 at the freeze (CR-T4), one Sonnet coder at a time, all offline. Paid dev steps:
≈ $0.56 recommended (caps total $0.95), Sonnet optional (+$1.19, cap $1.80). ADR: ADR-0046 (proposed).

## 1. What the new evidence says

| # | Finding | Source |
|---|---|---|
| E1 | `hierarchical_need_rules_plant` @ glm-default: D100 157/180, D1000 151/180. Non-runaway wrong answers are rare: correct among answered 157/165, 151/160 | `_results.md` DEV10 |
| E2 | Its failures are mostly **runaways**: 15 (D100) and 20 (D1000) PARSE_FAILUREs, all at 16,384 completion tokens except one (10,730, D1000). Runaway labels: PATH 7/9, UPSTREAM_TO_FIRST_VALVE 5/3, UPSTREAM_ALL 3/5, DOWNSTREAM_ALL 0/3 (D100/D1000). A runaway costs on average $0.0106 (D100) / $0.0105 (D1000) and takes 166 s / 245 s | `DEV10-D100`, `DEV10-D1000` `answers.jsonl` (computed) |
| E3 | Neither a lower output cap nor a timeout separates runaways cheaply: correct answers use up to 15,998 (D100) / 15,663 (D1000) completion tokens, 24 / 23 correct answers use > 4,096; the slowest answered question took 137 s (D100) while the fastest runaway took 133 s | same files (computed) |
| E4 | `cypher_rag_plant` @ glm-low on D100: 141/180, median 1.5 s. **Its total cost is $0.0420, not $0.0127**: the PG-P1b row counts only the final call; the query-writing call (`retrieval_usage`, $0.0293) is missing. Against need_rules' total $0.4692 that is ≈ 11× cheaper, not ≈ 36× | `CYP-D100-low/answers.jsonl`, `cost_usd` + `retrieval_usage.cost_usd` (computed) |
| E5 | The same omission affects DEV10: totals with retrieval calls are $0.4692 (D100, row says $0.459) and **$0.5802 (D1000, row says $0.484)**; the difference at D1000 is six unit-router calls ($0.097) on `no_anchor` fallbacks | `DEV10-*/answers.jsonl` (computed) |
| E6 | Cypher's **self-signal is informative**: of 180, 125 answers are "clean" (ANSWERED, ≥ 1 row, not abstaining) and 118 of them are correct (precision 0.944). The other 55 (6 RETRIEVAL_ERROR, 47 empty result, 35 abstaining; overlapping) are correct only 23 times, while need_rules gets 45 of those 55 right | `CYP-D100-low` × `DEV10-D100` join (computed) |
| E7 | Clean-but-wrong Cypher answers: 5 UPSTREAM_ISOLATION (need label UPSTREAM_TO_FIRST_VALVE), 2 LOOPS_NEAR_ITEM (GENERIC). No self-signal catches them | same join |
| E8 | On every escalated question that need_rules answered (no runaway), it was correct (45/45); the 10 escalated failures are all runaways | same join |
| E9 | mimo-v2.6-pro: 34/36 vs GLM 32/36, 0 runaways, ≈ 2.7× GLM's cost on the same 36. Three of the 15 D100 runaways are in the 36: mimo 2/3 correct, costs $0.021, $0.008, $0.013 | `_results.md` MIMO36; `MIMO36-D100/answers.jsonl` |
| E10 | Effort low vs default on `need_rules_plant` was measured only on the H100 test-corpus slice: 24/36 vs 33/36, $0.072 vs $0.103 — low saves ≈ 30 % (contexts are input-dominated) and loses 9 questions | `_results.md` PG-P1 (anecdotal, test corpus, not reported) |
| E11 | The two D100 runs are on the same plant: equal `source_graph_hash` (`5f2624e9…`), `question_set_sha256` (`4564f6f7…`), prompt hashes and primer flag; they differ only in the store profile (`n_store_nodes`) and the pin | `corpora.json`, `run_config.json` of both runs |

**Consequence.** ADR-0042's primary lever — choose glm-low vs glm-default for the *same* method before answering —
has little to win: on `need_rules_plant`, low effort saves about a third of the cost and loses accuracy (E10), and
it is unmeasured on the dev corpora. The large, measured cost and latency lever is the **method**: a structured
query is ≈ 11× cheaper and ≈ 5× faster, and it says when it has failed (E6). Effort and model become fixed
properties of each tier, with one exception: runaways (E2) need their own remedy, and that is where low effort and
the mid-tier model compete (tier 3).

## 2. Which part of the claim it serves

The thesis claim is that the best retrieval strategy depends on corpus scale. The cascade turns that into one
measurable quantity per corpus: **the share of questions a cheap structured query settles on its own** (tier-1
acceptance), and the accuracy of what it accepts. Both are reported per corpus (D100/D1000 now; H100/H1000 at test)
and per reach bin `k`. The D100 data already point in that direction: on long-reach questions (k ≥ 3) Cypher
scores 34/39 and need_rules 28/39, at k = 0 it is 44/68 vs 66/68 (§6). Whether that gap grows at H1000 is exactly
the scale question; the cascade is the deployable consequence of it.

## 3. Signals a policy may read

| Allowed (before or during answering) | Where it comes from |
|---|---|
| rules need label | `RuleNeedClassifier` on the question text and its anchors (free, deterministic; equals the DEV10 trace label) |
| anchor counts, `no_anchor` | `NeedInput.n_tag_anchors`, `n_unit_anchors` |
| tier outcome | `QuestionResult.outcome` (ANSWERED, PARSE_FAILURE, RETRIEVAL_ERROR, DID_NOT_FIT, …) |
| Cypher rows | `trace.retrieval.n_rows`, `empty_result`, `cypher_error` |
| abstention | `final_answer.not_present` |
| runaway | outcome PARSE_FAILURE **or** `completion_tokens ≥ pin.max_output_tokens` |
| cost, latency | `cost_usd + retrieval_usage.cost_usd`, `latency_s` |

| Forbidden (gold) | Why |
|---|---|
| `correct`, `f1`, `reference`, `family`, `k`, `u`, `evidence_*`, `answerable` | known only to the scorer; reading them is the oracle |

The structural guard: the policy receives a `Signals` object that has no gold field; gold is read only in
`evaluate.py`, and a metamorphic test flips every `correct` in the input rows and asserts the decisions are
byte-identical (§8, CR-T2).

Abstention as a flag has a cost: 20 of the 180 questions are unanswerable, and an abstaining Cypher answer to them
is correct (18/20 on D100). Escalating them costs a tier-2 call but no accuracy (need_rules 15/20, and the tier-1
answer remains the fallback only on runaway). Kept label-free on purpose: a rule "trust an empty result on PATH
questions" would be tuned to the benchmark's NO_PATH family.

## 4. The policy and its data model

### 4.1 `cascade_v1`

```
tier 1  cypher_rag_plant           glm-5.3-flash, effort low      accept: ANSWERED ∧ rows > 0 ∧ ¬not_present
tier 2  hierarchical_need_rules_plant glm-5.3-flash, default      accept: ANSWERED
tier 3  hierarchical_need_rules_plant T3 ∈ {mimo-v2.6-pro, glm-low} accept: ANSWERED     (T3 fixed by rule S1)
final   the tier-1 answer if tier 1 was ANSWERED, else the question fails (outcome of the last tier)
```
Cost of a question = sum over tiers tried; latency = sum (sequential). The variants of §5 differ only in the start
tier per need label or in which tiers exist.

### 4.2 Pydantic models — `src/plantgraph/qa/cascade/models.py` (new package)

```python
class AcceptRule(StrEnum):
    ANSWERED = "answered"            # outcome is ANSWERED (so: no runaway, no parse or retrieval error)
    ROWS = "rows"                    # trace.retrieval.n_rows > 0 (Cypher tiers only)
    NOT_ABSTAINED = "not_abstained"  # final_answer.not_present is False

class TierSpec(BaseModel):           # frozen
    name: str                        # "cypher-low", "need-default", "need-mimo", "need-low"
    strategy: str                    # registry name
    pin_sha256: str                  # hash of the run_config answer_pin; the join checks it
    accept: frozenset[AcceptRule]

class CascadePolicy(BaseModel):      # frozen; one JSON file per policy under qa/cascade/policies/
    name: str                        # "cascade_v1"
    tiers: tuple[TierSpec, ...]
    fallback_to_first_answer: bool = True
    start_tier_by_label: dict[NeedLabel, int] = {}   # variants only; label-free policies leave it empty

class Signals(BaseModel):            # frozen; everything a policy may read — no gold field by construction
    question_id: str
    tier: str
    outcome: Outcome
    n_rows: int | None
    not_present: bool | None
    runaway: bool
    cost_usd: float                  # final + retrieval calls
    latency_s: float
    need_label: NeedLabel

class Decision(BaseModel):           # frozen; output of the policy, input of evaluate
    policy: str
    question_id: str
    tiers_tried: tuple[str, ...]
    answered_by: str | None          # tier whose answer is final (fallback → the tier-1 name)
    cost_usd: float
    latency_s: float
```

### 4.3 Join and offline condition — `qa/cascade/join.py`

- Input: one run directory per (tier, corpus); `run_config.json`, `corpora.json`, `answers.jsonl`; the question
  file of the corpus (read for ids and text only; gold columns are dropped before `Signals` are built).
- Checks per tier against tier 1 (refuse on any mismatch, naming the field): `source_graph_hash` per corpus,
  per-question sha256 of the question row's `question_id` + `text` (so subset runs join by question, not by set
  hash), `primer`, the hashes of the shared prompt files (`final_answer.txt`, `legend_plant.txt`,
  `primer_pid_v1.txt`), `repeat == 0`, and `pin_sha256` equal to the tier spec.
- Gap refusal: for each policy, the questions that reach a tier with no row there are listed with the exact harness
  command (subset questions root, pin file, cap) — never filled silently.
- `needed` sub-command: writes `data/runs/<root>/qsub/<tier>/<corpus>/questions.jsonl` with the **union over the
  registered candidate policies** of the questions that reach `<tier>`, chosen from signals only. This is how the
  tier-3 paid runs get their question set.

### 4.4 Evaluate and report — `qa/cascade/evaluate.py`, `report.py`, `stats.py`

- `evaluate.py` attaches `correct` from the answering tier's row. References (computed here, never deployable):
  always-<tier>, **random escalation** at the policy's own tier-2 share (1,000 seeded draws, same downstream rules),
  **oracle cascade** (escalate exactly the gold-wrong tier-1 answers; upper bound).
- `stats.py`: paired bootstrap over questions (5,000 resamples, fixed seed) for accuracy, cost per question and
  latency per question, policy vs reference.
- `report.py` (CLI `python -m plantgraph.qa.cascade report …`): per corpus, one row per policy — correct, total
  cost, cost per question, latency median / mean / p90, share answered by each tier, tier-1 acceptance precision;
  then per need label, per family and per k-bin (family and k come from the question file, evaluation only); then the
  S1–S3 verdicts printed PASS/FAIL against §7's thresholds.

### 4.5 How the component reports its own accuracy

Against gold, per corpus: policy accuracy with paired CIs vs always-N and vs random escalation; the decider's
quality as tier-1 acceptance precision and recall of "tier 1 correct" (and AUROC once a scored decider such as Jev
exists); residual errors split into accepted-but-wrong (signal blind spot) and runaway-unrecovered.

## 5. Candidate policies and what is evaluable today

Runs that exist: `DEV10-D100`, `DEV10-D1000` (need @ default), `CYP-D100-low` (cypher @ low, D100 only),
`MIMO36-D100` (need @ mimo, 36 of the D100 questions).

| Policy | D100 offline now | D1000 offline now | Paid step that unlocks the rest |
|---|---|---|---|
| always-N (need @ default) | yes | yes | — |
| always-C (cypher @ low) | yes | no | CP-P1 |
| `cascade_v1` tiers 1–2 (+ tier-1 fallback) | **yes** | no | CP-P1 |
| `cascade_v1_iso` (UPSTREAM_TO_FIRST_VALVE starts at tier 2) | yes | no | CP-P1 |
| `label_router_dev` (per label, the better arm on D100; no cascade) | yes (in-sample) | no | CP-P1 |
| `n_first_v1` (need @ default; runaway → T3 → fail) | no (3 of 15 runaways covered by MIMO36) | no | CP-P2 / CP-P3 |
| `cascade_v1` with tier 3 | no (tier 3 reached by 10 D100 questions, 2 covered) | no | CP-P1 + CP-P2 / CP-P3 |
| any policy with need @ low as tier 2 | no | no | a full need @ low run per corpus (≈ $0.36 each, estimate; not proposed) |
| Sonnet anywhere | no | no | CP-P4 (optional) |
| Jev pre-router ("skip tier 1") | no | no | J-T1 + decisions (cents); after F1 decisions, not now |

## 6. Offline numbers on D100 (computed 2026-10-04 by the architect; not reported — dev corpus)

Source for every row: per-question join of `data/runs/cv1/runs/DEV10-D100/answers.jsonl` and
`data/runs/cv1/runs/CYP-D100-low/answers.jsonl` (180 questions each, same ids), questions from
`data/runs/cv1/questions/D100/questions.jsonl`. Cost = `cost_usd + retrieval_usage.cost_usd`; latency =
`latency_s`, summed over tiers tried. Scratch script, not in the repo; CR-T2/T3 reproduce these as their acceptance
check.

| Policy | Correct /180 | Total $ | Median s | Mean s | p90 s | need calls |
|---|---|---|---|---|---|---|
| always-N | 157 | 0.4692 | 7.8 | 34.9 | 121.5 | 180 |
| always-C | 141 | 0.0420 | 1.5 | 3.3 | 6.0 | 0 |
| N; runaway → C answer | 165 | 0.4736 | 7.8 | 35.2 | 121.5 | 180 |
| C; escalate on RETRIEVAL_ERROR only | 144 | 0.0904 | 1.6 | 7.9 | 7.3 | 6 |
| C; escalate on error ∨ abstain | 156 (160 with fallback) | 0.2080 | 2.0 | 16.3 | 24.7 | 41 |
| C; escalate on error ∨ empty | 163 (166 with fallback) | 0.2316 | 2.1 | 18.2 | 50.5 | 53 |
| **`cascade_v1` tiers 1–2** (error ∨ empty ∨ abstain), no fallback | 163 | 0.2425 | 2.3 | 19.2 | 52.0 | 55 |
| **`cascade_v1` tiers 1–2 + tier-1 fallback** | **167** | **0.2425** | **2.3** | **19.2** | **52.0** | 55 |
| `cascade_v1_iso` + fallback (label chosen on D100) | 170 | 0.2683 | 2.4 | 21.1 | 71.9 | 60 |
| `label_router_dev` (9 per-label choices made on these 180) | 167 (in-sample) | 0.1458 | — | — | — | 50 |
| random escalation, same 55 (1,000 draws) | mean 145.8, 95 % range 139–152 | — | — | — | — | 55 |
| oracle cascade C → N (gold; upper bound) | 172 | 0.1825 | 1.8 | 15.7 | 16.2 | 39 |

Paired bootstrap, `cascade_v1` (+ fallback) − always-N, 5,000 resamples, seed 1: accuracy **+0.056 [+0.006,
+0.106]**; cost per question **−$0.00126 [−$0.00161, −$0.00093]** (≈ −52 %); latency per question **−15.6 s
[−20.8, −10.9]**.

By reach (answerable questions; `cascade_v1` + fallback / always-N / always-C): k = 0 65 / 66 / 44 of 68;
k 1–2 46 / 48 / 45 of 53; k ≥ 3 **37 / 28 / 34** of 39; unanswerable 19 / 15 / 18 of 20.

Residual errors of `cascade_v1` + fallback (13): 7 accepted-but-wrong Cypher answers (5 UPSTREAM_ISOLATION,
2 LOOPS_NEAR_ITEM) and 6 runaways whose tier-1 fallback is also wrong — the second group is what tier 3 is for.

**Caveats.** One corpus, one repeat, 10 questions per family; D100 is the corpus on which `cascade_v1`'s flags were
*inspected* (they were not tuned — the rule is the plain "accept only a non-empty, non-abstaining answer" — but the
iso variant and the label router were chosen from these rows). The efforts of the two tiers differ by design. The
D100 Cypher run was on the uncommitted MP-T4 code. The k ≥ 3 advantage rests on 39 questions.

## 7. Overfitting guard and validation protocol

Fixed now, in this note, before CP-P1 to CP-P4 run and before anyone reads their results:

1. **Candidate set** = the policies of §5 (no new ones may be added after a dev result is seen without a new ADR,
   and any added one is labelled post hoc).
2. **S1 — tier 3.** T3 = whichever of need @ mimo and need @ glm-low answers more of the pooled dev runaway set
   (the 35 DEV10 runaways on D100 + D1000) correctly; tie → the cheaper (glm-low). Sonnet is not a candidate for T3
   unless the user asks for CP-P4 *and* both candidates answer fewer than half of the 35.
3. **S2 — confirmation on D1000** (second dev corpus; the flags were never inspected there). `cascade_v1` (tiers
   1–2 + fallback) is confirmed if its D1000 accuracy ≥ always-N's − 2 questions **and** its mean cost per question
   is lower. Otherwise the primary becomes `n_first_v1` (need @ default; runaway → T3), and the cascade is reported
   as a negative dev result.
4. **S3 — label variants.** `cascade_v1_iso` and `label_router_dev` are always reported, labelled "dev-tuned on
   D100". Either replaces the primary only if, on D1000, it beats `cascade_v1` by ≥ 2 questions at a cost no higher
   than 1.25× `cascade_v1`'s. (Thresholds are judgement, stated before the data.)
5. **Freeze.** The selected policy file(s) under `qa/cascade/policies/` and `qa/cascade/*.py` join the F1 manifest
   (ADR-0035 point 3) — CR-T4.
6. **Test.** After F1, the sealed held-out families are opened by QAR-T10 as planned; the test fixed runs (H100,
   H1000) per tier are joined by the frozen policy. No dev step reads `heldout-families.sealed.md`. The label-free
   primary passes held-out families through without any family knowledge; a label variant (if S3 selects one)
   inherits whatever labels the rules classifier gives the new families — Q2-style degradation is then reported.

D1000 is a **scale** check, not a **family** check: same 18 families and templates. Family transfer is tested
only by the held-out families at test time; this is stated as a threat.

## 8. Ordered coder tasks (Sonnet, one at a time; each ends green on ruff, mypy --strict, pytest; all offline)

None touches a file in the current working-tree diff (`harness/*`, `qa/strategies/cypher_rag.py`,
`qa/neo4j_view.py`, `qa/schema_text.py`, tests); the package only reads `answers.jsonl` through the existing models.

| # | Task | Depends on | Files | Acceptance | Size (estimate) |
|---|---|---|---|---|---|
| 1 | **CR-T1** models (§4.2), signal extraction (runaway, total cost, need label via `RuleNeedClassifier`), join with every check of §4.3 and gap refusal, `needed` sub-command | the current diff committed (it touches the harness models CR-T1 reads) | `qa/cascade/{__init__,models,signals,join,needed}.py`, `tests/test_cascade_join.py`, toy fixtures `tests/cascade_toy/` | toy runs: refuses on a changed `source_graph_hash`, a changed question text, a different primer, a pin mismatch; lists missing ids with a command; runaway detected both by outcome and by token cap; need label equals the trace label on toy rows | S/M |
| 2 | **CR-T2** policy engine (cascade, start-by-label, always-X), references (random escalation, oracle cascade), paired bootstrap; the five policies of §5 that are D100-evaluable as JSON files under `qa/cascade/policies/` | CR-T1 | `qa/cascade/{policy,evaluate,stats}.py`, `qa/cascade/policies/*.json`, `tests/test_cascade_policy.py` | metamorphic: flipping every `correct` leaves all `Decision`s byte-identical; import ban (`policy.py`, `signals.py` import no `qa.scoring`, `qa.questions`, `harness.gold`); toy cascade cost and latency sums; random reference reproducible by seed. Optional local check (skipped without `data/`): §6's rows reproduce exactly | M |
| 3 | **CR-T3** report CLI: markdown + JSON per corpus, per label / family / k-bin, tier shares, acceptance precision, S1–S3 verdicts | CR-T2 | `qa/cascade/{report,__main__}.py`, `tests/test_cascade_report.py` | golden markdown on the toy runs; S2/S3 verdict logic unit-tested on hand-made numbers | S/M |
| — | *Main session: `report` on D100 (free) → `_results.md` row CASCADE-00; the E4/E5 cost correction as a dated note on the PG-P1b and DEV10 rows* | CR-T3 | — | — | minutes |
| — | ***CP-P1, then CP-P2 / CP-P3** (§9) — **run by the user, paid, logged**; then `report` on D100 + D1000 → S1, S2, S3 verdicts* | CR-T3 | — | — | — |
| 4 | **CR-T4** add `qa/cascade/` and the selected policy files to the F1 manifest | S1–S3 decided | `qa/harness/freeze.py`, its test | manifest test fails on a one-byte policy change | S |
| later | **CR-T5** (could) Jev "skip tier 1" pre-router decider, reported not claimed | J-T1 | `qa/cascade/deciders.py` | AUROC vs "tier 1 accepted and correct" on dev | S |

Queue position: CR-T1 takes ER-T1's slot (#10) in `plant-graph-first-and-effort-routing.md` §8; it no longer waits
for J-T1, and it can move up as soon as the current diff is committed because it collides with nothing else.

## 9. Paid steps (estimates from measured per-question means; each capped at ≈ 1.5 × estimate)

| Step | What | Questions | Estimate | Hard cap | Basis |
|---|---|---|---|---|---|
| CP-P1 | `cypher_rag_plant` @ glm-low on D1000 (DEV10-D1000's 180). Needs Neo4j swapped: wipe D100, load D1000 `--store-profile plant` (one plant in Neo4j) | 180 | $0.042 | $0.10 | $0.0420 / 180 = $0.00023 total per question on D100 (`CYP-D100-low`); the query prompt is schema-only and the context is row-capped, so roughly size-independent |
| CP-P2 | `need_rules_plant` @ mimo on the 35 DEV10 runaways (D100 15, D1000 20); the 3 already in MIMO36 replay from `cache_mimo.sqlite` | 32 paid | $0.45 | $0.70 | mean $0.014 of mimo's three answers to runaway questions (`MIMO36-D100`) × 32 |
| CP-P3 | `need_rules_plant` @ glm-low on the same 35 | 35 | $0.07 | $0.15 | $0.072 / 36 = $0.0020 per question (PG-P1 low, H100 slice); harder questions may cost more, hence the wide cap |
| CP-P4 (optional, not recommended now) | `need_rules_plant` @ Sonnet on the same 35 | 35 | $1.19 | $1.80 | $0.034 per question (PAID-04, occurrence H100) |
| Test (after F1, part of EXP-0006) | per test corpus: tier 1 on all, tier 2 on all (it is also the always-N baseline), tier 3 on tier-2 runaways | e.g. 240 per corpus (24 families × 10) | ≈ $2.2 for H100 + H1000 together, of which ≈ $0.75 beyond the need runs EXP-0006 makes anyway | 1.5 × per step | C $0.00023/q; N $0.0026/q (D100) and $0.0032/q (D1000, with router calls); runaway rate 8–11 % (DEV10) × $0.014 (mimo) |

Order: CP-P1 first (it decides S2). CP-P2 and CP-P3 run regardless of S2, because `n_first_v1` (the fallback
primary) needs tier 3 too. Concurrency 4 as in the DEV10/CYP runs. Read the balance after each step. Recommended dev
spend ≈ $0.56 (caps $0.95) out of ≈ $21.5.

## 10. What happens to ADR-0042 and ER-T1

- ADR-0042 points 2, 3, 4, 7 and 8 are superseded by ADR-0046 (wrapped strategy, primary arm, escalation arm,
  claims, futility stop). Points 1 (configurations as pins), 5 (deciders — now an optional tier-1 skip, CR-T5) and
  6 (offline condition — refined to a per-question join, §4.3) carry over.
- ER-T1 is replaced by CR-T1…T3. The ER-P1…P4 runs of Part D.4 are replaced by CP-P1…P4 (dev) and the test step.
- `merged-plant-layer-and-model-router.md` §B and `plant-graph-first-and-effort-routing.md` Part D get a one-line
  pointer to this note on acceptance (main session), plus `00-index.md` and `40-design/README.md`.

## 11. Open user decisions (recommendation first)

- **U1 — adopt the label-free cascade as the routed arm** (recommended), instead of ADR-0042's per-question effort
  choice. Alternative: keep effort routing (needs ≈ $0.36 per dev corpus for need @ low first, and measured upside is
  small, E10).
- **U2 — tier-3 candidates:** run mimo and glm-low on the 35 dev runaways, CP-P2 + CP-P3 ≈ $0.52, caps $0.85
  (recommended); Sonnet (CP-P4, ≈ $1.19) only if both fail rule S1's half-bar.
- **U3 — tier 2 and the always-N baseline at default effort on the test corpora.** This revises ADR-0042's accepted
  U6 ("fixed runs at low effort everywhere") for this one strategy: the cascade's tier 2 and its comparator must be
  the same configuration, and DEV10/PG-P1 show default effort answers far more (E1, E10). Recommended yes; the
  low-effort fixed runs of the other arms stay as decided.
- **U4 — label variants only under S3** (recommended): reported, never primary unless they win on D1000.
- **U5 — approve CP-P1** ($0.042, cap $0.10) and the Neo4j swap D100 → D1000 (recommended).
- **U6 — the cost correction (E4, E5)** goes into `_results.md` as a dated note on the PG-P1b and DEV10 rows
  (recommended; the rows themselves stay as written).

Open questions (not for the user):
- **O1** Is the empty-result flag as useful at D1000? At larger scale Cypher's `send_to*` paths are longer and the
  30 s timeout may bite — CP-P1 answers it.
- **O2** RETRIEVAL_ERRORs are Cypher syntax errors (6 on D100, e.g. unknown function `indexOf`); one query retry
  with the error message would be a cheaper tier 1.5. Out of scope now (prompt change → F1 file), noted for later.
- **O3** The novelty check owed by ADR-0037/0042 now covers cascades with self-verification (FrugalGPT-style
  cascades are prior work; the defensible point stays the domain and the scale axis) — researcher.

## 12. Figures in this note and their sources

| Figure | Source |
|---|---|
| 157/180, 151/180, 15/20 runaways, correct among answered, latencies, $0.459 / $0.484 as reported | `_results.md` DEV10 |
| 141/180, 1.5 s, $0.0127 as reported; oracle union 172 | `_results.md` PG-P1b |
| 34/36, 32/36, ≈ 2.7×, 0 runaways | `_results.md` MIMO36 |
| 24/36 vs 33/36, $0.072 / $0.103 (need_rules_plant low / default, H100 slice) | `_results.md` PG-P1 |
| $0.034 per Sonnet question | `_results.md` PAID-04 |
| totals with retrieval calls ($0.0420, $0.4692, $0.5802), runaway token, cost and latency profile, E3's token and latency overlap, E6–E8 counts, mimo's three runaway answers, all of §6 | architect scratch computation 2026-10-04 over the four `data/runs/cv1/runs/*/answers.jsonl` files and the D100 / D1000 `questions.jsonl` — **computed, not a `_results.md` row yet** (CASCADE-00 after CR-T3) |
| paid estimates in §9 | arithmetic on the rows above — **estimates** |
