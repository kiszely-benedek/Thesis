---
component: EXP-0001 — the single-sheet end of the claim (ContextRAG vs the cascade along a size ladder, plus the EX01 anchor)
status: accepted with ADR-0054 (user, 2026-10-11); hashed into E.sha256 at commit E
adr: ADR-0054 (proposed)
depends: ADR-0013, ADR-0021, ADR-0022, ADR-0038, ADR-0044 (U3), ADR-0050, ADR-0052, ADR-0053 (F1, T)
code: new files only, under src/plantgraph/qa/exp0001/ (§11); no F1-frozen file changes
data: data/runs/exp0001/ (git-ignored)
---

# EXP-0001 — where does the single-sheet optimum stop being optimal?

## 1. Purpose and link to the claim

The claim has two ends. The plant-scale end is measured (EXP-0002: cascade_v3 0.937 / 0.917 acc@120 at H100 /
H1000, `_results.md` EXP-0002-*). The single-sheet end has no result: no ContextRAG answer exists in the project,
on any model, on any corpus (`_results.md`: PAID-01…04, DEV10, CASCADE-*, EXP-0002 contain no `context_rag` row).

EXP-0001 answers one question:

> On one sheet, does serializing the whole graph into the prompt (ContextRAG, ChatP&ID's optimum) match or beat
> the frozen cascade_v3 and its two tiers on accuracy, cost and latency — and at what corpus size does the
> ordering flip?

Without it, "the published optimum inverts" rests on prompt-size arithmetic alone. With it, the thesis can show
the optimum *and* its loss on the same pipeline, the same model and the same question families.

## 2. What exists, what is missing (verified 2026-10-11)

| Fact | Source |
|---|---|
| `context_rag` strategy: serializes the occurrence graph (GraphML, visible properties, ADR-0022 S1), no retrieval, one final call | `src/plantgraph/qa/strategies/context_rag.py`, `qa/serialize.py`, `qa/final_answer.py` |
| ContextRAG prompt: EX01 18,461 chars; H100 1,649,451; H1000 16,747,117 (≈ 16.3k chars per generated sheet + 768 template) | `_results.md` PROMPT-04 |
| Luna (`openai/gpt-6-luna`, host `openai`): context 1,050,000, **max prompt tokens 922,000**; $0.10 / $0.50 per M in/out, **$0.20 / $0.75 above 272,000 prompt tokens** | `30-experiments/openrouter-endpoints-2026-10-10.json`, `openrouter-models-2026-10-10.json` |
| GPT-5-mini (ChatP&ID's model) listed: 400,000 context, $0.25 / $2.00 per M | `openrouter-models-2026-10-10.json` |
| Measured $/question, Luna tiers (sealed): always_c_luna $0.00043, always_g_luna $0.00066–0.00074, cascade_v3 $0.00065–0.00071 | `EXP-0002-sealed-test.md` |
| EX01 imports to 36 nodes / 39 edges, context 17,693 chars | architect probe 2026-10-11 (scratch, no network), equals PROMPT-03 |
| EX01's loop tags `HV4750.01`, `PV4712.02`, `TV4750.03` sit on `ActuatingFunction` nodes; the three globe valves are tagged `C1` (component number, repeated 5× on the sheet) | same probe; the XML holds `PV4712.02` ×5 and no `TV4712.02` |
| ChatP&ID's 19 questions transcribed; **5 scored** (CP11–CP15, path exploration), 14 out of scope (ADR-0021) | `data/external/chatpid_ex01_qa.jsonl`, `qa/chatpid_qa.py` |
| Harness refuses a Proteus corpus (needs a gold plant and split manifest) | `qa/harness/runner.py:_load_corpus`, `qa/harness/corpus_record.py` |
| `run_unscored` answers one item without gold (the live cascade uses it) | `qa/harness/attempt.py` |
| `sealed_set` builds all 24 families on any `H\d+` corpus; `per_family` subsamples | `qa/questions/sealed_set.py`, `qa/questions/per_family.py` |
| Headline preset: 1–2 sheets per unit, 18–36 equipment per unit, budget 18; a one-sheet unit is rare (1 of 51, 17 of 509 units) | `ingest/headline.py`, `_results.md` SMOKE-07 |
| No LLM judge exists (QA-T16 never built) | `grep judge src/` → only cascade report names |
| HEAD = T (`4ffd87e`); F1→HEAD `src` diff = question-side files only | `git diff --name-only 07d4029 HEAD -- src` |

**Correction this design surfaces.** ADR-0053 decision 2 and the sealed report (row R2, D7) say ContextRAG is
`DID_NOT_FIT` at H100. On Luna that is very likely false: 1,649,451 chars fit in 922,000 tokens at any ratio
above 1.79 chars per token, and GraphML runs at roughly 2.5–3.5 (estimate, not measured). H100 was **not run by
choice** (ADR-0038); only H1000 does not fit (it would need ≥ 18.1 chars per token). EXP-0001 measures the ratio
and settles the wording (claim X5).

## 3. Substrates — both, with different jobs

### 3.1 The size ladder (carries the claim)

Fresh synthetic corpora from the **same headline preset** as D100/H100/H1000, so the size axis is continuous with
EXP-0002 and only size changes.

| Id | Target sheets | Seed | How chosen | Expected sheets / occurrence nodes | ContextRAG prompt (est.) |
|---|---|---|---|---|---|
| H1 | 1 | first seed in 100…399 whose one-unit corpus has **exactly 1 sheet** | seed scan (§9.1), selection on sheet count only | 1 / ~40 | ~17k chars |
| H3 | 3 | 3 | headline size search | 3–4 / ~150 | ~66k |
| H10 | 10 | 3 | same | 10–11 / ~440 | ~180k |
| H30 | 30 | 3 | same | 30–31 / ~1,250 | ~506k |
| H100 | — | 2 (the sealed corpus) | **conditional** stage C (§7, X3) | 100 / 4,059 | 1,649,451 (measured) |
| H1000 | — | 0 (sealed) | **no call**: arithmetic (X5) | 1,001 / 40,532 | 16,747,117 (measured) |

- Points are roughly ×3 apart, so they sit evenly on a log axis. H30 keeps the prompt under the 272k-token price
  step at ≥ 2.5 chars per token.
- The `H` prefix is required by `sealed_set` (`H\d+`), and is accurate: these corpora were never used in
  development. The thesis calls them "H1 … H30, EXP-0001 ladder".
- One plant per size. H1 is a minimum-size unit (18 equipment) by construction of the scan — stated as a threat.
- Seed 3 and the scan range 100…399 are not used by any earlier corpus (D 1, H100 2, H1000 0, X1000 77).

### 3.2 EX01 (the reproduction anchor; descriptive only)

`data/external/C01V04-VER.EX01.xml` (very likely ChatP&ID's `DEXPIEX01.xml`, ADR-0009 outcome log), imported
**as is** (ADR-0054 point 7), with ChatP&ID's 5 scored questions in their own words. n = 5, so EX01 gives a
qualitative anchor ("on their file, with their questions, does ContextRAG answer, and at what cost and speed?"),
never a claim.

## 4. Arms

All Luna arms use the sealed pins byte-for-byte (copied from `data/runs/sealed/inputs/`).

| Arm | Strategy | Pin (hash) | Where | Notes |
|---|---|---|---|---|
| **ctx-high** | `context_rag` | `pin_agent_luna_final_high.json` → effort high (`ffc026d3…`) | EX01, H1–H30, (H100) | ContextRAG at its strongest reasonable setting; its one call is the whole work |
| ctx-low | `context_rag` | `pin_cypher_luna_low.json` → effort low (`acf24178…`) | EX01, H1, H10 | effort sensitivity |
| ctx-gpt5mini | `context_rag` | new `pin_ctx_gpt5mini.json`: `openai/gpt-5-mini`, host `openai`, no fallbacks, temperature null, seed 0, 16,384 output tokens, no effort field | EX01 only | ChatP&ID's model on ChatP&ID's file |
| cyp (= always_c_luna) | `cypher_rag_plant` | `acf24178…`, params `{"timeout_s": 30, "row_cap": 200}` | EX01, H1–H30 | frozen tier 1 |
| ag (= always_g_luna) | `graph_agent_low_steps` | `ffc026d3…`, params `{"max_steps": 40}` | EX01, H1–H30 | frozen tier 2 |
| **cascade_v3** | offline join of cyp + ag | policy file at F1 | everywhere | the thesis's system; no extra calls |

- Primer on for every arm (harness default, as in EXP-0002). ChatP&ID had none: a stated difference.
- Policy files for the ctx arms are data, not code: `data/runs/exp0001/inputs/always_ctx_high.json` and
  `always_ctx_low.json`, one tier each (`strategy: context_rag`, the pin hash above, `accept: ["answered"]`).
- Deadline: 120 s for cyp/ag (as sealed); **300 s for ctx** so its uncut latency is observed. acc@120 is applied
  offline by the report's cutoff, so the metric is the same for every arm.
- Concurrency 4 (as sealed); 2 at H100.

## 5. Questions

**Ladder.** Per corpus, with the commands frozen at T (no new generator code):

```
sealed_set --corpus-id HN --ingest-json corpora/HN/ingest.json --seed 41 --n-per-bin 500 --n-unanswerable 100 \
           --n-per-family 20 --n-per-wording 1 --sample-seed 20261101 --out qfull/HN --pool-out qpool/HN
per_family --in qfull/HN/questions.jsonl --splits qfull/HN/splits.json --only-splits dev-old,dev-new,held-out \
           --n 4 --seed 20261101 --out questions/HN
```

4 per family × 24 families = at most 96 per size (wordings dropped; `--n-per-wording 1` only because
`sample_sealed_set` requires a positive value). Families with no candidate at a size are dropped and reported,
never replaced (ADR-0035 rule).

**Scopes** (fixed now, before any answer):
- **common** (primary): families with ≥ 1 question at **every** ladder size H1–H30, LOOP_ACTUATED_VALVE excluded
  (ADR-0044 U2). This removes the family-mix confound: H1 has one unit and one sheet, so unit-crossing and
  sheet-crossing families vanish there, and they are the hard ones.
- **all** (secondary): every family present at that size, LOOP_ACTUATED_VALVE excluded.
- Per family and per k-bin tables are reported, not claimed.

**H100 (stage C only):** `per_family --in data/runs/sealed/questions/H100/questions.jsonl --splits … --only-splits
dev-old,dev-new,held-out --n 1 --seed 20261101` → 24 questions, whose cyp/ag answers already exist in
`ST-CYP-H100` / `ST-AG-H100` (same frozen pins), so only ctx-high is paid.

**EX01:** CP11–CP15 from `chatpid_ex01_qa.jsonl`, `AnswerType.FREE_TEXT`, text unchanged (natural-questions rule).

## 6. Freeze and pre-registration

EXP-0001 runs after the sealed test, so it is not sealed, but it is **pre-registered**: everything below is fixed
and hashed before the first EXP-0001 answer exists.

**Frozen at F1 and used unchanged** (any change would make EXP-0001 measure a different system than EXP-0002):
`qa/strategies/**`, `qa/serialize.py`, `qa/final_answer.py` and its template, `qa/primer.py` and
`qa/prompts/**`, `qa/cypher.py`, `qa/agent/**`, `qa/plant_api/**`, `qa/context_render.py`, `llm/**`,
`qa/cascade/**` (accept rules, join, report), the four sealed input files, the policy files.

**What that implies.** If ContextRAG shows a fixable weakness (GraphML with hex ids is token-heavy; ChatP&ID's
"topology mode" might move the wall), it is **reported, not fixed**. The same holds for the cascade's known
isolation weakness (EXP-0002: UPSTREAM_ISOLATION 15–17/30). A smarter serializer would be a new arm under a new
ADR, never a silent change.

**New and allowed:** corpora H1–H30, their questions, EX01's import and checklist, the ctx pins and policy files
(data), and new modules under `src/plantgraph/qa/exp0001/` (EX01 runner and EXP-0001 report, §11).

**Mechanism** (as ADR-0053 5B):
1. **E** = a user commit of the §11 code, clean tree. `data/runs/exp0001/E.commit`.
2. `make_set.sh` builds corpora and questions at E, then writes `E.sha256` over: `E.commit`, `inputs/*` (pins,
   params, policies, `ex01_checklist.json`, `listing_E.json`), `corpora/*/ingest.json`, `questions/*/questions.jsonl`,
   `data/external/chatpid_ex01_qa.jsonl`, this design note, ADR-0054.
3. `run_exp0001.sh` refuses to start unless: tree clean; HEAD = E; `sha256sum -c E.sha256`;
   `git diff --name-only F1 E -- src` lists only T's allowed paths plus `src/plantgraph/qa/exp0001/`.
4. **Replay guard (free):** a cache-only replay of `ST-AG-H100` at E must be byte-identical to the sealed run.
   It proves the agent and final-answer path are still the F1 path. (A Cypher replay would need H100 in Neo4j;
   the git diff check covers that path.)
5. Deviations go to `data/runs/exp0001/DEVIATIONS.md`, with date and reason, as in the sealed run.

The design note and ADR-0054 are hashed, so their acceptance must be recorded **before** `make_set.sh` runs.

## 7. Claims and decision rules (pre-registered)

Notation: Δ(s) = acc@120(ctx-high) − acc@120(cascade_v3) on the same questions at size s; paired bootstrap over
questions, 10,000 resamples, seed 20261101, 95 % percentile CI (`qa/cascade/stats.paired_bootstrap`). x(s) =
log10(realized sheets).

| Id | Claim | Rule | Scope |
|---|---|---|---|
| **X1 (primary)** | The single-sheet advantage of ContextRAG shrinks with corpus size | OLS slope of Δ(s) on x(s) over H1, H3, H10, H30; bootstrap (resample questions within each size). **PASS** if the CI's upper bound < 0 | common |
| X2 | ChatP&ID's end holds: on one sheet ContextRAG is not worse than the cascade | **PASS** if the CI lower bound of Δ(H1) ≥ −0.05 (non-inferiority, the ±5-point margin of Q4) | common, then all |
| X3 | Accuracy flip point | s_acc = smallest measured size whose Δ CI upper bound < 0. Reported as "between s_prev and s_acc". None up to H30 → "no accuracy flip up to 30 sheets", and **stage C becomes eligible** | common |
| X4 | Cost and latency flip | s_cost = smallest size with mean $/q(ctx-high) > mean $/q(cascade_v3); s_lat = same on median latency. Descriptive, with the ratios | all |
| X5 | The context wall | r = median(prompt chars / prompt tokens) over ctx-high calls; c = chars per sheet from a least-squares fit of prompt chars on sheets; W = 922,000 × r / c sheets (listing re-read on the run day). H100 fits iff 1,649,451 / r < limit; H1000 likewise. No call | — |
| X6 | Effort sensitivity | Δacc and Δ$ of ctx-low vs ctx-high at H1 and H10. Descriptive | all |
| EX01 | Anchor | correct / 5 per arm per repeat, $/q, latency, prompt size; set beside ChatP&ID's 0.91 ($0.0044, 24.3 s) with the metric difference stated. **No claim** | 5 questions |

**Reading the outcome** (fixed now):
- X2 PASS and X1 PASS → "the single-sheet optimum is real on our pipeline and erodes with size; it flips at
  s_acc (accuracy), s_cost (cost), W (fit)". This is the claim's inversion, measured.
- X2 PASS, X1 FAIL → "ContextRAG holds its accuracy up to 30 sheets; the inversion is driven by cost (X4) and fit
  (X5)", and stage C decides whether accuracy flips by 100 sheets.
- X2 FAIL → "on this model and these questions, the published optimum does not hold even on one sheet"; the
  thesis says so and does not re-tune.
- A ceiling (both arms ≥ 0.98 everywhere) gives a flat slope: X1 FAIL, reported as such.

**Stage C trigger.** Run ctx-high on H100 (24 questions) only if X3 finds no flip up to H30 **and** X5 predicts
H100 fits **and** the user approves the spend. Otherwise H100 stays "not run (ADR-0038), predicted to fit".

## 8. Metrics and report

Per size × arm: n; acc@120 with Wilson CI; uncut accuracy; mean and median $/q (all calls); latency median / p90;
outcome counts (ANSWERED, NOT_PRESENT, PARSE_FAILURE, TIMED_OUT, DID_NOT_FIT, RETRIEVAL_ERROR, PROVIDER_ERROR).
Per size: realized sheets, occurrence nodes, ctx prompt chars, median prompt tokens, r. Then the X1–X6 verdict
table and a single figure: acc@120 and $/q against log sheets, with H100 (if run) and the H1000 wall marked.
Local compute is taken from INFRA-1 (ContextRAG serialization 0.34 s at 100 sheets); no new infrastructure run.

## 9. Run plan

### 9.1 `data/runs/exp0001/make_set.sh` (free; after E)

```sh
#!/bin/sh
# EXP-0001 ladder corpora, questions and EX01 import at commit E (ADR-0054). No paid call, no Neo4j.
set -eu
S=data/runs/exp0001; P=.venv/Scripts/python
die() { echo "ERROR: $*" >&2; exit 1; }
[ ! -e $S/E.sha256 ] || die "E.sha256 exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
git rev-parse HEAD > $S/E.commit
sheets() { $P -c "import json,sys;print(json.load(open(sys.argv[1]))['counts']['n_sheets'])" "$1"; }
for seed in $(seq 100 399); do   # H1: the first seed whose one-unit corpus is exactly one sheet
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1 --seed $seed --corpus-id H1 --check \
    --no-neo4j --out $S/scan/H1-$seed > $S/scan/H1-$seed.log 2>&1 || die "scan seed $seed failed"
  [ "$(sheets $S/scan/H1-$seed/ingest.json)" = 1 ] && { echo $seed > $S/H1.seed; break; }
done
[ -e $S/H1.seed ] || die "no one-sheet unit in seeds 100-399: stop and ask (fallback: two-sheet H1, seed 100)"
build() {  # build <id> <target> <seed>
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --corpus-id "$1" --check \
    --no-neo4j --out "$S/corpora/$1" > "$S/logs/corpus_$1.json" || die "corpus $1 failed"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$1" --ingest-json "$S/corpora/$1/ingest.json" \
    --seed 41 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 1 \
    --sample-seed 20261101 --out "$S/qfull/$1" --pool-out "$S/qpool/$1" || die "questions $1 failed"
  $P -m plantgraph.qa.questions.per_family --in "$S/qfull/$1/questions.jsonl" \
    --splits "$S/qfull/$1/splits.json" --only-splits dev-old,dev-new,held-out --n 4 --seed 20261101 \
    --out "$S/questions/$1" || die "subsample $1 failed"
}
mkdir -p $S/logs; build H1 1 "$(cat $S/H1.seed)"; build H3 3 3; build H10 10 3; build H30 30 3
$P -m plantgraph.qa.questions.per_family --in data/runs/sealed/questions/H100/questions.jsonl \
  --splits data/runs/sealed/questions/H100/splits.json --only-splits dev-old,dev-new,held-out --n 1 \
  --seed 20261101 --out $S/questions_c/H100
$P -m plantgraph.ingest proteus data/external/C01V04-VER.EX01.xml --corpus-id EX01 --no-neo4j \
  --out $S/corpora/EX01 > $S/logs/corpus_EX01.json || die "EX01 import failed"
sha256sum $S/E.commit $S/H1.seed $S/inputs/* $S/corpora/*/ingest.json $S/questions/*/questions.jsonl \
  $S/questions_c/H100/questions.jsonl data/external/chatpid_ex01_qa.jsonl \
  docs/private/40-design/exp0001-single-sheet.md docs/private/20-decisions/ADR-0054-*.md > $S/E.sha256
cat $S/qfull/*/availability.json | head -60   # per-family n actually available
```

### 9.2 `data/runs/exp0001/run_exp0001.sh` (paid; stages A and B)

Header rules: **do not run pytest while this runs; one corpus in Neo4j at a time; ends with D1000 (plant) loaded.**
`preflight`, `load`, `health`, `finish`, `replay` are the sealed script's functions with `S=data/runs/exp0001`,
plus:

```sh
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$|src/plantgraph/qa/exp0001/)'
# preflight also: HEAD == E.commit; sha256sum -c E.sha256; F1 diff within ALLOWED;
# fetch https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints -> logs/listing_run.json and stop if the
# openai endpoint's price or max_prompt_tokens differs from inputs/listing_E.json (re-estimate before spending)

ctx() {  # ctx <run-id> <corpus> <pin> <cap> <stage>
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0001 --corpus "$2:test" --strategy context_rag \
    --pin-json "$3" --corpora-root $S/corpora --questions-root $S/questions --runs-root $S/runs \
    --cache-path $S/cache_exp0001.sqlite --allow-paid-calls --cost-per-question-usd 0.02 \
    --max-spend-usd "$4" --concurrency 4 --question-deadline-s 300 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" ${rc:-0} "$5"
}
# cypher(), agent(): the sealed functions with --experiment EXP-0001 and $S paths.
```

Order:

| Step | What | Neo4j holds | Paid |
|---|---|---|---|
| 0 | preflight; replay guard `INF-ST-AG-H100` (cache `data/runs/sealed/cache_sealed.sqlite`, cache-only) | (unchanged) | no |
| A1 | `load EX01` (proteus, `--store-profile plant --fresh-database`) | EX01 | no |
| A2 | `python -m plantgraph.qa.exp0001 ex01 --arms ctx-high,ctx-low,ctx-gpt5mini,cyp,ag --repeats 3 --cap 0.40` (§11 E-T1) | EX01 | yes |
| B1 | for H1, H3, H10, H30: `load` → `cypher E1-CYP-<c>` (H1 first as smoke, cap $0.01) → cache-only replay | each alone | yes |
| B2 | restore D1000 (as the sealed script) | **D1000** | no |
| B3 | `agent E1-AG-<c>` for the four sizes → replays | D1000 | yes |
| B4 | `ctx E1-CTXH-H1` smoke (cap $0.03) → **gate** (below) → full H1, H3, H10, H30 | D1000 | yes |
| B5 | `ctx E1-CTXL-H1`, `E1-CTXL-H10` → replays of all ctx runs | D1000 | yes |
| B6 | `cascade report` over the five policies, then `python -m plantgraph.qa.exp0001 report` (§11 E-T2) | D1000 | no |

**Gate after the ctx smoke** (python heredoc in the script, like `health`): from the smoke rows compute r and
the mean output cost per question; project the remaining ctx cost as Σ n × (prompt chars / r × input price +
output cost). If the projection exceeds **$6.00**, stop and ask the user.

### 9.3 `data/runs/exp0001/run_exp0001_h100.sh` (stage C; only on the §7 trigger and the user's approval)

No Neo4j. `ctx E1-CTXH-H100` on `questions_c/H100`, corpora root `data/runs/sealed/corpora`, concurrency 2,
deadline 300 s, cap $4.00; replay; re-run the EXP-0001 report with `--h100-tiers
data/runs/sealed/runs/ST-CYP-H100,data/runs/sealed/runs/ST-AG-H100` so cascade_v3 on the same 24 questions is
joined from the sealed rows.

### 9.4 Abort rules

- Tier runs (cyp, ag): the sealed `health` rule (PROVIDER_ERROR + PARSE_FAILURE > 10 %, or RETRIEVAL_ERROR > 60 %
  → stop).
- ctx runs: PROVIDER_ERROR > 10 % → stop. PARSE_FAILURE, TIMED_OUT and DID_NOT_FIT are **results** and are
  reported, except PARSE_FAILURE > 50 % in the H1 smoke, which signals a pipeline fault → stop and ask.
- A stopped run is resumed once under the same run id. A second technical stop on the same run → stop, report,
  ask. Pins, prompts and code never change mid-experiment.

## 10. Budget and time

Estimates, not measurements. Basis: measured sealed $/q for the tiers; for ctx, PROMPT-04 chars per sheet, the
2026-10-10 listing, and an **assumed** ratio and output (central 3.0 chars/token and $0.002 output per question;
cap basis 2.5 and $0.004). The smoke gate replaces both assumptions with measurements before the large stages.

| Run | n | Central | Cap |
|---|---|---|---|
| EX01, 5 arms × 5 q × 3 repeats | 75 answers | $0.15 (GPT-5-mini ≈ half of it) | $0.40 |
| E1-CYP-H1…H30 | 4 × ≤ 96 | $0.17 | 4 × $0.15 |
| E1-AG-H1…H30 | 4 × ≤ 96 | $0.27 | 4 × $0.20 |
| E1-CTXH-H1 / H3 / H10 / H30 | 96 each | $0.25 / $0.40 / $0.77 / $1.81 | $0.60 / $0.80 / $1.50 / $3.00 |
| E1-CTXL-H1 / H10 | 96 each | $0.08 / $0.60 | $0.20 / $1.00 |
| **Stages A + B** | ≤ 1,420 answers | **≈ $4.5** | caps total ≈ $8.9 (ceilings; gate at $6) |
| Stage C: E1-CTXH-H100 (conditional) | 24 | ≈ $2.7 (550k tokens × $0.20/M + output) | $4.00 |

Time: coder E-T1…E-T3 ≈ 1–1.5 days; `make_set.sh` minutes; stages A+B ≈ 2–2.5 h wall (≤ 1,420 answers at
concurrency 4, replays included); EX01 blind review ≈ 1 h (main session) + ≈ 20 min (user); stage C ≈ 20 min.

## 11. Coder tasks (Sonnet, sequential; new files only)

| Task | Files | Acceptance |
|---|---|---|
| **E-T1** EX01 runner and review | `src/plantgraph/qa/exp0001/{__init__,__main__,ex01_models,ex01_runner,ex01_review}.py`, `tests/qa/exp0001/` | `python -m plantgraph.qa.exp0001 ex01` loads EX01 via `load_corpus_artifacts`, builds each arm with `harness.registry.build_strategy` (unchanged), answers CP11–CP15 as `FREE_TEXT` through `attempt.run_unscored`, one cache file per repeat (`cache_ex01_r{1,2,3}.sqlite`, because the cache key has no repeat), `SpendGuard` cap, `--allow-paid-calls` required for network. Writes `run_config.json` (git commit, dirty flag, pins, prompt hashes, question-file sha256) and `answers.jsonl` (`Ex01AnswerRow`). Derives cascade_v3 per repeat with the **frozen** accept rules (`qa.cascade.accept`, imported). `ex01-review` writes a blind sheet (answers shuffled with seed 20261101, arm hidden behind an id) plus tag hits against `ex01_checklist.json`; `ex01-tally` reads `ex01_verdicts.json` and prints correct / 5 per arm per repeat. **Before any paid call:** a fake-transport dry run proves `cypher_rag_plant` and `graph_agent_low_steps` build and answer on EX01; if either cannot without touching frozen code, the arm is reported "not applicable on EX01" and **no frozen file is changed**. |
| **E-T2** EXP-0001 report | `src/plantgraph/qa/exp0001/{report,report_models,ladder_stats}.py`, tests | Reads harness run dirs (and the sealed ST-* dirs for stage C), joins by importing `qa.cascade.join`/`policy`/`stats`, applies cutoff 120 s. Outputs §8 tables, X1–X6 verdicts exactly as §7 words them, the figure data (CSV), `report.md`. Slope and paired CIs on synthetic fixtures with known answers; ctx-low present at only some sizes is handled. First checks whether `cascade report` already accepts a one-tier `context_rag` policy; if it does, reuse its per-question output instead of re-joining. |
| **E-T3** Scripts and inputs | `data/runs/exp0001/{make_set.sh,run_exp0001.sh,run_exp0001_h100.sh}`, `inputs/` (pins copied from sealed, `pin_ctx_gpt5mini.json`, params, `always_ctx_high.json`, `always_ctx_low.json`, `listing_E.json` fetched on E-day) | §9 as written; `sh -n` clean; a dry pass with paid calls off stops at the first cache miss as designed. The coder never passes `--allow-paid-calls`; the user runs the scripts. |

**Data models (E-T1, E-T2):**
- `Ex01ChecklistItem(qid, required_tags: list[str], ordered: bool, aliases: dict[str, list[str]], forbidden_tags: list[str], required_statements: list[str], note: str)`
- `Ex01AnswerRow(run_id, qid, arm, repeat, outcome: Outcome, answer_text: str | None, not_present: bool, cost_usd, latency_s, prompt_tokens, completion_tokens, context_chars, provider: str | None, trace: dict)`
- `Ex01Verdict(blind_id, qid, verdict: Literal["correct", "wrong"], reason: str, reviewer: str)`
- `SizePoint(corpus_id, n_sheets, n_occurrence_nodes, ctx_prompt_chars, ctx_prompt_tokens_median, chars_per_token)`
- `ArmCell(corpus_id, policy, scope, n, correct_at_120, acc_at_120: Interval, acc_uncut, cost_mean, cost_median, latency_median, latency_p90, outcomes: dict[str, int])`
- `PairedDelta(corpus_id, scope, a, b, n, delta, ci: Interval)`; `Trend(scope, slope, ci: Interval, n_boot, seed)`
- `ClaimVerdict(id, wording, value: str, verdict: Literal["PASS", "FAIL", "REPORTED", "NOT_RUN"])`

## 12. EX01 checklist (draft — the user checks it before E)

Drawn from ChatP&ID's reference answers **and** the imported graph (architect probe 2026-10-11). An answer is
correct iff every required tag appears (in order where `ordered`), no forbidden tag is asserted as part of the
answer, and every required statement is made. Tags match with spaces and case ignored.

| qid | Required | Ordered | Forbidden | Required statement | Notes |
|---|---|---|---|---|---|
| CP11 | H1007 | — | — | the feed from P4711 / the inlet has **no path to T4750 that bypasses H1007** in the drawing | the recirculation via H1008 still enters T4750 but carries tank contents; mentioning it is not required |
| CP12 | HV4750.01, PV4712.02 | no | TV4750.03 | — | the SV 104.01 relief line also enters T4750; naming it as "not closed / relief" is not wrong |
| CP13 | T4750, 66KL21, 75SA21, 73KH12, P4712 | yes | — | — | the reducer has no printed tag; mentioning it is optional |
| CP14 | path 1: H1007, P4711 (or the inlet); path 2: H1008 | per path | — | names the valve of each path: HV4750.01, PV4712.02 | **ChatP&ID's reference says `TV4712.02`; the file has no such tag** — the valve on the H1008 → T4750 line is `PV4712.02` (`TV4750.03` sits on the other H1008 outlet, which reaches no item) |
| CP15 | P4711, H1007, HV4750.01, T4750 | yes | — | — | |

Valve aliases: `HV4750.01` and `PV4712.02` are on `ActuatingFunction` nodes that `control` a `GlobeValve` tagged
`C1`. An answer that names only "C1" does not identify the valve (five items carry `C1`) and is wrong.

## 13. Threats

- **Family mix changes with size** — handled by the common scope (primary); the all-family scope is shown beside.
- **One plant per size; H1 is a minimum-size unit** chosen by sheet count. Topology variance is confounded with
  size at each point.
- **One repeat on the ladder; Luna takes no temperature** (LAT-CTRL-1: 3/48 correctness flips). EX01 has 3.
- **Effort asymmetry**: ctx-high vs a low-effort Cypher tier. X6 bounds it at two sizes.
- **Serialization frozen**: GraphML with hex ids is token-heavy. A compact rendering would move X4 and X5; not tested.
- **Small sizes were never developed on**: the tiers were tuned on D100/D1000; their small-corpus behaviour is new.
- **EX01**: n = 5, manual blind scoring against a checklist written by us, ChatP&ID's reference has a tag typo,
  imported as is (actuator-borne loop tags), and our metric (binary) is not ChatP&ID's (judge 0–1 over 19).
- **Price step** at 272k prompt tokens and listing changes; the preflight re-reads both.
- **Concurrency 4** for every ladder run, as sealed.

## 14. Decisions for the user (ADR-0054)

| # | Decision | Recommendation |
|---|---|---|
| U1 | Substrate | both: the ladder carries the claim, EX01 is a descriptive anchor |
| U2 | Ladder | H1 (seed-scanned one sheet), H3, H10, H30; 4 questions per family |
| U3 | ContextRAG effort | high as the primary arm; low at H1 and H10 as sensitivity |
| U4 | Primary claim | X1 slope over the common-family scope; X2 non-inferiority at H1 |
| U5 | H100 | conditional stage C (no flip by H30, predicted fit, user approval; ≈ $2.7) |
| U6 | EX01 scoring | pre-written checklist + blind manual review, user confirms; no LLM judge |
| U7 | EX01 control-valve tags (ADR-0044 U3) | import as is — the same pyDEXPI structure ChatP&ID read |
| U8 | EX01 model | add ContextRAG on GPT-5-mini (ChatP&ID's model), EX01 only, ≈ $0.08 |
| U9 | Freeze | commit E + `E.sha256` + F1 allow-list + replay guard |

## 15. Open questions

- **O1** Luna's price and `max_prompt_tokens` on the run day (preflight reads them; X5 uses the run-day figure).
- **O2** Does `cascade report` accept a one-tier `context_rag` policy and sizes where a policy has no run? (E-T2.)
- **O3** Do `cypher_rag_plant` and `graph_agent_low_steps` work on EX01 (no `unit_id`, `P4712` is a
  `GenericItem`)? E-T1's dry run answers it; no frozen fix either way.
- **O4** Does `ingest proteus --store-profile plant` load EX01 into Neo4j? Step A1 shows it (free).
- **O5** Is an abandoned call (deadline) billed? Affects cost accounting of TIMED_OUT rows only.
- **O6** ADR-0053 and the sealed report say `DID_NOT_FIT` for ContextRAG at H100. After X5 is measured, the main
  session appends an outcome-log line to ADR-0053 and the thesis words H100 as "not run (ADR-0038)".

## 16. Figures and sources

| Figure | Source |
|---|---|
| Prompt chars EX01 / H100 / H1000 | `_results.md` PROMPT-04 |
| Luna and GPT-5-mini window and prices | `30-experiments/openrouter-endpoints-2026-10-10.json`, `openrouter-models-2026-10-10.json` |
| Tier $/q, latency, sealed accuracies | `30-experiments/EXP-0002-sealed-test.md` |
| ChatP&ID 0.91, $0.0044, 24.3 s, GPT-5-mini | `10-literature/2603.22528.md` |
| EX01 36 nodes / 39 edges, 17,693 chars, tags on actuators | architect probe 2026-10-11 (scratch script, no network, no Neo4j) |
| One-sheet units 1/51 and 17/509 | `_results.md` SMOKE-07 |
| Run-to-run flips 3/48 | `_results.md` LAT-CTRL-1 |
| All $ in §10 | arithmetic on the rows above — **estimates** |
