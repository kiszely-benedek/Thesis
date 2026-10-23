---
adr: 0055
title: Polish the demo for non-specialists — one question box with Hungarian example questions, typed questions always FREE_TEXT, a demo-owned merged Luna cache, the plant-profile ingest file per corpus, Hungarian label tables with a coverage test, fragment-only PDF jumps, and an Eredmények tab projected from the measured report.json files and drawn as inline SVG
status: accepted (user, 2026-10-12) — U1 (a) Hungarian D1000 examples with a paid warm-up (~$0.03, estimate), U2 (a) typed questions always FREE_TEXT, U3 (a) show the answer as it comes, U4 (a) Hungarian money format
date: 2026-10-12
supersedes: none. Amends ADR-0049 (proposed) in part — decision 7's "own cache" now starts as a merged copy of the experiment cache; §6.3's answer-form selector and §6.4's iframe rebuild are replaced. ADR-0024, ADR-0049 points 1–6 and the F1 freeze (ADR-0053) carry over unchanged.
design: 40-design/demo-polish.md
---

# ADR-0055 — Demo polish

## Context

The user tried the demo (2026-10-12): *"This should be a demo app, absolutely user-friendly."* *"Why is it written
which type each question is? In real life nobody will write that this is a CONNECTED question."* The benchmark
picker shows raw ids and family codes, the answer-form selector is unexplained, and outcome codes, notices and
errors are English developer text. Three wiring faults were found (design note §1):

- The demo cache is the GLM-era file, so benchmark questions miss and make paid calls, although the Luna runs the
  config names were cached in `cache_luna.sqlite`.
- The Cypher tier never runs: each corpus has one `ingest_json`, the occurrence-profile file, and the store check
  refuses it. Neo4j holds D1000 in the plant profile.
- The paid cascade opens lazily, so the first paid question waits for it.

Constraints: everything outside `src/plantgraph/demo/` is frozen (F1, commit 07d4029); no number may be typed by
hand; the cache key is pin + messages only (`llm/cache.py`), so a replay hits only on identical prompts.

Measured for this ADR (architect scratch, free): through the frozen `open_live_cascade`, with a copy of
`cache_luna.sqlite` and the plant-profile ingest file, D1000 dev 180/180 replays hit with both tiers and 180/180
answers equal the recorded `CYPL2-D1000`/`AGL3-D1000` rows; D100 dev 180/180 and PARA 252/252 hit agent-only (the
store holds D1000). The occurrence and plant ingest files differ only in the store profile, counts, timings and the
order of one set.

## Options considered

**1 — Answer type of a typed question**
- **A. Always FREE_TEXT; an unchanged example keeps its stored type, hidden (chosen).** Acceptance rules read only
  outcome, row count and abstention, never the answer type; FREE_TEXT only requires a string. The one measured
  sample (EX01, 90 FREE_TEXT answers) has 0 parse failures.
- **B. Rule-based type guess in the demo.** Free and fast; a wrong guess demands the wrong shape (parse failure or
  a misleading answer); the comparable need-classifier rules recognised 6/36 Hungarian rewordings (PARA-R0).
- **C. LLM type guess.** One more paid call per question, unevaluated, adds latency.
- **D. Keep the selector with a default.** What the user rejected.

**2 — Making the Cypher tier run**
- **A. Point `ingest_json` at the plant-profile file (chosen).** Config only; the file is the record of what is in
  Neo4j and rebuilds the same sheets (verified by the replay hits).
- **B. A second field `store_ingest_json`.** Explicit, but rebuilds the corpus twice (D1000 rebuild 20 s).
- **C. A `store_profile` field and building the plan in the demo.** Duplicates the ingest's plan step in the demo.
- **D. Load Neo4j in the occurrence profile.** The Cypher tier reads the plant profile only.

**3 — Cache**
- **A. A demo-owned merged copy of `cache_luna.sqlite` and the old demo cache, with a provenance sidecar (chosen).**
- **B. Point the demo at `cache_luna.sqlite`.** Free, but demo calls would enter an experiment cache (ADR-0049 7C).
- **C. Layered read-through cache.** Needs a change to the frozen client builder.

**4 — Example questions**
- **A. A small curated example file per corpus, plain `Question` lines with gold, built by a demo CLI with a
  provenance sidecar; D100 = the hu1 Hungarian wording of the 36 PARA-R1 base questions (free replay); D1000 = 36
  English dev questions until the user decides on Hungarian wordings (chosen).**
- **B. All 180 dev questions, without ids.** Too long to browse; English only.
- **C. Display-only Hungarian translations of English questions.** The screen would not show what the system was
  asked.

**5 — Results data**
- **A. Project the two `report.json` files at request time, with path, sha256 and date (chosen).** No copy can go
  stale; nothing is typed.
- **B. An extraction CLI writing a JSON snapshot into `data/runs/cv1/demo/`.** Needed only when a report exists as
  markdown alone — both exist as JSON.
- **C. Numbers in the page source.** Forbidden (never invent a number).

**6 — Charts**
- **A. A small inline-SVG module (`charts.js`), no CDN, no build step (chosen).** Two chart kinds (line with log axes
  and whiskers; grouped bars with whiskers) are all that is needed.
- **B. Vendored Chart.js or similar.** Mature, but a vendored dependency the professor must audit, and log-axis
  whiskers need plugins.
- **C. Server-side PNGs (matplotlib).** A heavy runtime dependency; no hover values.

**7 — PDF jumps**
- **A. One persistent iframe, fragment-only `#page=N`, PDF URL versioned by sha256 with `Cache-Control`; rebuild as
  a one-constant fallback decided by a manual Edge/Chrome check (chosen).**
- **B. Rebuild the iframe on every jump (today).** Re-opens a 4.9 MB PDF per click.
- **C. Vendored pdf.js.** Programmatic jumps and tag highlighting; several MB of vendored code — kept a Could.
- **D. One-page PDFs per sheet.** Instant, but loses scrolling and the flag links across sheets.

**8 — Hungarian labels**
- **A. One `labels.hu.json` table for every enum shown, plus a pytest that it covers every enum value; sentences in
  `strings.js`; the server sends codes (chosen).**
- **B. Translate in the server.** Mixes UI language into the API types.
- **C. Keep everything in `strings.js`.** No test can prove coverage without parsing JavaScript.

## Decision

1A, 2A, 3A, 4A, 5A, 6A, 7A, 8A. In addition, without a real alternative: tier runs `CYPL-*` → `CYPL2-*`
(ADR-0052); the paid cascade opens at corpus load when paid calls are allowed; the page states in Hungarian which
corpus Neo4j holds and that D100 is then answered by the agent alone ("not exactly the evaluated cascade").

## Rationale

No novelty is spent: each choice is the plainest one that keeps the frozen system untouched and the screen honest.
1A shows the user's own words to the system and nothing else, and keeps the examples identical to the evaluated
asks (free replay, real verdicts). 2A and 3A make D1000 run the evaluated two-tier cascade from the cache the
reported runs made — so what the defence shows is the system the EXP-0002 numbers describe. 5A and 6A put the
scale result on screen straight from the measured files, keeping the EXP-0001 and EXP-0002 question sets on
separate figures.

## Consequences

- D1000 examples replay free through both tiers; D100 examples replay free with the agent alone while Neo4j holds
  D1000.
- A typed question gets a short paragraph and no verdict; its behaviour is unmeasured beyond the EX01 sample and is
  never reported.
- The demo data folder gains `cache_luna_demo.sqlite` and `examples/*.jsonl`, each with a provenance sidecar.
- New sub-commands `seed-cache`, `examples`, `coverage`; the `coverage` report is the demo's self-check that every
  example replays free and equals the recorded answer.
- **Revisit if** fragment jumps fail in both browsers (→ 7C), the report JSON schemas change (the projection fails
  loudly), or the user asks for Hungarian D1000 examples (→ a `--wordings` mode and one paid warm-up pass).

## Outcome log
- **2026-10-12** Accepted by the user in chat ("Oké" to all four recommendations). The user added: in the demo the
  visitor should simply ask free questions — no answer form anywhere in the UI (U2 a). Open: whether the stored
  example questions should also be asked without their hidden answer form (that would make them paid misses and
  remove the automatic check) — asked in chat.
- **2026-10-12** DP-T1 committed by the user (`89f8dbe`). Server restarted on the new config: D1000 runs
  `cascade_v3` (tier1_store true); a D1000 benchmark question replayed from cache, $0, 0.56 s, correct.

- **2026-10-12** DP-T2 `7d4ef78`, DP-T3 `99ca994`, DP-T4 `6986e69` committed by the user. DP-T5 in the working tree.
- **2026-10-12** U1 carried out. 36 D1000 example wordings in Hungarian by a fresh agent with no repo access
  (`data/runs/cv1/demo/examples/D1000.hu.wordings.json`); every tag and unit number checked by regex against the
  English (0 mismatches); example file `D1000.hu.jsonl` via `examples --wordings`; config backup
  `demo_config.before_hu_d1000.json`. Paid warm-up through the demo (cascade_v3, Neo4j holding D1000): **$0.01865
  spent** (estimate was $0.026), 35/36 correct, answered by Cypher 27 / agent 9, median latency 7.5 s; the miss is
  UPSTREAM_ISOLATION TK-425-6 (Cypher tier accepted a wrong valve set — the known weak family). `coverage` after the
  warm-up: 36/36 cache hits, no misses; 31/36 answers equal the English recorded runs (expected to differ: different
  wording, not a regression measure).

**Superseded in part by ADR-0056 (2026-10-16): English demo; live only, no replay; explicit plant switch.**
