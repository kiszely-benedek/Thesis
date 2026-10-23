# Faster OpenRouter models for the graph agent: shortlist and bake-off plan

**Read on:** 2026-10-10 · **Paid calls made:** none (free metadata endpoints, public web pages, local run files only)
**Snapshots saved:** `docs/private/30-experiments/openrouter-models-2026-10-10.json` (GET `/api/v1/models`),
`docs/private/30-experiments/openrouter-endpoints-2026-10-10.json` (GET `/api/v1/models/{id}/endpoints` for 13
models + `reasoning_config` from GET `/api/frontend/v1/catalog/models`).
**No paper involved** → no `10-literature/` row.

Source tags used below:
- **[OR-L]** OpenRouter model listing, 2026-10-10.
- **[OR-E]** OpenRouter per-endpoint list, 2026-10-10. Its `latency_last_30m` / `throughput_last_30m` fields came back `null` for every endpoint. The model pages render their speed charts client-side, so **OpenRouter's own speed figures were not readable**.
- **[OR-C]** OpenRouter catalog `reasoning_config`, 2026-10-10.
- **[OR-D]** OpenRouter provider-routing docs, https://openrouter.ai/docs/guides/routing/provider-selection, read 2026-10-10.
- **[AA]** Artificial Analysis, read 2026-10-10. Workload is 10,000 input tokens; latency is the median over the past 72 h; "first chunk" includes thinking time for reasoning models. Intelligence Index is v4.3.2. Pages: `artificialanalysis.ai/models/<slug>/providers`, `/models/<slug>`, `/leaderboards/models`.
- **[RUN]** our own run files under `data/runs/cv1/runs/`, computed 2026-10-10.
- **est.** an estimate, with the method stated.

---

## 1. Where our time actually goes [RUN]

graph_agent, QAR-P2-D100 (GLM-5.3-flash, default effort, 90 questions, unpinned route):

| | value |
|---|---|
| calls per question | 4.10 (agent steps + final answer) |
| prompt / completion tokens per question | 7,028 / 5,728 |
| completion tokens per call: p50 / p75 / p90 / p95 / max | 147 / 587 / 2,849 / 10,110 / 16,384 |
| calls with ≥ 1,000 completion tokens | 60 of 355 live calls → **79 % of all model time**, 88 % of completion tokens |
| calls that hit the 16,384 cap (`finish_reason: length`) | 15 → 49 % of model time |
| latency of short calls (< 100 completion tokens) | median 2.83 s (n = 134) |
| per-question model time, **steps + final** | median 23.7 / mean 99.8 / p90 377.3 / max 1,122.2 s |
| per-question model time, final call only | median 3.5 / mean 38.5 / p90 63.6 / max 1,035.4 s |

**Correction to `_results.md` QAR-P2:** that row reports "latency median 3.5 s / mean 38.5 / p90 63.6 / max 1,035 s", which is the **final call only**. Including the agent steps, it is median 23.7 / mean 99.8 / p90 377.3 s. The cost in that row ($0.258) already includes the steps.

**Correction to the anchor figure:** the 7,587-token step took 235.78 s, which is **32.2 tok/s**, not about 62. Its billed cost ($0.002250192 for 1,498 + 7,587 tokens) matches Novita FP8's GLM price ($0.084 / $0.28) to 7 decimals. That host match is an **inference from price**: the client does not store which host served a call. AA's median for Novita on GLM-5.3-Flash is 59 tok/s.

**Which hosts served us (inference from price, 257 calls with ≥ 1,500 completion tokens across QAR-P2, DEV10-D100 and DEV10-D1000):** each call's billed cost was matched to the nearest host price in [OR-E] (2026-10-10 prices, which may differ from the prices on the run dates). The result:

| inferred host | calls | median tok/s | range |
|---|---|---|---|
| Sail Research, FP4 | 121 | 90.5 | 21.5–129.8 |
| inference.net, FP4 | 43 | 92.7 | 32.3–285.3 |
| no match within 3 % | 31 | 70.5 | 15.8–127.0 |
| list-price hosts ($0.15/$0.50: Crusoe, CoreWeave, Parasail, Friendli, Atlas) | 20 | 114.0 | 11.3–274.1 |
| others: Novita, near-ai, GMI, DeepInfra, Phala, Decart, Inceptron | 42 | 61.7–98.6 | — |

This fits [OR-D]. Default routing picks a host "weighted by the inverse square of its price". Because our pin has `route_provider: null`, GLM traffic goes mostly to the cheapest (FP4-quantized) hosts. Those hosts are neither the fastest nor one fixed configuration. To confirm for free, look the `gen-…` ids up with `GET /api/v1/generation?id=…`. That endpoint costs nothing but needs the API key, so it was not called here.

**What follows.** There are two separate levers.
- **Fewer reasoning tokens** acts on the 17 % of calls that cause 79 % of the time.
- **Higher tokens/s** acts on every long call, but only proportionally.

What-if estimates (est.: each call = 2 s overhead + completion tokens ÷ its measured speed; applied to the graph_agent calls only, 9,363 s in total = 104.0 s per question):
- every call at ≥ 186 tok/s with the same tokens: 38.4 s/q
- every call capped at 1,000 completion tokens at its measured speed: 34.9 s/q
- both together: 15.5 s/q

**GLM-5.3-flash's default effort is `max`** ([OR-C]: efforts `low`/`high`/`max`, reasoning mandatory, default `max`). So our "default" pins (PAID-02, DEV10, QAR-P2, the T3-glm64k tier) all ran at **max** effort. `high` is an untested middle setting on the same model.

## 2. Shortlist

All six accept `response_format` (JSON mode) on the pinned host [OR-E]. All context windows are far above our largest prompt (about 30k characters).

| # | OpenRouter id → pinned host | $/M in / out [OR-E] | tok/s · first chunk (s) on that host [AA] | Reasoning controls [OR-C] | Params the host lacks [OR-E] | Context [OR-E] | AA Intelligence Index v4.3.2 |
|---|---|---|---|---|---|---|---|
| 1 | `z-ai/glm-5.3-flash` → `fireworks` (alt. `coreweave/nvfp4`) | 0.15 / 0.50 (both) | Fireworks 186 · 1.44; CoreWeave 172 · 1.57 (our measured long-call median ≈ 90) | low / high / max; **mandatory**; default **max** | Fireworks: **no `seed`** (CoreWeave has seed, but it is FP4) | 1,048,576 | **42** (model page; effort not stated) |
| 2 | `anthropic/claude-haiku-5.5` → `anthropic` | 0.10 / 0.50 | 237 · 292.71 at max; leaderboard: low 180 · 10.18, medium 169 · 14.42 | low / medium / high / xhigh / max; **not mandatory (can be off)**; default medium | **no `temperature`, no `seed`** on any host | 1,000,000 | max **43** (model page); leaderboard only: high 38, medium 34, low 29 |
| 3 | `deepseek/deepseek-v4.1-flash` → `parasail/fp8` (alt. `deepseek`) | Parasail 0.30 / 1.20; DeepSeek 0.15 / 0.60 | Parasail 221 · 1.02; DeepSeek 217 · 1.03 | low / high / max; not mandatory; default high | DeepSeek first-party: no `seed`; Parasail has every param | 1,048,576 | leaderboard only: max 39, non-reasoning 25 |
| 4 | `openai/gpt-6-luna` → `openai` | 0.10 / 0.50 (`openai/fast` 0.20 / 1.00) | max 137 · 101.52; leaderboard: low 129 · 3.20, non-reasoning 118 · 0.77 | none / low / medium / high / xhigh / max; not mandatory; default medium | **no `temperature`** | 1,050,000 | max **38** (model page); leaderboard only: low 22, non-reasoning 18 |
| 5 | `openai/gpt-oss-120b` → `cerebras/fp16` (alt. `groq`) | Cerebras 0.35 / 0.75; Groq 0.15 / 0.60 | **Cerebras 1,668 · 0.46**; Groq 472 · 0.71 (high variant) | low / medium / high; mandatory; default medium | none (Cerebras max output 40,960) | 131,072 | **12** (high, model page); leaderboard: low 10 |
| 6 (reference) | `xiaomi/mimo-v2.6-pro` → `xiaomi/fp8` | 0.435 / 0.87 | Xiaomi 43 · 3.45; DeepInfra 39; GMI 46; Novita 36 | effort levels not exposed in [OR-C]; `reasoning` param accepted | Xiaomi host: no `seed` | 1,048,576 (host) | not shown on AA pages read |

On "comparable quality": only #2 at high/max effort and #1 itself reach GLM's 42 on AA's general index. #3 (39 at max) and #4 (38 at max) are close at max effort, but max is exactly the setting we are trying to avoid. At low effort the leaderboard has Haiku at 29 and Luna at 22. #5 is the **speed ceiling**, with a large general-reasoning gap (12 vs 42). Our measured task accuracy outranks any of these indices: MiMo scored 46 on AA's leaderboard and beat GLM 34/36 vs 32/36 on MIMO36. Only the bake-off can show whether low effort is enough for single JSON tool-call steps.

**Considered, not shortlisted.**
- `z-ai/glm-5.3-flashx` ($0.37 / $1.25): the vendor claims "up to 200 tokens/s" [OR-L]. There is no AA data, it has a single host (`z-ai/fp8`), and that host has no `seed` [OR-E].
- `xiaomi/mimo-v2.6-pro-ultraspeed` ($4.35 / $8.70): 10× the price, no AA data.
- `inception/mercury-2.5`: a diffusion LM at 720 tok/s · 3.33 s [AA], but index 12 and no `seed`.
- `google/gemini-3.5-flash-lite`: index 22.
- `qwen/qwen3.8-27b` on `cerebras/fp16`: that host has **no `response_format`** [OR-E], and AA lists no Cerebras row.
- `minimax/minimax-m3` on SambaNova: 120 tok/s [AA], not fast; AA shows no index.

High-throughput hosts (Cerebras, Groq, SambaNova) on OpenRouter today serve only `gpt-oss-120b`/`20b`, `qwen3.8-27b` (Cerebras, no JSON mode), `minimax-m3` and `-m2.7`, `llama-3.3-70b`, and older DeepSeek versions [OR-E]. **No capable model (index ≥ about 38) is on Cerebras or Groq with JSON mode.**

## 3. Why each could be faster for *our* workload

| # | Lever | Mechanism |
|---|---|---|
| 1 GLM @ Fireworks | **tokens/s** (and `high` instead of `max` for **tokens**) | The same model at about 2× our measured long-call median. Moving the default from max to high cuts the runaway tail without changing the model, so ADR-0014's one-model rule is kept. |
| 2 Haiku 5.5 | **tokens** (effort low or off) + tokens/s (about 170–240) | Short JSON steps need little thinking. Reasoning is optional, so the 147-token median step could stay close to its JSON length. |
| 3 DeepSeek V4.1 Flash | **tokens** (low or off) + tokens/s (about 220) | Optional reasoning. Fast hosts that support our full parameter set exist. |
| 4 GPT-6 Luna | **tokens** (`none`/`low`) | AA: 0.77 s first chunk with no reasoning. Throughput (about 120–130) is only somewhat above ours. Quality at low effort is the risk. |
| 5 gpt-oss-120b @ Cerebras | **tokens/s** (about 18× ours) | Even a 7,587-token runaway takes about 4.5 s at 1,668 tok/s (est.). Best fit for the Cypher tier, where completions are short and the schema is given. |
| 6 MiMo-V2.6-Pro | **tokens** only | MIMO36 measured a median of 169 completion tokens (GLM: 502) with 0 PARSE_FAILURE. Its host speed (36–46 tok/s) is *slower*, so a long answer is slower. |

## 4. Cost estimate from our measured tokens [RUN] × [OR-E] prices

Per-question token counts:
- **graph_agent:** 7,028 prompt + 5,728 completion (QAR-P2 measured, GLM at max effort; this is the **pessimistic** column).
- **Capped 1k:** the same calls with each completion capped at 1,000 tokens, giving 1,433 completion per question (est., a plausible low-effort case).
- **Cypher tier:** 1,690 prompt + 173 completion (CYP-D100-low, GLM low).

Other models tokenize differently and may take more or fewer steps, so read these as ±30 % (est.).

| Config | GA $/q pess. | GA $/q capped | CY $/q | 18 q GA pess. | 18 q CY | 72 q GA pess. |
|---|---|---|---|---|---|---|
| GLM-5.3-flash @ Fireworks / CoreWeave | 0.0039 | 0.0018 | 0.00034 | 0.071 | 0.006 | 0.282 |
| Claude Haiku 5.5 | 0.0036 | 0.0014 | 0.00026 | 0.064 | 0.005 | 0.257 |
| DeepSeek V4.1 Flash @ Parasail | 0.0090 | 0.0038 | 0.00071 | 0.162 | 0.013 | 0.647 |
| DeepSeek V4.1 Flash @ DeepSeek | 0.0045 | 0.0019 | 0.00036 | 0.081 | 0.006 | 0.323 |
| GPT-6 Luna | 0.0036 | 0.0014 | 0.00026 | 0.064 | 0.005 | 0.257 |
| gpt-oss-120b @ Cerebras | 0.0068 | 0.0035 | 0.00072 | 0.122 | 0.013 | 0.486 |
| gpt-oss-120b @ Groq | 0.0045 | 0.0019 | 0.00036 | 0.081 | 0.006 | 0.323 |
| MiMo-V2.6-Pro (reference) | 0.0080 | 0.0043 | 0.00089 | 0.145 | 0.016 | 0.579 |
| Claude Sonnet 5.5 (comparison only) | 0.0713 | 0.0284 | 0.00511 | 1.284 | 0.092 | 5.136 |

Measured billed cost per question, for comparison: graph_agent $0.00295 and Cypher $0.00023 [RUN]. These are below list because of the cheap FP4 hosts.

## 5. Bake-off plan

**Stage 0 (free, before any paid call)**
1. Pin check against [OR-E]. Every parameter we send must be listed by the pinned host, because `require_parameters: true` would otherwise return 404. Concretely:
   - Haiku and Luna pins: `temperature: None`.
   - Haiku pin: `seed: None`.
   - GLM @ Fireworks pin: `seed: None`.
   - For DeepSeek, use Parasail, which lists every parameter.

   Note that [OR-D] treats `response_format` as a **soft preference even under `require_parameters`**, so JSON mode is not guaranteed by routing.
2. Optional, and needs the user's key, though it costs nothing: `GET /api/v1/generation?id=<gen-id>` for the QAR-P2 calls, to replace the price-based host inference with the real provider names.
3. Code facts the plan depends on:
   - `_step_pin` (`qa/agent/loop.py`) **overwrites** `extra.reasoning` with `{"effort": "low"}` when `step_effort="low"`. A reasoning-off pin would be switched back on for steps, so run reasoning-off configs with `step_effort="default"` and set the effort in the pin.
   - The cache key is pin + JSON mode + messages (`llm/cache.py`), so every new host or effort gets fresh keys and nothing old is overwritten.
   - A repeat with the same pin replays from cache and does **not** re-measure latency. Latency repeats need a fresh cache file.
4. Pre-register the selection rule (proposal):
   - A config passes Stage 1 if it scores ≥ baseline − 1 of 18 correct, has ≤ 1 PARSE_FAILURE, and has a lower **p90** per-question total latency (steps + final) than the baseline.
   - Rank the passing configs by p90 latency, then by accuracy.
   - At most 2 go to Stage 2.

**Stage 1: 18 questions (one per family from `data/runs/cv1/q5/D100/questions.jsonl`, fixed seed), graph_agent v2 (`da38f58`, step_effort low unless stated) + `cypher_rag_plant`, D100, concurrency 4, all configs in one time window.**

| Config | Pin | Est. GA+CY, 18 q (pess.) | Hard cap |
|---|---|---|---|
| S1-A baseline | GLM-5.3-flash, current pin (unpinned host, final at max) | 0.077 | $0.20 |
| S1-B host lever | GLM @ `fireworks`, same efforts, seed None | 0.077 | $0.20 |
| S1-C effort lever | GLM @ `fireworks`, final effort `high` | 0.077 | $0.20 |
| S1-D | Haiku 5.5 @ `anthropic`, effort low, temp/seed None | 0.069 | $0.20 |
| S1-E | DeepSeek V4.1 Flash @ `parasail`, effort low | 0.175 | $0.35 |
| S1-F | GPT-6 Luna @ `openai`, effort low, temp None | 0.069 | $0.20 |
| S1-G speed ceiling | gpt-oss-120b @ `cerebras`, effort low | 0.135 | $0.30 |
| **Stage total** | | **0.679** | **$1.50** |

S1-A can be dropped if a graph_agent v2 run on these 18 questions already exists under the same pin.

**Stage 2: the remaining 72 questions for the best 1–2 configs.** Pessimistic estimate per config: GA $0.26–0.65 + CY $0.02–0.05. Cap **$0.80 per config, $1.60 for the stage**.

**Stage 3 (optional): latency repeatability.** Re-run the 18 questions for the winner and the baseline with a **fresh cache file**, at another time of day: about $0.08 each (est.). Cap **$0.30**.

**Worst case for all stages: $3.40** of the about $19 left. Each stage stops early at its cap (`--max-spend-usd`).

**Routing for reproducible latency.** Keep `provider.order = [host]` with `allow_fallbacks: false` (already implemented in `request_kwargs.py`) and always set `route_provider`; never leave it `null`. Do **not** use `sort: "throughput"` or `preferred_min_throughput`. Per [OR-D] those react to a rolling 5-minute window and only deprioritize hosts, so the host can change from call to call. Consider `provider.quantizations` (e.g. `["fp8", "bf16", "fp16"]`) only where a single host cannot be pinned. Small code addition worth making (coder): store the serving `provider` from the response body on `ChatResponse`, so the host is a recorded fact rather than an inference.

## 6. Risks

1. **Provider variance.**
   - Within one inferred host our speed spread is 21–130 tok/s [RUN].
   - AA's figures are 72-hour medians on a 10k-input workload, not our prompts, and not OpenRouter's own measurements.
   - Pinning one host removes the between-host variance, but not the within-host variance, and fallbacks off means an outage becomes a `provider_error`. 1-day uptime [OR-E]: Fireworks GLM 99.44 %, CoreWeave GLM 100 %, Anthropic 100 %, OpenAI 100 %, Parasail DeepSeek 100 %, Cerebras gpt-oss 100 %; `openai/flex` for Luna only 76.7 %.
2. **JSON compliance.** `response_format` is a soft preference in routing [OR-D], so whether the host's JSON mode actually works must be **measured** (PARSE_FAILURE per config). Our client sends `json_object`, not a JSON schema.
3. **Quantized routes.**
   - Our past GLM numbers (DEV10, QAR-P2, CP-P2) were most likely served mostly by FP4 hosts (inference). A pinned host with another quantization is a different configuration, which is why S1-A runs on the same 18 questions instead of reusing old answers.
   - Cerebras gpt-oss is fp16, Parasail DeepSeek fp8, CoreWeave GLM nvfp4; Fireworks reports "unknown".
4. **Determinism.** Haiku and Luna hosts list no `temperature`; Haiku and Fireworks-GLM list no `seed` [OR-E]. Those pins run at the provider's default sampling, so run-to-run variance is higher and must be stated in the thesis.
5. **Cache/replay.** New pins mean new keys (safe), and replays reproduce the recorded latency. Re-measuring latency needs a fresh cache file.
6. **ADR-0014 point 4.** The model is frozen per sweep. Switching after sweep results exist means re-running those sweeps, so the bake-off must conclude before the sweep.
7. **Benchmarks ≠ our task.** AA's index is general. Per-effort indices come from the leaderboard page only (not checked on the model pages). Haiku 5.5 was released on 2026-10-07, so its price and behaviour may still change.

## Sources
- OpenRouter models listing and per-endpoint lists, read 2026-10-10 (snapshots above).
- [OpenRouter provider selection docs](https://openrouter.ai/docs/guides/routing/provider-selection)
- [AA GLM-5.3-Flash providers](https://artificialanalysis.ai/models/glm-5-3-flash/providers), [AA GLM-5.3-Flash](https://artificialanalysis.ai/models/glm-5-3-flash)
- [AA gpt-oss-120b providers](https://artificialanalysis.ai/models/gpt-oss-120b/providers), [AA gpt-oss-120b](https://artificialanalysis.ai/models/gpt-oss-120b)
- [AA Claude Haiku 5.5 providers](https://artificialanalysis.ai/models/claude-haiku-5-5/providers), [AA Claude Haiku 5.5](https://artificialanalysis.ai/models/claude-haiku-5-5)
- [AA GPT-6 Luna providers](https://artificialanalysis.ai/models/gpt-6-luna/providers), [AA GPT-6 Luna](https://artificialanalysis.ai/models/gpt-6-luna)
- [AA DeepSeek V4.1 Flash providers](https://artificialanalysis.ai/models/deepseek-v4-1-flash/providers), [AA MiMo-V2.6-Flash providers](https://artificialanalysis.ai/models/mimo-v2-6-flash/providers), [AA MiMo-V2.6-Pro providers](https://artificialanalysis.ai/models/mimo-v2-6-pro/providers)
- [AA Mercury 2.5 providers](https://artificialanalysis.ai/models/mercury-2-5/providers), [AA MiniMax-M3 providers](https://artificialanalysis.ai/models/minimax-m3/providers), [AA Qwen3.8 27B providers](https://artificialanalysis.ai/models/qwen3-8-27b/providers)
- [AA models leaderboard](https://artificialanalysis.ai/leaderboards/models)
- Secondary, conflicting, not used for figures: [eesel.ai GLM-5.3-Flash pricing](https://www.eesel.ai/blog/glm-5-3-flash-pricing), [Requesty GLM-5.3-Flash](https://www.requesty.ai/model/zai/glm-5-3-flash)
