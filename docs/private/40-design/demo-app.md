---
component: demo application — drawing-set PDF export (one page per sheet) and a local web UI that answers questions through the cascade, replay-first, with guarded paid calls
status: draft — awaiting review
related: [ADR-0049 (proposed); ADR-0024 (what the demo is), ADR-0023 (flag style), ADR-0014 (paid-call guard), ADR-0048 + cascade-v2.md (tiers, 120 s cutoff)]
date: 2026-10-10
author: architect (Opus 5.5)
---

# Design — demo application and drawing-set export

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | Timing | Build now (user, 2026-10-10); **PDF export first** (DA-T1), then the live path, then the UI. |
| R2 | Drawing source | `CorpusArtifacts.localized_sheets` — the system's own input, visible properties only; never gold. |
| R3 | Layout | Pure-Python **layered layout** (cycle break → longest-path layers → dummy nodes → barycenter sweeps), instruments in a band above, flags on the sheet edges. No graphviz. |
| R4 | PDF | **fpdf2**, A3 landscape, one page per sheet, outline grouped by hundreds, flags are links to the target page, searchable text, deterministic bytes. Sidecar `drawings.index.json` (sheet → page, self-check report). |
| R5 | Web | **FastAPI + uvicorn**, one static HTML page with plain JS, the browser's PDF viewer in an iframe, jumps by `#page=N`. Bound to 127.0.0.1. |
| R6 | Answering | `qa/cascade/live.py`: a **lazy walk over `walk_question`/`decide`** (the offline policy code), 120 s cutoff carried across tiers. Same function behind a CLI `ask` subcommand. |
| R7 | Paid calls | Replay-only first; on a cache miss show an estimate; a paid call needs `--allow-paid-calls` on the server **and** a per-question confirmation, within a **session cap (default $0.50)**; demo cache and call log of its own; one question at a time. |
| R8 | Evidence | Gold-free "answer sheets" (sheets of the items named in the question and answer, from the resolved item graph) + "read sheets" from the trace; for benchmark questions also the gold evidence sheets, k, and correct/incorrect. All clickable → page. |
| R9 | Corpora | **D100 and D1000 now**; H100/H1000 only after the F1 freeze (user to confirm, §11 U1). |

ADR-0049 records R1–R7. Coder tasks DA-T1…DA-T5 (§10). No paid call in any task.

## 1. Evidence (all measured 2026-10-10, architect scratch, free and local)

| # | Finding | Source |
|---|---|---|
| E1 | Sheets have **no coordinates**. A localized sheet node carries `node_class`, `tag`, `unit_id`, `plant_id`, `loop_tag`, `measured_variable`, connector fields (`connector_number`, `referenced_drawing_number`, `line_number`, `fluid_code`); edges carry `relation`, `line_number`, `fluid_code`. Connector info lives on the stub nodes; the `connectors` list is cleared by `localize()`. | D100 rebuild via `qa/corpus.load_corpus_artifacts` |
| E2 | D100: 101 sheets, 16–62 symbols per sheet (median 42), 1–9 connectors (median 4), 4,212 symbols, 430 connectors; relations send_to 3,128, send_signal_to 557, measured_by 272, control 272. Sheet ids are `"0"`…`"100"` (string). | same |
| E3 | Layout shape (flow nodes, send_to edges): **D100** 7–20 layers (median 13), tallest column with dummy nodes 4–12, no cycles. **D1000** 6–28 layers (median 12), tallest column 3–14 (median 7), dummies per sheet 0–125 (median 9), instrument nodes 0–24 per sheet, **3 sheets with a cycle** (one reversed edge each), densest sheet 75 symbols. | scratch layering over all sheets |
| E4 | Rebuild time: D100 4.5–5.3 s; **D1000 45–47 s**, ready with graph view and item graph ≈ **50 s**; D1000 working set ≈ **585 MB** after load (peak 866 MB). | scratch timing, Win32 `GetProcessMemoryInfo` |
| E5 | **PDF prototype** (boxes, lines, labels, flags, outline, links; less than the final drawing): D1000 1,000 pages — **fpdf2 4.6 s, 2.47 MB**; reportlab 8.9 s (2.4 s layout), 3.31 MB. D100: fpdf2 0.5 s, 0.25 MB. Both PDFs open in pypdf with 1,000 outline entries; page text is extractable (search works). | scratch venv, fpdf2 2.8.9, reportlab 5.0.1 |
| E6 | Licences: fpdf2 LGPL-3.0-only, ships `py.typed`; reportlab BSD, no type info. Both pure-Python wheels on Windows. Graphviz binary **not installed** (`dot` not on PATH). | package metadata |
| E7 | First-cut rendering of D1000 sheet 464 (scratch PNG): readable, but unfilled boxes let lines strike through tags, straight long edges cross unrelated boxes, instrument labels were truncated and signal flags fell into the flow area. Fixed in §4.2–4.3 (filled boxes drawn after lines, dummy nodes, full labels, signal flags in the instrument band). | visual inspection |
| E8 | Per-question cost and latency, summed over the final and retrieval-side calls (no local compute): tier 1 `cypher_rag_plant` @ glm-low — CYP-D100-low (180 q) cost median $0.00022, p90 $0.00031, max $0.00251, latency median 4.8 s, p90 10.5 s; CYP-D1000-low cost median $0.00022, p90 $0.00035, max $0.00464, latency median 5.0 s, p90 11.3 s. Tier 2 `graph_agent` v2 pilot CV2-P1-D100 (**16 q only**): cost median $0.00069, p90 $0.00273, max $0.00371; latency median 10.5 s, p90 24.8 s, max 46.2 s. graph_agent v1 (QAR-P2, 90 q, no deadline): cost max $0.02588. | `data/runs/cv1/runs/*/answers.jsonl` (computed) |
| E9 | The experiment harness already has every safety piece the demo needs: replay-only client with a refusing transport (`harness/clients.py`), `SpendGuard` with reservations (`harness/spend_cap.py`), `UsageMeter` with a deadline (`harness/usage_meter.py`), `RequestTimedOut`/`TIMED_OUT` (CV2-T2). `FREE_TEXT` exists as an `AnswerType` with a format sentence in `final_answer.py`. | code read |
| E10 | `walk_question` (`qa/cascade/accept.py`) returns `missing_tier` when a tier has no row — exactly "which tier to run next" for a live walk. | code read |

## 2. Which part of the claim it serves

The demo is not evidence for the claim; it is the engineering deliverable the 2026-09-20 framing puts first — a
working system over a plant-scale drawing set — and the defence's one-screen view of it. Two things tie it to the
claim: (a) the 1,000-page PDF makes "plant scale" concrete and supplies the thesis figure of a sheet; (b) every
answer shows the tier that settled it, its latency and its cost, computed by the same code as the cascade report,
so the D100 → D1000 effect of ADR-0048 can be seen by hand. **Demo answers are never reported numbers** (own cache,
own log, `reported=False`).

## 3. Scope

- **Must (this note):** export D100/D1000 PDFs; pick a corpus → its PDF on the left; ask a typed question or pick a
  benchmark question on the right; answer with tier, latency, cost, evidence sheets (jump to page), k for benchmark
  questions; replay-first; paid only with flag + confirmation + session cap.
- **Should (later tasks, ADR-0024 log):** generate a plant and a question set from the UI; a "load into Neo4j"
  button (wipes the old plant, one-plant rule); read-through to the experiment caches; live tier progress beyond
  "tier N running".
- **Could:** start an evaluation run from the UI; vendored pdf.js with tag highlighting; unit-grouped outline;
  orthogonal edge routing.

## 4. Drawing-set export (`src/plantgraph/demo/drawing/`)

### 4.1 Input and output

```
input : corpus_id, path to ingest.json            (load_corpus_artifacts → localized_sheets, resolution)
output: <out>/<corpus_id>/drawings.pdf            one A3 landscape page per sheet
        <out>/<corpus_id>/drawings.index.json     DrawingIndex: sheet → page, outline groups, DrawingReport
default out: data/runs/cv1/drawings/              (git-ignored via data/runs/)
CLI   : uv run python -m plantgraph.demo.drawing --corpus D1000 --corpora-root data/runs/cv1/corpora --out data/runs/cv1/drawings
```

Only `localized_sheets` and `resolution` counts are read; the module must not import `GoldCorpusData` fields (added
to the existing AST import-ban test).

### 4.2 What a page shows

Each symbol class family has one glyph; every visible property is printed (the drawing is the system's input, made
visible). Labels are English, ASCII — fpdf2's core fonts are Latin-1 only and real flags read this way.

| Family (schema) | Glyph | Text |
|---|---|---|
| Equipment (`EQUIPMENT_CLASSES`) | white-filled rectangle | tag (bold), class name (small) |
| Valves (`VALVE_CLASSES`) | bow-tie (two triangles); check valve adds a bar | tag, class name (small) |
| Instrument functions (`ProcessInstrumentationFunction`, `ProcessSignalGeneratingFunction`, `ActuatingFunction`) | circle (ISA bubble), one outline style per class | loop tag (full), measured variable |
| Pipe flow (`send_to`) | solid black polyline, arrowhead at target | line number near the source end |
| Signals (`send_signal_to`, `control`, `measured_by`) | dashed blue polyline, arrowhead | — |
| Pipe connector In / Out | flag (rectangle with a point) on the **left / right** edge | `FROM DWG n` / `TO DWG n`, line number, fluid, own connector number (small); `referenced_connector_number` only if present (FULL style) |
| Signal connector In / Out | same flag in the instrument band, left / right | `FROM/TO DWG n`, loop tag |
| Page furniture | border; title block bottom right: corpus id, **DWG n**, units on the sheet, symbol count, "simplified generated drawing"; legend bottom left | |

### 4.3 Layout algorithm (`layout.py`, pure functions, deterministic)

1. **Partition** nodes: *flow* = equipment, valves, pipe connectors; *instrument* = instrument functions and signal
   connectors. Build the flow graph from `send_to` edges, nodes inserted in sorted id order (determinism).
2. **Break cycles** (E3: 3 D1000 sheets): repeat `nx.find_cycle`, reverse the cycle's last edge for layering only;
   mark it `is_back_edge` (drawn with its true direction).
3. **Layer** by longest path from sources; force pipe-In connectors to layer 0 and pipe-Out connectors to the last
   layer + 1.
4. **Dummy nodes** on every edge spanning more than one layer, so a long line runs through empty slots and never
   behind an unrelated box (fixes E7). Tallest column with dummies ≤ 14 on D1000 (E3).
5. **Order** inside each layer: start by natural tag order, then exactly **4 down/up barycenter sweeps** (fixed
   count — deterministic, standard).
6. **Coordinates:** flow band = lower ≈ 70 % of the drawing area; columns evenly spaced; one global row pitch, so
   rows align across columns. If `layers × min_column_pitch` exceeds the width, the whole drawing scales uniformly
   (`scale ≤ 1`, recorded per page; text never below 4 pt — estimate for 28 layers: scale ≈ 0.6).
7. **Instrument band** (upper ≈ 25 %): each instrument's x = mean x of its flow neighbours (two passes, so
   instrument→instrument chains settle), then a left-to-right sweep with a minimum gap over at most 4 rows. Signal
   flags at the band's left/right ends by direction.
8. **Edges** are polylines through their dummy points; lines are drawn first, symbols (white-filled) on top.

Output types are in §7. The layout knows nothing about PDF; the renderer knows nothing about graphs.

### 4.4 PDF assembly (`render_pdf.py`, fpdf2)

- `FPDF(orientation="L", unit="pt", format="A3")`, no auto page break; pages in **natural sheet order**
  (numeric ids as integers, others as strings).
- **Outline:** level 0 = groups of 100 pages ("DWG 0–99" …), level 1 = "DWG 464 — units 288, 289".
- **Links:** each flag whose target drawing is in the corpus is a link to that page (`add_link(page=…)` created for
  all pages before drawing). A target not in the corpus is drawn, not linked, and counted (`dangling_flags`).
- **Search:** text is real text, so the viewer's Ctrl+F finds "DWG 464", a tag or a line number.
- **Deterministic bytes:** fixed creation date and producer; two exports of one corpus are byte-identical (if fpdf2
  writes a random file `/ID`, override it with a hash of the corpus id and `source_graph_hash`).
- **Index sidecar** `drawings.index.json` (`DrawingIndex`, §7): sheet → page, the PDF's sha256, and the
  `DrawingReport`.

### 4.5 Self-measurement (`DrawingReport`)

Counts written to the sidecar and printed by the CLI: pages, symbols drawn, lines drawn, flags drawn, flags linked,
dangling flags, symbol-box overlaps, minimum page scale, layout seconds, render seconds. **Acceptance:** symbols drawn
= `resolution.n_occurrences`, flags drawn = `resolution.n_connectors`, lines drawn = edges of the localized sheets,
overlaps = 0. Fidelity is tested by extracting page text (pypdf): every tag, loop tag, flag target and line number of
a sheet appears on its page.

### 4.6 Usability at 1,000 pages

| Concern | Answer | Basis |
|---|---|---|
| Size | ≈ 2.5 MB prototype; final drawing adds arrows, labels and polylines — **estimate ≤ 6 MB** | E5 measured, factor estimated |
| Generation time | rebuild ≈ 47 s + layout and render ≈ 5–10 s → **≈ 1 min for D1000**, ≈ 6 s for D100 | E4, E5 measured; sum estimated |
| Finding a sheet | outline (bookmarks) grouped by hundreds; Ctrl+F on "DWG n"; in the app a "go to DWG" box | §4.4 |
| Following a line | click a flag → the target sheet's page | §4.4 |
| Opening | pypdf opens and reads page 518 in 0.5–1.0 s; browser viewers render lazily | E5 |

## 5. The live question path (library, `src/plantgraph/qa/`)

### 5.1 Unscored answering (small refactor, no behaviour change)

- `qa/strategies/base.py`: `answer_question` takes an **`AskedQuestion` Protocol** (`question_id`, `text`,
  `answer_type`) instead of `Question`; `Question` satisfies it unchanged.
- `qa/harness/attempt.py`: split `_attempt` into `run_unscored(...) -> UnscoredAnswer | ProviderError` (strategy,
  meter, deadline, `TIMED_OUT`) and the scoring step; `attempt` = both. Takes an `AttemptSettings` (run id, answer
  pin, context wall, primer) built from `RunConfig`, so the demo needs no fake `RunConfig`.
- `qa/cascade/signals.py`: `extract_signals` takes an `AnswerRow` Protocol (the fields it reads) so an
  `UnscoredAnswer` qualifies. **All existing harness and cascade golden tests stay byte-identical.**

### 5.2 Live cascade walk (`qa/cascade/live.py`)

```
signals = {}
loop:
    walk = walk_question(policy, qid, None, signals)
    if walk.missing_tier is None: break
    remaining = C − Σ latency of tiers tried          # C = 120 s, carried across tiers
    if remaining ≤ 0: stop (TIMED_OUT)
    row = run_unscored(tier strategy, asked, deadline=remaining)
    signals[tier][qid] = extract_signals(row, tier, pin, None)
decision = decide(policy, qid, None, signals)          # same code as the report → same tier, latency, cost
summed latency > C → outcome TIMED_OUT (as the report scores it)
```

- Tier settings (pin, strategy parameters, primer) come from a **tier source run's** `run_config.json`; the app
  refuses to start if `pin.pin_hash() != TierSpec.pin_sha256`. Policies with `start/last_tier_by_label` are refused.
- Strategies are built **once per corpus and client mode** (replay, paid) and reused; the paid set only exists when
  the server was started with `--allow-paid-calls`.
- `python -m plantgraph.qa.cascade ask --corpus D100 --policy cascade_v2 "…"` calls the same function (one code
  path, `qa-system.md` §18.1 item 1).

### 5.3 Clients and caches

- **Replay client** (default): `build_chat_client(allow_paid_calls=False)` over the demo cache
  `data/runs/cv1/demo/cache.sqlite`; a miss raises `CacheMiss` → the walk stops and returns `NeedsPaidCall` (no
  network: the refusing transport guarantees it).
- **Paid client**: same cache file in live mode, call log `data/runs/cv1/demo/calls.jsonl`. Experiment caches are
  never written (read-through to them is a Should).
- **Tier 1 store:** at load, `check_store_profile(plan, "plant")` + `open_checked_neo4j_view`. Only the corpus the
  store holds gets tier 1 (today D1000, index 2026-10-06). For another corpus the UI offers "tier 2 only", run as a
  derived policy named `<policy>-no-<tier>` and labelled "not the evaluated policy".

### 5.4 Evidence sheets (`demo/app/evidence.py`, gold-free)

- **Answer sheets** = for every tag in the final answer (TAG, TAG_SET, TAG_PATH; FREE_TEXT: tag-shaped tokens
  matched with the plant API's own tag matching) **and** in the question text: `ItemGraph.ids_for_tag` →
  `ItemRecord.sheets`. A yes/no or count answer thus shows its anchors' sheets.
- **Read sheets** = `trace.retrieval.routed_sheets` when the strategy records it (graph_agent does; Cypher does not).
- **Benchmark questions additionally:** gold `evidence_sheets`, `k`, `k_connector`, `k_identity`, `u`, the
  reference answer, and `correct` from `score_answer` — computed in the app layer, never passed to `live.py`.
- **Measured, not assumed:** `evidence_sheet_agreement(run_dir, questions, item_graph)` computes precision and
  recall of the gold-free answer sheets against gold `evidence_sheets` over a recorded run (free); DA-T3 reports it
  for CYP-D100-low and CV2-P1-D100 so the user knows how far the shown sheets match the true evidence.

### 5.5 Cost estimate and session cap (`demo/app/estimate.py`, `spend.py`)

- **Estimate** per tier from the corpus's recorded runs whose strategy and pin hash match the tier (E8): median and
  max per-question cost, with run ids and question counts; falls back to another corpus's runs, labelled. Shown as
  "tier 1 settles it: ≈ $0.0002 (median, CYP-D1000-low, 180 q); escalates: + ≈ $0.0007 (median), worst seen $0.0037
  (CV2-P1-D100, 16 q)" — the numbers are read from the files at run time, never typed in.
- **Reservation** for a confirmed question = 1.5 × Σ tiers' worst seen (E8 today: 1.5 × ($0.00464 + $0.00371) ≈
  $0.0125, computed); `SpendGuard.reserve` refuses if spent + reservation > cap.
- **Session cap** `--session-cap-usd`, required with `--allow-paid-calls` (as the harness requires a cap for a
  paid run), recommended **$0.50**. The header
  shows session spend / cap and the demo's all-time spend summed from `calls.jsonl` (budget: $25 total).

## 6. The app (`src/plantgraph/demo/app/`)

### 6.1 Process model

- `uv run python -m plantgraph.demo.app --config data/runs/cv1/demo/demo_config.json [--allow-paid-calls
  --session-cap-usd 0.50] [--port 8000]`; host fixed to 127.0.0.1.
- At start a background thread loads the configured corpora in order (D100 ≈ 5 s, D1000 ≈ 50 s, E4); the PDFs are
  served at once; asking is enabled per corpus when loaded.
- A question runs as a **job** in a worker thread; one job at a time (a lock; a second ask → 409). The job status
  holds the running tier, elapsed seconds and spend so far; the page polls it every second.

### 6.2 Endpoints

| Method, path | Returns |
|---|---|
| `GET /` | the static page |
| `GET /api/status` | `AppStatus`: corpora (loaded, PDF present, tier-1 store state), policy and tiers, paid allowed, `SpendStatus` |
| `GET /corpora/{id}/drawings.pdf` | the PDF (`application/pdf`, inline) |
| `GET /api/corpora/{id}/index` | `DrawingIndex` (sheet → page) |
| `GET /api/corpora/{id}/questions` | benchmark question list: id, family, text, answer type (no gold) |
| `GET /api/corpora/{id}/questions/{qid}` | `BenchmarkView`: reference, gold sheets as pages, k, recorded answers from the configured runs |
| `POST /api/ask` | `AskRequest` → `{job_id}`; 403 if `allow_paid` but the server lacks the flag; 409 if busy |
| `GET /api/jobs/{job_id}` | `JobStatus` |

### 6.3 Screen (UI strings Hungarian, one `STRINGS` object in `app.js`)

Left ≈ 60 %: the PDF iframe and a "DWG ___" go-to box. Right: corpus selector with load and tier-1 store status;
question box, answer-form selector (default free text), benchmark picker; **Ask**. While running: a ticking timer
and "tier N running". On a cache miss: a dialog with the estimate, session spend / cap, **Ask live** / **Cancel**.
Answer panel: the answer, outcome, "answered by tier N (strategy, model)", fallback marker, total latency (cascade
definition) and wall time, cost and "from cache" / "paid $x"; a per-tier table (outcome, accepted, latency, cost,
calls, cached, steps, stop reason, rows); evidence chips (answer sheets, read sheets, gold sheets for benchmark
questions) — **a click jumps the PDF to that page**; k and correct/incorrect for benchmark questions.

### 6.4 Jump to page

`iframe.src = "/corpora/D1000/drawings.pdf#page=" + page`. If the user's browser does not move on a hash-only
change, replace the iframe element (forces a reload of the local file; acceptable at a few MB). pdf.js is the Could
fallback (ADR-0049 option 5D).

## 7. Data model

```python
# demo/drawing/models.py
class PlacedSymbol(BaseModel):      # frozen
    node_id: str; family: Literal["equipment","valve","instrument","pipe_flag","signal_flag"]
    node_class: str; x: float; y: float; width: float; height: float; labels: tuple[str, ...]
    target_sheet: str | None = None # flags only (referenced_drawing_number)
class RoutedLine(BaseModel):        # frozen
    source: str; target: str; relation: str; points: tuple[tuple[float, float], ...]
    line_number: str | None = None; is_back_edge: bool = False
class SheetLayout(BaseModel):       # frozen
    sheet_id: str; units: tuple[str, ...]; scale: float
    symbols: tuple[PlacedSymbol, ...]; lines: tuple[RoutedLine, ...]
class DrawingReport(BaseModel):
    pages: int; symbols: int; lines: int; flags: int; flags_linked: int; dangling_flags: int
    overlaps: int; min_scale: float; layout_s: float; render_s: float
class DrawingIndex(BaseModel):
    corpus_id: str; pdf_sha256: str; pages: dict[str, int]   # sheet_id -> 1-based page
    report: DrawingReport

# qa/cascade/live_models.py
class TierReport(BaseModel):
    tier: str; strategy: str; model_id: str; outcome: Outcome; accepted: bool
    latency_s: float; wall_s: float; cost_usd: float; spent_usd: float
    n_calls: int; n_cached: int; n_steps: int | None; stop_reason: str | None; n_rows: int | None
class LiveAnswer(BaseModel):
    question_text: str; corpus_id: str; answer_type: AnswerType; policy: str
    outcome: Outcome; final_answer: FinalAnswer | None; answered_by: str | None; fell_back: bool
    tiers: tuple[TierReport, ...]; latency_s: float; wall_s: float
    cost_usd: float; spent_usd: float; from_cache: bool; trace_sheets: tuple[str, ...]
class NeedsPaidCall(BaseModel):
    missing_tier: str; reason: str

# demo/app/models.py
class SheetLink(BaseModel): sheet_id: str; page: int; tags: tuple[str, ...]
class CostEstimate(BaseModel): per_tier: dict[str, TierCostStats]; reservation_usd: float
class TierCostStats(BaseModel): median_usd: float; max_usd: float; n_questions: int; run_ids: tuple[str, ...]; other_corpus: bool
class SpendStatus(BaseModel): session_spent_usd: float; session_cap_usd: float | None; demo_total_spent_usd: float
class AskRequest(BaseModel): corpus_id: str; text: str; answer_type: AnswerType = AnswerType.FREE_TEXT
    benchmark_question_id: str | None = None; allow_paid: bool = False; tier2_only: bool = False
class DemoAnswer(BaseModel): live: LiveAnswer; answer_sheets: tuple[SheetLink, ...]; read_sheets: tuple[SheetLink, ...]
    benchmark: BenchmarkView | None
class JobStatus(BaseModel): job_id: str; state: Literal["running","done","needs_paid","refused","error"]
    running_tier: str | None; elapsed_s: float; result: DemoAnswer | None
    needs_paid: NeedsPaidCall | None; estimate: CostEstimate | None; spend: SpendStatus; message: str | None

# demo/app/config.py
class DemoCorpus(BaseModel): corpus_id: str; ingest_json: Path; drawings_dir: Path
    questions_jsonl: Path | None = None; recorded_runs: tuple[Path, ...] = ()
class TierSource(BaseModel): tier: str; run_dir: Path        # run_config.json → pin, params, primer
class DemoConfig(BaseModel): corpora: tuple[DemoCorpus, ...]; policy: str
    tier_sources: tuple[TierSource, ...]; question_deadline_s: float = 120.0
    cache_path: Path; calls_log_path: Path
```

## 8. Files

```
src/plantgraph/demo/__init__.py                 what the demo package is
src/plantgraph/demo/drawing/{__init__,__main__,models,layout,layering,glyphs,render_pdf,export}.py
src/plantgraph/demo/app/{__init__,__main__,config,models,state,server,evidence,estimate,spend}.py
src/plantgraph/demo/app/static/{index.html,app.js,app.css}
src/plantgraph/demo/app/demo_config.example.json
src/plantgraph/qa/cascade/{live,live_models}.py ; edits: qa/strategies/base.py, qa/harness/attempt.py, qa/cascade/{signals,cli}.py
tests/test_demo_{layout,render_pdf,export,evidence,estimate,app}.py, tests/test_cascade_live.py
```

## 9. Tests and self-measurement (summary)

Unit tests without Neo4j or network everywhere (fake transport, stub `CypherSource`, toy sheets); optional local
checks skip when `data/` is absent. Self-measurement: `DrawingReport` (export), `evidence_sheet_agreement`
(answer sheets vs gold), and the per-tier report of every answer (latency, cost, cached). The live decision is
tested equal to `decide()` on the same signals.

## 10. Coder tasks (Sonnet, one at a time; ruff, `mypy --strict`, pytest green; offline; no paid call)

| # | Task | Files | Tests / acceptance | Size |
|---|---|---|---|---|
| **DA-T1a** | **Sheet layout (pure).** §4.3 steps 1–8 | `demo/__init__.py`, `demo/drawing/{__init__,models,layering,layout}.py`, `tests/test_demo_layout.py` | toy sheets (chain, branch, cycle, pipe In/Out flags, instruments, signal flags): same input → identical layout; In flags at min x, Out flags at max x, signal flags in the band; no two symbol boxes overlap; every edge routed once, ends on its symbols, no segment crosses a non-endpoint box; the cycle yields exactly one `is_back_edge`; optional local: all 101 D100 sheets, 0 overlaps | M |
| **DA-T1b** | **PDF renderer and export CLI.** §4.2, §4.4, §4.5. `uv add fpdf2`, `uv add --dev pypdf` | `demo/drawing/{glyphs,render_pdf,export,__main__}.py`, `tests/test_demo_render_pdf.py`, `tests/test_demo_export.py`, AST ban test extended | small synthetic corpus: pages = sheets; each page's text has "DWG n", every tag, loop tag, flag target and line number of that sheet; outline groups + one entry per sheet; one link per in-corpus flag, pointing at the right page; dangling flag drawn, unlinked, counted; two exports byte-identical; report counts = `n_occurrences`, `n_connectors`, edges; **then the user runs the CLI for D100 and D1000 (free, ≈ 1 min) and gets the PDFs** | M |
| DA-T2 | **Unscored answering and the live cascade.** §5.1–5.3 | `qa/strategies/base.py`, `qa/harness/attempt.py`, `qa/cascade/{signals,live,live_models,cli}.py`, `tests/test_cascade_live.py` | every existing harness/cascade golden test unchanged; fake transport + stub Cypher: tier 1 accepted → tier 2 never called; 0 rows → tier 2 runs with deadline C − tier-1 latency; tier 2 PARSE_FAILURE after tier 1 ANSWERED → fallback to tier 1; summed latency > C → TIMED_OUT; replay mode cache miss → `NeedsPaidCall`, refusing transport never hit; live decision == `decide()` on the same signals (several toy cases); pin-hash mismatch and label-routing policy refused; AST ban: `live.py` imports no gold module; `ask` CLI prints the answer and tier table | M/L |
| DA-T3 | **Evidence sheets, estimate, spend.** §5.4–5.5 | `demo/app/{evidence,estimate,spend,models}.py`, `tests/test_demo_{evidence,estimate}.py` | toy item graph: TAG_SET → union of item sheets; BOOLEAN → anchors' sheets; FREE_TEXT finds tags with the plant API's matching; estimate from toy `answers.jsonl` = median/max with run ids; fallback corpus labelled; reservation refuses over the cap; all-time spend summed from a toy `calls.jsonl`; **report** `evidence_sheet_agreement` precision/recall on CYP-D100-low and CV2-P1-D100 (free, local; printed, not gated) | S/M |
| DA-T4 | **App server.** §6.1–6.2. `uv add fastapi uvicorn`, `uv add --dev httpx` | `demo/app/{config,state,server,__main__}.py`, `demo_config.example.json`, `tests/test_demo_app.py` | TestClient with fakes: status lists corpora and loading state; PDF served inline; index; question list carries no gold; detail carries reference, gold pages, k, recorded rows; ask without paid on a miss → `needs_paid` with estimate; `allow_paid` without the server flag → 403; second ask while running → 409; job → `done` with `DemoAnswer`; benchmark question gets `correct`; host is 127.0.0.1 | M |
| DA-T5 | **The page.** §6.3–6.4 | `demo/app/static/{index.html,app.js,app.css}`, smoke test in `tests/test_demo_app.py` | static files served; every API path in `app.js` exists in the router (string check); manual checklist reported in the chat: jump to page in Edge and Chrome (fallback if needed), go-to-DWG box, confirmation dialog shows estimate and spend, timer, tier table, chips jump | M |

Order: DA-T1a → DA-T1b (user gets the PDFs) → DA-T2 → DA-T3 → DA-T4 → DA-T5. **CV2-T5** (`cascade_v2.json`)
must land before the first real use of DA-T4; DA-T2's tests use a toy policy and do not wait for it.

## 11. Open user decisions (recommendation first)

- **U1 Corpora:** D100 (101 sheets) and D1000 (1,000) now; H100/H1000 PDFs and questions only after F1 — testing
  by hand on the sealed test plants before the freeze would let what you see shape the system. Recommended.
- **U2 Session cap $0.50** and a confirmation for **every** paid question. Recommended (≈ 40 questions even at the
  conservative reservation, E8).
- **U3 UI in Hungarian, drawings in English labels** (Latin-1 core fonts; real flags read "TO DWG …"). Recommended.
- **U4 Neo4j holds D1000.** Keep it; D100 then runs "tier 2 only", clearly labelled; switching needs a reload (the
  one-plant rule). Recommended.
- **U5 Timing:** the demo before the headline (your request) — recorded in ADR-0049. Confirm.

## 12. Risks (not for the user)

- **O1** Hash-only iframe navigation in Chromium may not move the page; fallback in §6.4, pdf.js as Could.
- **O2** All tiers were measured on typed answer formats; behaviour with `FREE_TEXT` (tier-1 acceptance, parse
  rate) is unmeasured. The UI shows the answer-form selector next to the question.
- **O3** Free-hand testing on dev corpora can still steer tuning; any change it prompts goes through the normal
  dev process and is logged.
- **O4** The tier-2 estimate rests on 16 pilot questions (E8); it is replaced by the V2-D1000 run once it exists
  (the estimator reads whatever runs the config lists).

## 13. Figures and sources

| Figure | Source |
|---|---|
| E1–E4, E7 | architect scratch over `load_corpus_artifacts("D100"/"D1000")`, 2026-10-10 — computed |
| E5, E6 | scratch venv (fpdf2 2.8.9, reportlab 5.0.1, pypdf 6.20.0), same machine, 2026-10-10 — measured on a prototype, not on the final renderer |
| E8 | `data/runs/cv1/runs/{CYP-D100-low,CYP-D1000-low,CV2-P1-D100,QAR-P2-D100}/answers.jsonl` — computed |
| Size ≤ 6 MB, ≈ 1 min export, scale ≈ 0.6, reservation ≈ $0.0125 | arithmetic on the rows above — **estimates** |
