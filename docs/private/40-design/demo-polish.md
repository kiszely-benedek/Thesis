---
component: demo polish — revision 1 (one plain question box, label table, result card, PDF jump, results tab, wiring fixes); revision 2 (English, live-only answering with the plant loaded into Neo4j per ask, the ask's trace, a design system, engineer tools, intro, glossary, other-plant comparison, presentation mode, answer diagram)
status: revision 2 — draft, awaiting review (revision 1 accepted with ADR-0055 on 2026-10-12)
related: [ADR-0055 (accepted; superseded in part by ADR-0056); ADR-0056 (accepted 2026-10-16, revision 2); ADR-0049 (proposed) and demo-app.md (what is polished); ADR-0024; ADR-0053 F1 freeze; ADR-0054 / EXP-0001; EXP-0002]
date: 2026-10-12 (revision 1), 2026-10-16 (revision 2)
author: architect (Opus 5.5)
---

# Design — polishing the demo app

## Revision 2 (2026-10-16) — what changed and why

The user asked (2026-10-16) for a page that is *"as user-friendly, beautiful and understandable for a
non-specialist as possible — use proper CSS, it should feel good to use"* **and** genuinely useful for a P&ID
engineer, and accepted five extra ideas: a "what is this?" intro box, glossary tooltips, the same question on the other plant, a
presentation mode for the defence, and a small path diagram. Money for live questions is not a concern (the local
session cap is already $5.00, `demo_config.json`). DP-T1…DP-T5 are committed (last `ce9bb60`); nothing below
changes them. Sections 0–16 are revision 1, kept as written; where revision 2 changes them, a **[rev 2]** note says
so in place.

**Language — the demo is now English (user decision 2026-10-16: demo in English).** Everything visitor-facing on
the page is English and the example questions are English. This supersedes every "Hungarian" part of revision 1:
P8 (Hungarian examples), P9 (`labels.hu.json`, Hungarian sentences), §5.1 screen texts, §6 drafts, §7 card texts and
the hu-HU money format, and U1, U3, U4 (§14). The codes, the sections of the label table and its coverage test stay;
only the language and the file name change (§18). The chat with the user and the thesis stay Hungarian. For the
record: PARA-R1 measured Hungarian rewordings at least as well answered as English ones through `cascade_v3` on
D100 (hu 142/144, en 102/108, `_results.md`); the switch is an audience choice, not an accuracy one.

**Live only — no cache replay, ever (user decision 2026-10-16).** Every question, examples included, runs live
through the evaluated cascade (Cypher tier first, then the agent if the first answer is not accepted). The user
rejects stored answers that come back in a fraction of a second when the measured median is several seconds: it
misrepresents the system. This supersedes P1's replay role (the merged cache is no longer read), P5 (an eager paid
open at load; now a fresh cascade per ask, §17.1), P7's "replay is free" rationale (the FREE_TEXT rule itself
stays), P8's "free replay" selection reason, §7 item 2's "stored answer (instantly)" fact line, §12's replay
coverage as the demo's self-check, DP-T1/DP-T2's role in the demo story, and the `needs_paid` / `--replay-only`
path. It also removes the agent-only D100 mode: the visitor selects a plant, which loads it into Neo4j, and then
asks questions about that plant (§17.2).

| Change | Where | Why |
|---|---|---|
| Live-only answering: a fresh live cascade with an empty in-memory cache per ask; one live path in `run_job`; replay sub-commands and `--replay-only` retired | §17.1, §17.4, DP-T12 | user decision 2026-10-16 |
| An explicit plant switch: selecting a plant wipes Neo4j and loads it, with a visible phase; asks never reload | §17.2, DP-T13 | the user's model: one plant chosen deliberately, then all questions to it |
| The real trace of every ask, recorded verbatim by a demo-owned HTTP transport (query, rows as the model saw them, tool calls, observations), and an interactive route view | §17.3, §21.5, DP-T14, DP-T18, DP-T19 | the user's high-priority "how the model got there" |
| Demo language English: label table renamed `labels.en.json`, English strings, English example files, en-US money format | §18, DP-T11 | user decision 2026-10-16 |
| A visual design system (tokens, two themes, components) | §19 | the user's "proper CSS"; lands in DP-T6, so the first try after DP-T7 has the new look |
| Engineer tools: tag lookup, clickable tags in answers, copy button (session history dropped by the user); plain-English class names (rev 1's Should) promoted to Must | §20 | "useful for a P&ID engineer"; every value comes from data the demo already holds (§20.1) |
| The extra ideas specified: intro, glossary, presentation mode, route view; the other-plant comparison dropped | §21 | user decisions 2026-10-16 |
| API changes (all inside `demo/`) | §22 | |
| k / u explanation corrected | §7 item 5 note, §21.2 | revision 1 said "k: ennyi lapot kell összekötni"; `Question.k` counts **evidence edges whose two ends have different home sheets** (`qa/models.py`), not sheets |
| DP-T8's header test moves to a new file | §25 | `tests/test_demo_app.py` is exactly 400 lines (`wc -l`, 2026-10-16) |
| Coder tasks re-cut: DP-T6…DP-T10 keep their numbers; DP-T11…DP-T20 new (DP-T11 done, DP-T17 dropped); DP-T12…DP-T14 run before DP-T6, DP-T18/T19 right after DP-T7 | §25 (replaces §13's DP-T6…DP-T10 rows) | one commit each, S/M, ≤ 400 lines per file |

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| P1 | Cache **[rev 2: superseded — live only, the demo reads no cache, §17.1]** | A **demo-owned merged copy** `data/runs/cv1/demo/cache_luna_demo.sqlite` = `cache_luna.sqlite` ∪ the old demo cache, written once by a small CLI with a provenance sidecar. Experiment caches are never written. |
| P2 | Cypher tier | Point each corpus's `ingest_json` at the **plant-profile** file `data/runs/cv1/neo4jplant/<id>/ingest.json`. Config-only; no new field. Verified: it rebuilds the same sheets (E2, E3). |
| P3 | Tier runs | `CYPL-D*` → `CYPL2-D*` (ADR-0052 canonical row order). |
| P4 | Store state **[rev 2: the page now loads the plant instead of explaining agent-only, §17.2]** | The demo reads which corpus Neo4j holds (one read query) and reports a typed `StoreState`; the page says in Hungarian why D100 runs with the agent only. |
| P5 | Cold start **[rev 2: superseded — a fresh cascade per ask, §17.1]** | Open the paid cascade **at corpus load** when paid calls are allowed, not on first use. |
| P6 | Asking | **One question box.** Example questions (natural wording, no ids, no family codes) listed by plain-language topic; a click fills the box. No answer-form selector. |
| P7 | Answer type **[rev 2: rule kept; the replay reason is void]** | Typed text → **FREE_TEXT** always. An example asked unchanged keeps its stored answer type, hidden (that is what makes its replay free and its verdict possible). |
| P8 | Examples **[rev 2: superseded by P8′]** | D100: the **hu1** Hungarian wording of the 36 PARA-R1 base questions (free replay, E2). D1000: 36 English dev questions (same sampling rule) until the user decides U1. |
| P9 | Hungarian **[rev 2: language superseded by P9′]** | Every enum the page shows (outcome, stop reason, tier, strategy, topic, store state, job state, error code) is translated in **one JSON table** `static/labels.hu.json`, with a pytest that it covers every enum value. Sentences stay in `strings.js`. The server sends codes, never English text meant for the user. |
| P10 | Result card | Big answer → "Honnan tudja?" sheet chips → reference and verdict (examples only) → **Részletek** (folded: tier table, both time figures, k/u, technical message) → **Hogyan működik?** (folded). |
| P11 | PDF | One persistent iframe; a jump changes only `#page=N`; the PDF URL is versioned by its sha256 and served with `Cache-Control`. Rebuilding the iframe stays as a one-constant fallback. pdf.js highlighting stays a Could. |
| P12 | Results tab | `GET /api/results` projects the two **`report.json`** files (no extraction copy, no typed numbers) with provenance; `charts.js` draws inline SVG (no CDN, no build step). Four figures; EXP-0001 and EXP-0002 never on one axis. |

ADR-0055 records P1, P2, P7, P8, P11, P12 and the label/chart technology. Coder tasks DP-T1…DP-T10 (§12). No paid call in any coder task.

**[rev 2] added recommendations** (ADR-0056, accepted 2026-10-16):

| # | Item | Decision |
|---|---|---|
| P19 | Live only | Every ask opens a fresh live cascade whose model clients use a private, empty in-memory cache (`Path(":memory:")`); no cache file is ever read; a per-call `from_cache` guard proves it (§17.1). |
| P20 | Plant in Neo4j | Selecting a plant is the load: wipe the held plant, `load_corpus` with the plan the demo already built, a visible phase with its measured time; asking disabled meanwhile; an ask never reloads (`plant_not_loaded`); the demo starts on the plant Neo4j holds (§17.2). |
| P21 | Ask trace | A demo-owned recording HTTP transport keeps every request and response of the ask: the Cypher query and the rows as the model saw them, each agent tool call with its arguments and observation; joined with the call log for cost and cache flags (§17.3). |
| P8′ | Examples (supersedes P8) | English: D100 = the 36 English originals of the PARA-R1 base (`paraphrase_base_D100.json`; all are D100 dev questions with byte-equal text), D1000 = the existing `examples/D1000.jsonl` (36 English dev questions, per-family 2, seed 20261011). Asked live like any question; reference and verdict kept (§18). |
| P9′ | Labels (supersedes P9's language) | Same codes, sections and coverage test; English texts; file renamed `static/labels.en.json` (§18). |
| P13 | Look | A "title-block" design system: CSS custom-property tokens, light and dark themes (system preference by default, a manual three-way toggle), system fonts only, WCAG AA contrast computed per token pair (§19). |
| P14 | Engineer tools | Tag lookup over the loaded item graph (no model call); clickable tags and sheet ids inside answers; copy button; plain-English class names (§20). Session history dropped. |
| P15 | Intro + glossary | A dismissible "What is this?" box; glossary terms as focusable inline terms with one shared tooltip, texts in `labels.en.json` `glossary` (§21.1, §21.2). |
| P16 | Same question on the other plant | **Dropped** (user, 2026-10-16): it needs both plants in one interaction — no bouncing (§21.3). |
| P17 | Presentation mode | Confirmed: large type and a step bar over sequences in the local `demo_config.json`, one plant per sequence, every step asked live (§21.4). |
| P18 | Route view | Interactive inline SVG of the route the system actually took: items the model saw, step by step, with the direct drawing edges between them; the answer and its path highlighted; hover for tag, class, sheets; click to jump the PDF (§21.5). |

## 1. Evidence (2026-10-12, architect scratch, free and local)

| # | Finding | Source |
|---|---|---|
| E1 | The LLM cache key is a hash of **pin + json_mode + messages** only; run id, question id and purpose are not in it. A replay hits iff the prompts are byte-identical. | `llm/cache.py` `cache_key` |
| E2 | **Replay through `open_live_cascade`** on a scratch copy of `cache_luna.sqlite`, ingest = plant-profile file, replay-only client: **D1000** (Neo4j holds D1000, Cypher tier opened): dev 180/180 hits, policy `cascade_v3` with both tiers, answered by cypher-luna 120 / agent-luna 60, **180/180 final answers equal** to `CYPL2-D1000` / `AGL3-D1000`; 180 asks took 14.8 s wall in total, the first 0.87 s; corpus rebuild 20.2 s. **D100** (store holds D1000 → `cascade_v3-no-cypher-luna`): dev 180/180 hits, 180/180 equal to `AGL3-D100`; PARA 252/252 hits (251 answered by the agent, 1 with no tier answer), 251/251 equal to `AGL3-PARA-D100`; rebuild 1.8–1.9 s. | scratch `replay_check.py` |
| E3 | `corpora/D*/ingest.json` (occurrence) and `neo4jplant/D*/ingest.json` (plant) differ only in `store_profile`, counts, timings, `load_report`, `neo4j_version` and the **order** of the `equipment_classes` set; generator and split configs are equal, so `load_corpus_artifacts` rebuilds the same sheets (E2 confirms: every agent prompt hit). Plant D1000 counts 37,124 nodes / 111,668 relationships = what Neo4j holds. | JSON diff |
| E4 | `cascade_v3` accept rules: tier 1 `[answered, not_abstained, rows]`, tier 2 `[answered]`. `is_accepted` reads `Signals` only (outcome, n_rows, not_present) — **not the answer type**. The answer type acts twice: the fixed format sentence in the final prompt and the shape check (`FREE_TEXT` must be a string; a JSON list → `PARSE_FAILURE` → tier 1 not accepted). | `qa/cascade/accept.py`, `policies/cascade_v3.json`, `qa/final_answer.py` |
| E5 | The only measured `FREE_TEXT` asks: EX01 (EXP-0001), 5 ChatP&ID questions × 3 repeats, English, one 39-node plant. **0 parse failures in 90 answers.** Cypher arm: 10 ANSWERED (8 with rows > 0 and not abstained, i.e. tier-1 acceptable; 2 abstained), 5 RETRIEVAL_ERROR. n = 15 per arm: shows FREE_TEXT does not break parsing; says nothing about Hungarian or about plant scale. | `data/runs/exp0001/ex01/answers.jsonl` |
| E6 | Both result reports exist as JSON. `exp0001/report/report.json`: `sizes` (H1, H3, H10, H30 with **n_sheets 1, 4, 10, 30** — H3 has 4 sheets), `cells` (corpus × arm × scope: n, Wilson `acc_at_120`, `cost_mean`, `latency_median`), `wall_sheets` 142.53, `scope_families.common` 19 families; `ctx-low` absent at H3 and H30. `sealed/report/report.json`: `sealed.sheets` {H100: 100, H1000: 1001}, `sealed.scope_rows` (corpus × scope × policy: Wilson `accuracy`, `summary.cost_per_question_usd`, `summary.latency_median_s`, `latency_p90_s`, `n_questions`, `n_correct_at_cutoff`). | file read |
| E7 | The PDF route sends `ETag`, `Last-Modified`, `Accept-Ranges`, no `Cache-Control`; D1000 PDF 4,930,374 bytes. `drawings.index.json` carries `pdf_sha256` and pages (D100 101, D1000 1,000). | `curl` on the running server (GET only), index files |
| E8 | Running server: both corpora `tier1_store: false`, tiers `[agent-luna]`; demo `calls.jsonl` 41 calls, 6 paid, $0.00054902. | `GET /api/status`, calls log |
| E9 | `CascadePool` opens the replay cascade in `__init__` and the paid one on first `asker(paid=True)`; `run_job` tries replay first, then paid. This is where the caller's measured 14.1 s first-question wall vs 5.9 s tier latency comes from. | `demo/app/cascade_pool.py`, `jobs.py` |
| E10 | The system never sees the family label: retrieval gets `question.text`; the final step also gets `answer_type`, used only for the format sentence and shape check. | `answering.py`, `final_answer.py` |

## 2. Which part of the claim it serves

None directly — the demo is the defence's one-screen view of the deliverable (ADR-0024, ADR-0049 §2). Two items do
touch the claim: the **Eredmények** tab shows the measured scale effect (EXP-0001 ladder, EXP-0002 H100 → H1000)
read from the report files, and the D1000 corpus now runs the **evaluated** cascade (both tiers), so what is shown
live is the system the numbers describe. Demo answers stay unreported (own cache, own log).
**[rev 2]** Live only: every ask now runs the evaluated cascade with real calls, on either plant (§17), so the
screen shows the real latency and cost a visitor would get. Demo answers stay unreported (own call log, no cache).

## 3. Scope

- **Must:** P1–P12.
- **Should:** Hungarian class names in answers (`CentrifugalPump` → "centrifugálszivattyú"), via the same label table.
  **[rev 2]** promoted to **Must** (DP-T7) as **plain-English** names (`CentrifugalPump` → "centrifugal pump"),
  because the tag lookup and the diagram show classes too (§20).
- **Could:** vendored pdf.js with tag highlighting; a "load this plant into Neo4j" button (one-plant rule).
  **[rev 2]** the plant load becomes a Must, as the explicit plant switch (§17.2). Adds to Could: a demo-computed
  "path check" (shortest path between the asked items, clearly
  labelled as not the system's answer) — rejected for now (§21.5).
- **[rev 2] Must also:** §17 live-only answering, plant switch and recorded trace; §18 English; §19 design system;
  §20 engineer tools; §21 intro, glossary, presentation mode, route view.
- **Out:** any change outside `src/plantgraph/demo/`, demo tests and `data/runs/cv1/demo/` (F1 freeze); translating
  model answers; inferring answer types.

## 4. Wiring fixes

### 4.1 Cache (P1)

**[rev 2]** Superseded: the demo no longer reads this file (live only, §17.1). It stays on disk as an archive.

`python -m plantgraph.demo.app seed-cache --from data/runs/cv1/cache_luna.sqlite --from data/runs/cv1/demo/cache.sqlite --out data/runs/cv1/demo/cache_luna_demo.sqlite`

- Opens every source read-only (`file:…?mode=ro` URI — the old demo cache may be open in the running server).
- Copies the `responses` table of the first source, then `INSERT OR IGNORE` from the next ones (same key = same
  request, E1, so the first source wins; the experiment's response is the one the reported answer came from).
- Refuses an existing `--out`. Writes `<out>.provenance.json`: sources with sha256 and row counts, rows written,
  rows skipped as duplicates, date.
- `demo_config.json`: `cache_path` → the new file; `calls_log_path` unchanged (all-time demo spend stays continuous).
  The old `cache.sqlite` stays as an archive.

### 4.2 Store ingest (P2, P3)

`demo_config.json` per corpus: `ingest_json` → `data/runs/cv1/neo4jplant/<id>/ingest.json`; `tier_runs` and
`recorded_runs` → `CYPL2-<id>`, `AGL3-<id>` (+ `CYPL2-PARA-D100`, `AGL3-PARA-D100` in D100's `recorded_runs`).
The `DemoCorpus.ingest_json` docstring says: *"the ingest file of the store's load (plant profile); it also rebuilds
the sheets the drawing and the agent use"*. `demo_config.example.json` is updated to the same shape.

### 4.3 Store state (P4)

`demo/app/store_probe.py`:

```python
def held_corpus_ids(settings: Neo4jSettings) -> tuple[str, ...]          # MATCH (d:DrawingSet) RETURN d.corpus_id
def store_state(policy, plan: LoadPlan, corpus_id, tier1_opened: bool,
                probe: Callable[[], tuple[str, ...]]) -> StoreState     # pure decision, unit-tested
```

| kind | when | page text (Hungarian, `labels.hu.json`) |
|---|---|---|
| `ready` | tier 1 opened | "Mindkét lépés elérhető." |
| `holds_other` | store holds another corpus | "A gráfadatbázisban most a {held} üzem van; egyszerre csak egy üzem lehet benne. Ezen az üzemen ezért csak a gráfbejáró ügynök válaszol — ez nem pontosan az értékelt kaszkád." |
| `empty` | no DrawingSet | "A gráfadatbázis üres …" |
| `wrong_profile` | `plan.profile` ≠ the Cypher tier's profile | "A beállított ingest-fájl nem az adatbázis-lépés profiljával készült …" |
| `mismatch` | holds this corpus, but counts differ | "A gráfadatbázisban lévő üzem nem egyezik a beállítottal …" |
| `unreachable` | no settings or driver error | "A gráfadatbázis nem érhető el …" |
| `not_needed` | policy has no Cypher tier | (nothing shown) |

`CorpusStatus` gains `store: StoreState` and `n_sheets: int | None` (pages in the drawing index). `tier1_store`
stays for compatibility. The raw `LiveAnswer.notice` is no longer shown to the user (§6).

### 4.4 Cold start (P5)

**[rev 2]** Superseded by the per-ask cascade (§17.1); the open time is now shown per ask.

`CascadePool.__init__` also opens `(paid=True, tier2_only=False)` when `allow_paid_calls`, and logs the seconds
each open took. The background loader absorbs it; the first paid question then pays only for its calls.
**Measured by:** `CorpusStatus.open_s` (dict mode → seconds) shown under Részletek in the status line, and the
manual check "first paid question: wall − tier latency" reported in the chat after DP-T3.

## 5. Asking (P6–P8)

### 5.1 Screen

**[rev 2]** Same structure, English texts ("Question", "Ask", "Example questions (36)", topic headings in
English); the placeholder is still the first example's text, now English (§18).

```
[ 101 lapos üzem (D100) ▾ ]   ⓘ store text if not ready
┌ Kérdés ─────────────────────────────────────────┐
│ (textarea, placeholder: "Pl. Eljuthat az anyag a TK-3-3-ból a T-47-4-be?") │
└─────────────────────────────────────────────────┘
[ Kérdezés ]   timer
▸ Példakérdések (36)          ← <details>, open by default until the first ask
   Útvonalak az üzemen át      · question text (button) …
   Előtte és utána: szomszédok, források, elzárás
   Műszerek és szabályozókörök
   Tételek, egységek és rajzlapok
```

- The placeholder is the text of the corpus's first example (never typed by hand).
- Clicking an example fills the box and remembers `example_id`. Any edit that makes the text differ clears it.
- Corpus label: `"{n_sheets} lapos üzem ({corpus_id})"`, `n_sheets` from the drawing index.
- Topic of an example = `family_topics[family]` in `labels.hu.json`; topic order fixed in the same file.

### 5.2 Request and server rule

```python
class AskRequest(BaseModel):          # replaces the current one
    corpus_id: str
    text: str                         # required, non-blank
    example_id: str | None = None     # an example the text came from
    tier2_only: bool = False
```

`asked_question`: if `example_id` names an example **and** `text.strip() == example.text.strip()` → the example
itself (stored answer type, gold available, replay hits). Otherwise → `FreeTextQuestion.from_text(text, FREE_TEXT)`.
The server decides; the page cannot send a mismatched pair. `answer_type` leaves the request.

### 5.3 Why FREE_TEXT for typed questions (P7)

- Acceptance does not read the answer type (E4); FREE_TEXT only loosens the shape check to "a string". The single
  measured sample has 0/90 parse failures (E5).
- A rule-based type guess that is wrong forces a wrong shape (a list demanded for a yes/no question) → parse failure
  or a misleading answer. The closest measured rule system, the need classifier, recognised 6 of 36 Hungarian
  rewordings (PARA-R0, `_results.md`); a type rule would face the same wording spread.
- An LLM type guess adds a paid, unevaluated call to every typed question.
- The cost: a typed question's answer is a short paragraph, not a scored value, and has no verdict — which is right
  for a question nobody has a reference for.

### 5.4 Example files (P8)

`python -m plantgraph.demo.app examples --from <questions.jsonl> (--variant hu1 | --per-family 2 --seed 20261011) --corpus <id> --out data/runs/cv1/demo/examples/<id>.jsonl`

- Writes plain `Question` lines (same schema as `questions.jsonl`, gold kept) and `<out>.provenance.json` (source
  sha256, rule, count). `questions_jsonl` in the config points at this file, so the loader is unchanged.
- D100: `--from data/runs/cv1/para/D100/questions.jsonl --variant hu1` → 36 Hungarian questions (replay: E2).
- D1000: `--from data/runs/cv1/questions/D1000/questions.jsonl --per-family 2 --seed 20261011` → 36 English
  (replay: E2). If U1 = yes, a third mode `--wordings <json>` swaps in Hungarian texts made by the PARA-R0
  procedure (blind Sonnet rewording, tags checked by regex), keeping each question's gold.

## 6. Hungarian everywhere (P9)

**[rev 2]** Superseded in language (user decision 2026-10-16: demo in English): the table becomes
`static/labels.en.json` with English texts; the codes, sections, the "missing key shows the raw value and warns"
rule, the error-code mechanism and the coverage test stay. The Hungarian drafts below are kept for the record only.

- `static/labels.hu.json`: `outcomes` (6), `stop_reasons` (7), `tiers`, `strategies`, `topics`, `family_topics`
  (all 24 families), `store_states`, `job_states`, `error_codes`, `results_policies`, `answer_values`
  (`yes` → "Igen", `no` → "Nem"), later `class_names`.
- `labels.js` looks a key up; a missing key shows the raw value **and** logs a console warning (no silent gap).
- Drafts (user may reword): outcomes — ANSWERED "megválaszolta", DID_NOT_FIT "nem fért el a modell
  szövegkeretében", PARSE_FAILURE "a modell válasza nem volt értelmezhető", RETRIEVAL_ERROR "hiba az adatok
  lekérdezésekor", PROVIDER_ERROR "a modellszolgáltató hibát jelzett", TIMED_OUT "nem készült el az időkorláton
  belül"; stop reasons — done "befejezte", max_steps "elérte a lépésszám-korlátot", prompt_budget "elfogyott a
  szövegkerete", errors "túl sok eszközhiba", overflow "a modell szövegkerete betelt", runaway "a modell
  gondolkodása elfutott, nem adott választ", deadline "elfogyott az ideje"; tiers — cypher-luna "1. lépés:
  adatbázis-lekérdezés (Cypher)", agent-luna "2. lépés: gráfbejáró ügynök".
- **Errors:** `server.py` raises `HTTPException(status, detail={"code": …, "message": …})`; codes
  `unknown_corpus`, `unknown_job`, `unknown_question`, `corpus_not_ready`, `busy`. The page shows
  `error_codes[code]`; the English `message` only inside a folded "Technikai részletek".
- Job end states: `needs_paid` (replay-only) → "Erre a kérdésre nincs tárolt válasz, és a demó most csak tárolt
  válaszokkal fut." + folded hint about the `--replay-only` flag; `refused` → "Elérted a munkamenet költségkeretét
  ({cap})."; `error` → "Hiba történt a válasz közben." + folded technical text.

## 7. Result card (P10)

1. **Answer** (large). BOOLEAN → Igen/Nem; lists → comma list; `not_present` → "A rendszer szerint ez az
   információ nincs rajta a rajzokon."; fallback → amber line "Egyik lépés válaszát sem fogadta el a rendszer;
   az első lépés válaszát mutatjuk — óvatosan kezeld."
2. **One fact line:** who answered (tier label), time, cost. **[rev 2]** The replay line is void (live only); the line is §17.3's.
   - Replay: "Tárolt válasz (azonnal) · élőben {latency} mp volt · eredeti költsége {cost} (≈ {cost×1000} / 1000
     kérdés)".
   - Paid: "Válaszidő: {job elapsed} mp · költség {spent} (≈ {spent×1000} / 1000 kérdés)".
3. **Honnan tudja?** chips: "A válaszban szereplő tételek lapjai" (answer sheets), "Az ügynök által megnézett lapok"
   (read sheets, only when non-empty). A chip reads `DWG 464` (as printed on the sheet) and jumps the PDF.
4. **Ellenőrzés** (examples only): "Helyes válasz: …" and "A rendszer válasza: helyes / nem egyezik"; chips "A
   helyes válaszhoz szükséges lapok" (gold sheets).
5. **Részletek** (`<details>`, closed): tier table in Hungarian (lépés, eredmény, elfogadva, idő, költség, hívások,
   ebből tárolt, ügynöklépések, leállás oka, adatbázis-sorok); the two time figures with one-line definitions
   ("modellidő a kaszkád szabálya szerint" vs "valós várakozás ebben a gépben"); k/u explained ("k: ennyi lapot kell
   összekötni a válaszhoz — {k_connector} lapösszekötőn át, {k_identity} ugyanazon tétel több lapon; u: érintett
   technológiai egységek"); the running policy; the technical notice.
   **[rev 2]** The k/u sentence above is wrong about what k counts. `Question.k` = evidence edges whose two ends
   have different home sheets; `k_connector` = the part resolved by an off-page connector pair; `k_identity` = the
   part resolved because the item is drawn on both sheets; `u` = evidence edges whose ends carry different unit ids
   (`qa/models.py` docstrings). Corrected text in §21.2 (glossary `k`, `u`).
6. **Hogyan működik?** (`<details>`, closed; numbers only from `/api/status`):

   > A kérdést először egy **adatbázis-lekérdező lépés** kapja: a nyelvi modell lekérdezést (Cypher) ír a teljes
   > üzem gráfjára, és a kapott sorokból fogalmaz választ. Ha ez a lépés nem talál sort, azt mondja, hogy az adat
   > nincs a rajzokon, vagy a válasza nem értelmezhető, a kérdés a **gráfbejáró ügynökhöz** kerül: ez eszközökkel
   > (keresés, szomszédok, útvonal) lépésenként járja be a rajzlapokon átívelő gráfot. Egy kérdésre összesen
   > {cutoff} másodperc jut. A bal oldali rajzok a rendszer saját bemenetéből készültek: azt mutatják, amit a
   > rendszer lát. A példakérdések válaszai tárolva vannak, ezért ingyen és azonnal jönnek; egy új kérdés fizetős
   > modellhívással megy, a munkamenet költségkeretén belül.

Money format (`format.js`): `Intl.NumberFormat("hu-HU", {style: "currency", currency: "USD",
currencyDisplay: "narrowSymbol"})`; ≥ $0.01 → 2 decimals ("2,00 $"), below → 2 significant digits ("0,00071 $"),
0 → "0 $".

**[rev 2]** The card's structure stays; its texts become English (§18). Money format becomes
`Intl.NumberFormat("en-US", {style: "currency", currency: "USD"})`: ≥ $0.01 → 2 decimals ("$2.00"), below → 2
significant digits ("$0.00071"), 0 → "$0". Seconds: `en-US`, one decimal ("3.2 s").

## 8. Drawing viewer (P11)

- One iframe per corpus selection. `jumpToPage(n)` sets `iframe.src = pdfUrl + "#page=" + n` (same document;
  Chromium's and Firefox's viewers follow a fragment change — **to verify by hand**, ADR-0049 O1).
- `pdfUrl = /corpora/{id}/drawings.pdf?v={pdf_sha256[:12]}`; the route adds `Cache-Control: private,
  max-age=86400`. If a rebuild is ever needed it is served from the browser cache, not re-sent.
- `const PDF_JUMP = "fragment"` in `viewer.js`; `"rebuild"` restores today's behaviour. The DP-T8 manual check
  (Edge and Chrome; 5 chip jumps on D1000) decides the value and is reported in the chat.
- Tag highlighting: not possible with the built-in viewer's fragment API in Chromium; stays a Could (pdf.js).

## 9. Eredmények tab (P12)

### 9.1 Data

`demo/app/results.py` reads the two report files named in the config and projects them; no copy is written.

```python
class Interval(BaseModel): estimate: float; ci_low: float; ci_high: float          # Wilson 95 %
class Provenance(BaseModel): path: str; sha256: str; modified: datetime; result_row: str
class LadderPoint(BaseModel): corpus_id: str; n_sheets: int; arm: str; n: int
    accuracy: Interval; cost_mean_usd: float; latency_median_s: float
class LadderView(BaseModel): scope: Literal["common"]; n_families: int; cutoff_s: float
    wall_sheets: float; points: tuple[LadderPoint, ...]; absent: tuple[str, ...]; source: Provenance
class SealedRow(BaseModel): corpus_id: str; n_sheets: int; policy: str; n_questions: int; n_correct: int
    accuracy: Interval; cost_per_question_usd: float; latency_median_s: float; latency_p90_s: float
class SealedView(BaseModel): scope: Literal["headline"]; rows: tuple[SealedRow, ...]; source: Provenance
class ResultsView(BaseModel): ladder: LadderView | None; sealed: SealedView | None

# config.py
class ResultsSources(BaseModel):
    ladder_report: Path               # data/runs/exp0001/report/report.json
    ladder_result_row: str = "EXP-0001-LADDER"
    sealed_report: Path               # data/runs/sealed/report/report.json
    sealed_result_row: str = "EXP-0002-H100, EXP-0002-H1000"
class DemoConfig: ... ; results: ResultsSources | None = None
```

`GET /api/results` → `ResultsView` (404 `results_not_configured` when absent). Input parsing uses small Pydantic
models with `extra="ignore"` over just the fields of E6; a missing field raises with the path and the field name.
Scope `common` (19 families, the claim's scope, ADR-0054) for the ladder; `headline` (460 questions) for the
sealed test.

### 9.2 Figures (`results.js` + `charts.js`)

| # | Figure | Axes | Series | Marks |
|---|---|---|---|---|
| F1 | Pontosság a lapszám függvényében (EXP-0001) | x log sheets 1…1,000; y 0–100 % | ContextRAG (high) vs kaszkád v3, Wilson whiskers | point labels "H3 (4 lap)" from `n_sheets` |
| F2 | Költség / kérdés (EXP-0001) | x log; **y log** | same two | vertical line at `wall_sheets`, label "kontextusfal ≈ {round} lap: e fölött a teljes rajzkészlet nem fér a promptba" |
| F3 | Medián válaszidő (EXP-0001) | x log; y linear seconds | same two | — |
| F4 | Lezárt teszt: H100 vs H1000 (EXP-0002) | grouped bars, y 0–100 % with whiskers | kaszkád v3, mindig ügynök, mindig Cypher × {H100, H1000} | table below: $/kérdés, medián / p90 idő, n |

- Every figure has a Hungarian caption: what was measured, n, the scope, and "Forrás: {path} ({sha256[:8]},
  {modified})"; F1–F3 add "A két kísérlet kérdéskészlete eltér, ezért az EXP-0002 külön ábrán van."
- **Részletek** under each: the full table of the projected rows (all ladder arms, including the two tiers and
  ctx-low with its absences), so nothing is hidden by the chart's selection.
- `charts.js` API: `lineChart(host, {x: {log, domain, label}, y: {log, domain, label, format}, series, marks})`,
  `barChart(host, {groups, yDomain, yLabel, format})`; SVG via `createElementNS`, hover text via `<title>`, fixed
  palette, no external code.

## 10. API changes (summary)

| Route | Change |
|---|---|
| `GET /api/status` | `CorpusStatus` + `store: StoreState`, `n_sheets`, `open_s` |
| `GET /api/corpora/{id}/questions` | `QuestionSummary` loses `answer_type` (family kept for the topic, never displayed) |
| `POST /api/ask` | `AskRequest` §5.2 (`example_id`, no `answer_type`) |
| `GET /corpora/{id}/drawings.pdf` | `Cache-Control` header |
| `GET /api/results` | new |
| all | errors as `{"detail": {"code", "message"}}` |

## 11. Files

```
src/plantgraph/demo/app/{seed_cache,coverage,store_probe,examples,results}.py           new
src/plantgraph/demo/app/{config,api_models,answering,cascade_pool,corpus_runtime,state,server,__main__}.py  edited
src/plantgraph/demo/app/demo_config.example.json                                       edited
src/plantgraph/demo/app/static/{index.html,app.css,strings.js}                          edited
src/plantgraph/demo/app/static/{app,api,labels,format,ask,answer,viewer,results,charts}.js  (ES modules; app.js split)
src/plantgraph/demo/app/static/labels.hu.json                                           new
tests/test_demo_{seed_cache,coverage,store_probe,examples,labels,results}.py            new
tests/test_demo_app.py, tests/test_demo_page.py                                         edited
data/runs/cv1/demo/{demo_config.json, cache_luna_demo.sqlite(+provenance), examples/*.jsonl(+provenance)}  local, git-ignored
```

`__main__.py` becomes sub-commands: `serve` (default, today's behaviour), `seed-cache`, `examples`, `coverage`.

**[rev 2]** The full file list after revision 2 is §21.

## 12. Tests and self-measurement

- **[rev 2: retired with the replay path, §17.1]** **Replay coverage** (`coverage` sub-command, DP-T2): asks every example of a corpus in replay mode through the
  demo's own loader and prints hits, misses by tier, answered-by counts, and how many answers equal the recorded
  rows. Expected on today's data (E2): D1000 36/36 hits with both tiers, D100 36/36 hits agent-only. It is the
  demo's accuracy-against-ground-truth for "is the example free and identical to the evaluated answer".
- **Label coverage** test: `labels.hu.json` has every `Outcome`, `StopReason`, `QuestionFamily`, store-state kind,
  job state, error code in `server._STATUS_OF`, every tier and strategy of the configured policy, every results
  policy.
- **Results projection**: toy report files → exact projected values; optional real-file test (skips if absent):
  every sealed row's estimate = `n_correct / n_questions`; ladder H3 `n_sheets` = 4; wall = `wall_sheets`.
- **Store state**: pure decision table over fake probes (each kind once).
- **Page**: every API path and every `labels.*` key the JS uses exists (string scan, as today); manual checklist
  per UI task, results reported in the chat.

## 13. Coder tasks (Sonnet, one at a time; ruff, `mypy --strict`, pytest green; offline; no paid call; never stop PID 1136 — the user restarts the server)

**[rev 2]** DP-T1…DP-T5 below are done (committed by the user, last `ce9bb60`). The DP-T6…DP-T10 rows are
revision 1's and stay for traceability; the tasks to build are the re-cut table in §25.

| # | Task | Files | Tests / acceptance | Size |
|---|---|---|---|---|
| DP-T1 | **Demo cache seed + config fix.** §4.1, §4.2 | `seed_cache.py`, `__main__.py` (sub-commands), `demo_config.example.json`, `tests/test_demo_seed_cache.py` | toy sqlite files: union, first source wins on a duplicate key, refuses existing out, sources opened read-only, provenance counts; **then locally:** build `cache_luna_demo.sqlite`, edit `demo_config.json` (cache, plant ingest, CYPL2), print the provenance | S |
| DP-T2 | **Replay coverage command.** §12 | `coverage.py`, `__main__.py`, `tests/test_demo_coverage.py` | fake loader: hits / misses counted per tier, never a paid client; **locally:** D1000 dev and D100 dev reported (expected 180/180 each, E2) | S |
| DP-T3 | **Store state + eager paid open.** §4.3, §4.4 | `store_probe.py`, `cascade_pool.py`, `corpus_runtime.py`, `state.py`, `api_models.py`, `tests/test_demo_store_probe.py`, `tests/test_demo_app.py` | decision table (7 kinds); paid cascade opened at construction iff allowed; `open_s` recorded; status carries `store`, `n_sheets` | S/M |
| DP-T4 | **Examples + ask rule.** §5.2, §5.4 | `examples.py`, `answering.py`, `api_models.py`, `tests/test_demo_examples.py` | `--variant` and `--per-family/--seed` deterministic; gold kept; text-match rule (unchanged text → stored type; edited → FREE_TEXT; unknown id → FREE_TEXT); **locally:** write D100 (hu1) and D1000 files, point the config at them, run `coverage` (expected 36/36 each) | S/M |
| DP-T5 | **Error codes + label table.** §6 | `server.py`, `static/labels.hu.json`, `tests/test_demo_labels.py` | coverage test §12; every domain error → `{code, message}`; status codes unchanged | S |
| DP-T6 | **Page restructure + ask panel.** §5.1 | `static/*.js` (ES modules), `index.html`, `app.css`, `tests/test_demo_page.py` | no file > 400 lines; string scan of API paths and label keys; manual: corpus label, store text for D100, examples by topic, click fills box, edit clears example | M |
| DP-T7 | **Result card.** §7 | `answer.js`, `format.js`, `strings.js`, `app.css` | manual: one replayed D1000 example answered by tier 1, one by tier 2, one D100 example, one typed question in replay-only (needs-paid text); money format; Részletek and Hogyan működik? closed by default | M |
| DP-T8 | **PDF jumps.** §8 | `viewer.js`, `server.py` (header), `tests/test_demo_app.py` | header present; versioned URL; manual Edge + Chrome, 5 jumps on D1000, result → `PDF_JUMP` value, reported in the chat | S |
| DP-T9 | **Results projection + route.** §9.1 | `results.py`, `config.py`, `server.py`, `tests/test_demo_results.py` | toy reports exact; real-file checks §12; provenance sha256 equals the file's | M |
| DP-T10 | **Eredmények tab.** §9.2 | `results.js`, `charts.js`, `index.html`, `app.css` | manual: four figures; F1 point labels show 1/4/10/30 sheets; F2 log y and wall line; F4 whiskers; every number on screen equals the Részletek table, which equals `/api/results` | M |

Order: DP-T1 → DP-T2 (the user restarts the server: D1000 runs the full cascade, examples replay free) → DP-T3 →
DP-T4 → DP-T5 → DP-T6 → DP-T7 → DP-T8 → DP-T9 → DP-T10. Each task is one commit; the user runs every commit.

## 14. Open user decisions (recommendation first)

**[rev 2]** U1–U4 were decided on 2026-10-12 (all (a), ADR-0055 status line); U1 was carried out (ADR-0055
outcome log). With the demo in English (2026-10-16): U1's Hungarian D1000 file stays on disk but is no longer
configured; U2 (typed questions always FREE_TEXT) is unchanged; U3 (Hungarian question → English answer) is moot;
U4 is replaced by the en-US format (§7 note). Revision 2's open questions are §26.

- **U1 D1000 examples in Hungarian.** (a) English dev questions — free, but not Hungarian; (b) **recommended:** 36
  Hungarian wordings by the PARA-R0 procedure (fresh blind agent, tags checked by regex), then one paid warm-up pass
  so they replay free at the defence — estimate 36 × $0.00071 ≈ $0.026 (EXP-0002 H1000 cascade_v3 mean $/q;
  an estimate, D1000 is not H1000); (c) show a Hungarian translation but ask the English text — rejected, the
  screen would not show what the system was asked.
- **U2 Typed questions.** **Recommended:** always FREE_TEXT, no selector. Alternatives: rule-based guess (fragile
  on Hungarian, a wrong guess forces a wrong shape); LLM guess (an extra paid, unevaluated call per question).
- **U3 If a Hungarian typed question gets an English paragraph** (the frozen prompt is English; unmeasured):
  **recommended:** show it as it is. Alternative: a demo-only translation call — paid, and not part of the
  evaluated system.
- **U4 Money format.** **Recommended:** Hungarian, "2,00 $" / "0,00071 $". Alternative: "$2.00" as in the request.

## 15. Risks (not for the user)

- **R1** Fragment jumps may not move Chromium's viewer (ADR-0049 O1) → `PDF_JUMP = "rebuild"`, now cache-served.
- **R2** A later re-ingest of D1000 with `--fresh-database` changes nothing the demo checks (counts equal), but a
  re-ingest of D100 makes D1000 agent-only; the status says so (P4).
- **R3** FREE_TEXT behaviour at plant scale and in Hungarian is unmeasured (E5 is 15 English asks per arm on one
  tiny plant); typed-question answers are not evidence for anything.
- **R4** `report.json` field names are the reports' own; a regenerated report with renamed fields fails loudly at
  start (projection raises), never draws a wrong chart.

**[rev 2] risks**
- **R5** Live answers vary: a live ask can be wrong or slower than the recorded run of the same question (the
  sealed accuracy is not 100 %); the verdict line shows it honestly. A provider outage leaves the demo without
  answers — there is deliberately no replay fallback.
- **R6** The per-ask cascade open time and the D1000 wipe time are unmeasured; DP-T12 and DP-T13 measure them. If the
  open is slow, the §17.1 reopen-on-repeat follow-up applies.
- **R7** The recording transport replaces the SDK's own HTTP client; it must keep the SDK's timeouts and limits
  (DP-T14 tests a slow response).
- **R8** The trace parser reads request bodies and the call-log format of frozen code; a format change is kept as raw
  text and flagged, never shown as a wrong step.

## 16. Sources

| Figure | Source |
|---|---|
| E2 counts and seconds | architect scratch `replay_check.py`, 2026-10-12, copy of `cache_luna.sqlite`, replay-only client, local Neo4j holding D1000 |
| E3 | JSON diff of `data/runs/cv1/{corpora,neo4jplant}/{D100,D1000}/ingest.json` |
| E5 | `data/runs/exp0001/ex01/answers.jsonl` (counted) |
| E6 | `data/runs/exp0001/report/report.json`, `data/runs/sealed/report/report.json` |
| E7, E8 | `GET` on 127.0.0.1:8765, `drawings.index.json`, `data/runs/cv1/demo/calls.jsonl` |
| $0.00071, U1 estimate | `_results.md` row EXP-0002-H1000; 36 × it = arithmetic, **estimate** |
| 14.1 s / 5.9 s | caller's session measurement (not re-measured here) |

---

# Revision 2 sections (2026-10-16)

## 17. Live answering (P19–P21) — DP-T12, DP-T13, DP-T14, before DP-T6

### 17.1 No cache reads: a fresh live cascade per ask (DP-T12)

**What the code does today (read 2026-10-16).** `open_live_cascade` (`qa/cascade/live_build.py`, frozen) builds every
tier's client with `build_chat_client(allow_paid_calls=True, cache_path=…)` (`qa/harness/clients.py`), which opens
`SqliteCache(cache_path, "live")` — a **read-through** cache: `ChatClient` looks the request up before any network
call (`llm/client.py`, `self._cache.get(request)`) and stores every answer (`put`). The frozen client has no switch
that turns reads off. `CascadePool` keeps one replay and one paid cascade per corpus for the whole server run, and
`run_job` tries replay first.

**What the demo controls.** The `cache_path` argument. Given `Path(":memory:")`, `sqlite3.connect` opens a
**private, empty, in-memory database** for each `SqliteCache` (checked 2026-10-16: `str(Path(":memory:")) ==
":memory:"`, the connection works, no file is created; `SqliteCache.__init__`'s `path.parent.mkdir` gets `.`, which
is harmless). So the demo can run with **no cache reads without touching frozen code**.

**Design.** An in-memory cache still fills during a cascade's life, so an identical request later in the same
cascade would hit. The demo therefore opens a **fresh cascade for every ask** and closes it when the job ends: every
ask starts with empty caches, by construction.

```python
# demo/app/live_cascades.py (replaces cascade_pool.py)
#: Each tier client gets its own empty SQLite database in memory: nothing is read from disk, and
#: the database disappears when the ask's cascade is closed.
LIVE_CACHE = Path(":memory:")

class LiveCascadeFactory:
    def __init__(self, settings: LiveSettings) -> None          # policy, view, plan, tier runs, log, cutoff, guard, http_client
    def open_for_ask(self) -> tuple[OpenedCascade, float]       # the cascade and the seconds it took to open
```

- `run_job` has **one path**: reserve money (the `SpendGuard`, as now) → `open_for_ask()` → `cascade.ask(asked)` →
  close → release the reservation with the real spend. A `NeedsPaidCall` result can no longer occur (paid clients
  never raise `CacheMiss`); if it does, the job ends `error`.
- **Guard (self-measurement):** the job checks every `TierReport.n_cached == 0`, `LiveAnswer.from_cache is False`
  and no trace call with `from_cache` (§17.3). A violation marks the result `cache_hit_detected: true`, shown as a
  red line on the card and logged. Expected never; a test proves two identical asks send two network requests
  through the fake transport.
- **Open cost** (`open_live_cascade` reads each tier's `run_config.json`, opens and checks Neo4j, builds the
  strategies) is **not measured**. `JobStatus.open_s` records it per ask; the card shows it as "preparing" and keeps
  it out of the model time. DP-T12 reports the median of 5 opens per plant in the chat (fake transport, no paid
  call). If it exceeds 1.0 s, a follow-up may keep one cascade per corpus and reopen only before an ask whose exact
  text it has already seen (every model request carries the question text, so only such a repeat can match a cache
  entry — to be verified by reading the prompts if adopted). Not built now.
- No API key at start (`openrouter_settings.from_env()` is `None` and no test transport): the corpus is marked
  `error` with the code `no_api_key` (new) — the demo cannot answer without live calls. Tests inject the fake
  transport, which `build_chat_client` accepts without a key.

**Cost and time the visitor will see** (measured, not promised): the U1 warm-up asked the 36 Hungarian D1000
examples live through the demo — $0.01865 in total, median latency 7.5 s (ADR-0055 outcome log); that is about
$0.0005 per ask (arithmetic). EXP-0002 H1000 `cascade_v3`: $0.00071 per question (`_results.md`). The $5.00 session
cap (`demo_config.json`) is far above a defence's needs.

### 17.2 The plant in Neo4j: an explicit plant switch (DP-T13)

**Facts.** Neo4j holds one plant at a time (user rule; it holds D1000 now). A Cypher tier opens only when the store
holds exactly the asked corpus (`open_checked_neo4j_view` → `check_store`). The public, frozen loader functions are
`store.neo4j_loader.wipe_corpus(settings, corpus_id)` and `load_corpus(settings, plan) -> LoadReport` (wipe own
corpus, schema, nodes, relationships, verify counts and invariants); settings from `neo4j_settings.from_env()`. The
demo already holds each plant's full plant-profile `LoadPlan` (`load_corpus_artifacts(...).load_plan`, P2).

**Times.** INFRA-1 measured full ingests at 3.1 s (D100) and 26.1 s (D1000) (medians of 3, `_results.md`), most of it
regeneration, which the demo skips. The load stage alone, in the plant-profile ingest records: **`load_total`
2.25 s (D100), 8.59 s (D1000)** (`data/runs/cv1/neo4jplant/D*/ingest.json`, `stage_seconds`, one run each). Wiping
D1000 out of a populated database is **not measured** (that ingest ran on a fresh database: its `load_wipe` 0.02 s
wiped nothing); DP-T13 measures it.

**Decision (user, 2026-10-16; ADR-0056 2A).** *A plant is chosen deliberately, then all questions go to that plant.*
Selecting the other plant in the plant switch **is** the load: it wipes the held plant and loads the chosen one, with
a visible loading phase and its measured time. While a plant loads, asking is disabled. An ask never reloads the
database: an ask about a plant the database does not hold is refused with `plant_not_loaded`. At start the demo
selects whatever plant Neo4j holds (D1000 now); if it holds none or is unreachable, the page says so and asking waits
until the visitor selects a plant. Rejected: loading inside the ask (the first revision-2 proposal — it hides a
reload inside a question and invites bouncing between plants), D1000 only, D100 agent-only, spawning the ingest CLI.

```python
# demo/app/store_loader.py
class PlantLoad(BaseModel):
    corpus_id: str; wiped: tuple[str, ...]; wipe_s: float; load_s: float     # load_s = LoadReport.total_s
def switch_plant(corpus_id: str, plan: LoadPlan, held: Callable[[], tuple[str, ...]],
                 settings: Neo4jSettings) -> PlantLoad                       # wipe every held id, then load_corpus(plan)

# api_models.py
class PlantStatus(BaseModel):
    held: tuple[str, ...]                    # what Neo4j holds now (cached; probed at start and after each switch)
    loading: str | None                      # the plant being loaded, if any
    elapsed_s: float | None                  # of the running load
    last: PlantLoad | None                   # the last finished switch, with its measured seconds
    error: str | None                        # error code of a failed switch (`plant_load_failed`)
```

- `POST /api/plant {corpus_id}` → 202 and starts the switch on a worker thread **under the same `Busy` lock** as asks
  (a switch while an ask runs → 409 `busy`; an ask while a switch runs → 409 `busy`). Switching to the plant already
  held → 200, nothing done. `GET /api/plant` → `PlantStatus` (the page polls it once a second while loading);
  `AppStatus` also carries `plant: PlantStatus`.
- The ask job checks the held plant before opening the cascade: not held → `plant_not_loaded` (new code), no call.
- Phase text in the plant switch: "Loading D100 into the graph database… 1.4 s (last time 2.3 s)". "Last time" is
  the last measured switch to that plant, initially `stage_seconds.load_total` of its ingest file (read, not typed).
  When done: "D100 loaded in 2.6 s (D1000 wiped in {wipe_s} s)".
- Store-state text `holds_other` → "The graph database holds plant {held}. Select a plant above to load it." (shown
  only if the selection and the database disagree, e.g. after a failed switch).
- New error codes `plant_not_loaded` ("This plant is not in the graph database. Select it above to load it first.")
  and `plant_load_failed` ("Loading this plant into the graph database failed.").

### 17.3 The real trace of an ask, recorded verbatim (DP-T14)

The user wants to **see the route the system actually took**: the query the model wrote and the rows it got; each
agent tool call, its arguments and what came back. Three candidate sources were checked (2026-10-16):

| # | Source | What it holds | Verdict |
|---|---|---|---|
| 1 | The per-ask in-memory cache (DP-T12) | `responses(key, response_json)`: the cache key (a **hash** of the request) and the `ChatResponse` only (`llm/cache.py`) — the model's replies (Cypher text, tool calls), **not** the requests | insufficient: no rows, no tool results; the same as the call log |
| 2 | **A demo-owned HTTP transport** | the demo already passes `http_client` through `open_live_cascade` → `build_chat_client` → `ChatClient` → `openai.OpenAI(http_client=…)` (`qa/cascade/live_build.py`, `qa/harness/clients.py`, `llm/client.py`); `httpx2` 2.13.1 has `BaseTransport` and `HTTPTransport`; calls are not streamed. A wrapping transport sees every request body (the full message list) and every response body | **works, no frozen change** |
| 3 | Call log + re-running plant-API primitives locally | tool names and arguments from `calls.jsonl`; `ItemGraph` lookups are deterministic (results sorted by `sort_key`, "design §3.3 determinism") and public | fallback only, not needed |

**What source 2 yields, verbatim.** The agent loop sends the whole conversation on every call: system prompt, the
question, then for each step the assistant's tool call and a `user` message holding the tool's **observation**
(`qa/agent/loop.py`). So the request of step n+1 contains the result of step n, and the last request contains all of
them. The Cypher tier's final-step request contains "the query and its rows as JSON lines in a canonical order — the
context the final step sees" (`qa/strategies/cypher_rag.py`), i.e. the rows exactly as the model saw them (with the
"cut off at the first N rows" header when truncated). Limits: the rows shown are those in the prompt (capped by the
tier's row cap, as evaluated); nothing the model did not see is shown.

```python
# demo/app/trace_recorder.py
@dataclass(frozen=True)
class Exchange:
    request_json: dict[str, object]          # the body the SDK sent (model, messages, response_format, …)
    response_json: dict[str, object] | None  # None when the call failed or was abandoned
    status: int | None; elapsed_s: float
class RecordingTransport(httpx2.BaseTransport):
    """Passes every request to `inner` unchanged and keeps a copy of the request and the response body."""
    def __init__(self, inner: httpx2.BaseTransport) -> None
    def handle_request(self, request: httpx2.Request) -> httpx2.Response
    def exchanges(self) -> tuple[Exchange, ...]          # thread-safe snapshot, in send order
```

- **Follow-up change to DP-T12's `live_cascades.py` (made in DP-T14, not in DP-T12's spec):** `open_for_ask()`
  returns an `AskHandle(cascade, recorder, open_s)`. For each ask it builds a fresh client whose transport is a
  `RecordingTransport` around the injected test transport, or around `httpx2.HTTPTransport()` in production, and
  passes it as `http_client`. The job reads `recorder.exchanges()` **before** closing the cascade. The client must
  keep the SDK's default timeouts and connection limits (use the SDK's own default client class with
  `transport=…` if the installed SDK has one, otherwise the same values); a test asserts that a slow fake response
  still times out as before.
- Late responses of abandoned calls that arrive after the job closed are ignored (the snapshot was already taken).

```python
# demo/app/ask_trace.py
class CypherStep(BaseModel):
    tier: str; query: str; context: str                  # the final-step context text, verbatim
    rows: tuple[dict[str, object], ...]                  # the JSON lines parsed; () if none or unparsable
    truncated: bool
class AgentStep(BaseModel):
    index: int; tool: str; args: dict[str, object]; observation: str
    items: tuple[str, ...]                               # item ids named in args or observation (§21.5)
class TraceCall(BaseModel):
    purpose: str; latency_s: float; cost_usd: float; from_cache: bool; error_kind: str | None
class AskTrace(BaseModel):
    cypher: tuple[CypherStep, ...]; agent: tuple[AgentStep, ...]; calls: tuple[TraceCall, ...]
def build_trace(exchanges: Sequence[Exchange], log_lines: Sequence[CallLogLine],
                item_graph: ItemGraph) -> AskTrace
```

- **Joining.** The job's call-log lines (the lines appended since the job started, as in the first DP-T14 design)
  give `purpose`, cost, latency and `from_cache` per call; an exchange is matched to its line by the response body's
  `id` = the line's `provider_response_id`. Retried HTTP attempts without a response stay out of the steps and are
  counted in `calls`.
- **Parsing.** A `cypher` call's response text is the query; the following `answer` call's last user message is the
  context, whose JSON lines become `rows`. An `agent_step` call's response text is the tool call (`{"call": {"tool":
  …, "args": …}}`); the observation is the `user` message that follows it in the **next** request (for the last step:
  in the final `answer` request). Items in args and observations are words that name a plant item —
  `evidence.tags_in_text` (tags) plus `ItemGraph.has_item` (untagged items are shown to the model by item id).
  Anything that does not parse is kept as raw text and flagged, never dropped silently.
- `DemoAnswer` gains `trace: AskTrace` and `cache_hit_detected: bool` (any `from_cache` in the job's calls).

**Card facts (replace §7 item 2).** One line: "Answered in {elapsed} s · model time {latency} s · cost {spent} · by
Step 1: database query". When the cascade open was slow: "preparing: {open} s — not part of the answer time".
**Details:** the per-tier table; the **step list** (Cypher: query block, rows as a table with the "N rows" header;
agent: numbered tool calls with their arguments and a folded observation each); the per-call table. The interactive
route graph over the same steps is §21.5.

### 17.4 Retired with the replay path (DP-T12)

| Item | Fate | Reason |
|---|---|---|
| `--replay-only` flag, `JobStatus` state `needs_paid` and field `needs_paid` | removed | no replay |
| `CascadePool` (replay / paid / tier-2-only modes) | replaced by `LiveCascadeFactory` | one live mode |
| `AskRequest.tier2_only` | removed | no non-evaluated mode on the page |
| `DemoConfig.cache_path` | removed (an old config that still has it loads: Pydantic ignores unknown keys by default, and `DemoConfig` does not forbid them) | the cache is `LIVE_CACHE` |
| `seed-cache`, `coverage` sub-commands; `seed_cache.py`, `coverage.py`; `tests/test_demo_seed_cache.py`, `tests/test_demo_coverage.py` | deleted | their only purpose was replay |
| `cache_luna_demo.sqlite`, `cache.sqlite` | stay on disk as archives, unread | provenance of earlier results |
| `examples`, `agreement`, `estimate` | kept | not replay-dependent (examples file builder; answer-sheet agreement CLI; the spend guard's reservation) |

### 17.5 Live progress while an ask runs, and lost time on the card (DP-T21) — added 2026-10-16

**Why.** First live try (user, 2026-10-16): a D100 example ("Which instruments measure E-30-3?") took 58.4 s wall
for 29.1 s model time; the page showed only a timer for the whole minute. The call log and the job's trace show
why: three cypher attempts failed at the provider (frozen `ChatClient._call_with_retries`: 429/5xx/connection
errors, backoff 1 + 2 + 4 s; `AskTrace.unlogged_attempts = 3`), the fourth took 25.2 s, the answer call 3.8 s.
Earlier D1000 Cypher asks in the same session took 5.3–5.8 s (query) + 1.3–2.2 s (answer). The answer was right.
The user's complaint: "58 mp-ig gondolkodott és semmit sem láttam addig belőle."

**What.** The recording transport already sees every attempt; show it **while** the ask runs.

- `RecordingTransport` records an attempt **when it starts** (request body, start time) and completes it when the
  reply or the error arrives: `Exchange` gains `started_s` (perf_counter offset from the window mark), `status`
  stays `None` while running, and `error: str | None` (exception class name, e.g. `ReadTimeout`,
  `ConnectError`; for a reply with status ≥ 400 the status code). `exchanges()` returns finished and running
  attempts in start order; a running one has `response_json is None and error is None and status is None`
  (`Exchange.running` property). Thread safety as before.
- New `progress.py`: `LiveProgress(events: tuple[ProgressEvent, ...])`, built from `window.exchanges()` and
  `window.log_lines()` on every `GET /api/jobs/{id}` while the job runs (cheap: one ask has ≤ ~20 exchanges).
  `ProgressEvent`: `phase` (`cypher`, `answer`, `agent_step`, `unknown`), `state` (`running`, `done`, `failed`),
  `started_s`, `elapsed_s`, `attempt` (1-based within the same phase run of consecutive failed-then-retried
  attempts), `http_status`, `error`, and `summary` (the Cypher query text for a finished cypher call; `"N rows"`
  for a finished answer call is NOT known — the row count is the cypher step's, shown with it; for a finished
  agent step `tool(args)` and the observation's first line when the next request holds it).
  **Phase** of an attempt: from its joined call-log line when there is one; otherwise from the request body by the
  frozen prompts' fixed markers (the same markers `trace_parse.py` already relies on — e.g. the Cypher final
  prompt's "Cypher query that was run:"), else `unknown`, shown as "waiting for the model". Never guess a phase
  from order alone.
- `JobStatus` gains `progress: LiveProgress | None` (filled while running and kept at the end), and
  `running_tier` stays `None` (the cascade still has no hook; the tier is visible from the phase).
- **Lost time.** `AskTrace` (or `DemoAnswer`) gains `failed_attempts: int` and `lost_s: float` = the summed
  durations of failed attempts plus the waits between them (wall time between a failed attempt's end and the next
  attempt's start in the same phase). Exactly measured from the recorder, never estimated.
- **Page.** While asking: under the "Asking… N s" timer, a live timeline (one line per event, newest last, the
  running one with a moving elapsed counter): "Step 1 · writing the database query… 8.2 s"; a failed attempt in
  amber: "The model provider did not answer (HTTP 502 / ReadTimeout) — retrying (attempt 2 of 6)"; "Query written
  · MATCH …" (one line, monospace, ellipsis); "Writing the answer…"; agent: "Action 2 · find(tag="E-30-3")".
  The timeline folds into the card's Details when the answer arrives. The facts line gains, only when
  `failed_attempts > 0`: "· 3 failed provider attempts, 29.3 s lost" (amber, with a glossary tip "The model
  provider returned errors; the system retried. This time is not the model's thinking time.").
- **Tests** (`tests/test_demo_progress.py`): running attempt visible before its reply (fake transport that blocks
  on an event); failed attempts with status and error class; phase from log line vs from markers vs unknown;
  lost_s from synthetic timestamps; JobStatus carries progress while running. Page invariants for the new module.
- **Files:** `trace_recorder.py`, `progress.py` (new), `jobs.py`, `api_models.py`, `ask_trace.py` or
  `answering.py` (lost time), `static/progress.js` (new), `static/ask.js`, `static/answer.js`, `static/strings.js`,
  `static/card.css`, `labels.en.json` (glossary `lost_time`), tests. Demo files only; frozen code untouched.

### 17.6 The database is read again before every ask (DP-T16) — added 2026-10-16

**Why.** The server used to learn which plant Neo4j holds only at start and after its own switch
(`PlantTracker`). Something outside the demo (a loader run, a wipe) could change the database, and the demo kept
answering against the wrong plant. **What.** Under the ask lock, before any model call, `AppState.start_ask` runs
`PlantTracker.verify_unchanged()`: one `held_corpus_ids` read (the app's `HeldCorporaProbe`, fakeable in tests; median
10 ms against the local Neo4j, first call 70 ms, 9 runs). If the plants read differ from the tracker, the tracker takes
the read value, the cascades are reopened on the new contents, and the ask is refused with `store_changed` (409); the
page then refreshes `/api/status`, so the plant switch shows the plant really held. If the read fails (Neo4j down) the
ask is refused with `store_unreachable` (409), no model call. A corpus whose policy has no database step is not checked.
Tests: `tests/test_demo_store_loader.py` (match, mismatch, probe error), `tests/test_demo_labels.py` (both texts).

## 18. English (P8′, P9′) — DP-T11, first

**Label table.** Rename `static/labels.hu.json` → `static/labels.en.json`; same codes and sections, English texts.

- **Chosen: `labels.en.json`** — the name says the language the visitor sees; a later second language is one more
  file, not a rename. Rejected: `labels.json` (the language becomes implicit); keeping `labels.hu.json` with English
  content (the name would lie).
- Edits: `labels.py` (`LABELS_PATH`, docstring), `topics.py` docstring, `server.py` comment,
  `tests/test_demo_labels.py` (`answer_values` → `{"yes": "Yes", "no": "No"}`). The tests read `LABELS_PATH`, so the
  coverage tests follow the rename.
- Drafts (the user may reword): outcomes — ANSWERED "answered", DID_NOT_FIT "did not fit in the model's input",
  PARSE_FAILURE "the model's reply could not be read", RETRIEVAL_ERROR "the data lookup failed", PROVIDER_ERROR "the
  model provider returned an error", TIMED_OUT "not finished within the time limit"; stop reasons — done
  "finished", max_steps "reached the step limit", prompt_budget "ran out of input budget", errors "too many tool
  errors", overflow "the model's input filled up", runaway "the model kept thinking and gave no answer", deadline
  "ran out of time"; tiers — cypher-* "Step 1: database query (Cypher)", agent-* "Step 2: graph agent"; topics —
  routes "Routes through the plant", neighbours "Before and after: neighbours, sources, isolation", instruments
  "Instruments and control loops", items "Items, units and sheets"; error codes one-to-one, plus `no_api_key` "The
  demo has no model API key, so it cannot answer." and `plant_load_failed` "Loading this plant into the graph
  database failed."

**Strings.** `strings.js` English; `index.html` `lang="en"`. Money: `Intl.NumberFormat("en-US", {style:
"currency", currency: "USD"})`, ≥ $0.01 → "$2.00", below → 2 significant digits "$0.00071", 0 → "$0".

**Examples** — English, asked live like any question; their reference and verdict stay:

| Plant | File | How it is built | Why this one |
|---|---|---|---|
| D100 | `data/runs/cv1/demo/examples/D100.en.jsonl` | `examples --from data/runs/cv1/questions/D100/questions.jsonl --corpus D100 --wordings data/runs/cv1/demo/examples/D100.en.wordings.json --out …`; the wordings JSON `{id: text}` is a one-line local conversion of `data/runs/cv1/paraphrase_base_D100.json` (a list of `{id, family, text}`) | the same 36 questions as the PARA-R1 base and the current Hungarian examples (ids equal minus `#hu1`, so the pairings of §21 stay); all 36 are D100 dev questions with byte-equal text (checked 2026-10-16), so their gold is the dev gold |
| D1000 | `data/runs/cv1/demo/examples/D1000.jsonl` (exists) | per-family 2, seed 20261011 (its provenance file) | English counterpart of the current Hungarian file, same ids |

- Rejected for D100: `--per-family 2 --seed 20261011` on the dev file — no conversion and symmetrical with D1000,
  but only 6 of its 36 picks overlap the PARA base (computed with `select_per_family`, 2026-10-16), so the pairing
  and the §21.4 steps would change.
- The `examples` command does this unchanged (`--wordings` keeps the named questions in file order with their gold).
  `demo_config.json` → `D100.en.jsonl` and `D1000.jsonl` (backup first). The free replay check of revision 1 is gone
  with the replay path; the self-check is the examples test (ids, gold kept) plus the user's live try.
- U2 stays (typed → FREE_TEXT). U3 is moot (English question, English prompt, English answer).

## 19. Visual design system (P13) — DP-T6

### 19.1 Identity

The page should feel like a **drawing title block on drafting paper**, not a web template: warm paper background,
near-black ink, one blueprint blue, hairline rules instead of shadows, small upper-case field labels above values (as
a title block labels "DWG NO." above the number), and sheet references drawn as the **off-page connector flag** the
PDFs themselves use (demo-app.md §4.2). Instrument-bubble circles number the "how to use" steps. Tags, sheet numbers
and figures are set in a monospace face, so they read as data. Nothing else is decorated.

### 19.2 Tokens (`static/tokens.css`)

Light values on `:root`; dark values on `:root[data-theme="dark"]`. `theme.js` always sets `data-theme` to `light`
or `dark` on `<html>`, resolving "auto" through `matchMedia("(prefers-color-scheme: dark)")` and following its
`change` event, so each value is written once and no `@media` duplicate block exists. `color-scheme: light dark` on
`:root` lets form controls and scrollbars follow.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#f5f4ee` | `#11161c` | page background |
| `--surface` | `#ffffff` | `#182029` | cards, inputs, tooltip |
| `--surface-2` | `#eceff2` | `#212a34` | folded panels, table header, hover |
| `--ink` | `#17202a` | `#e5eaef` | body text, title-block rule |
| `--ink-muted` | `#4d5a67` | `#a3afbb` | labels, captions, hints |
| `--rule` | `#c8cfd6` | `#313d49` | decorative separators only |
| `--rule-strong` | `#77828e` | `#6f7d8b` | input and chip outlines (non-text 3:1) |
| `--accent` | `#1d5aa6` | `#6aa6f5` | primary button fill, active tab, selection |
| `--on-accent` | `#ffffff` | `#0b1420` | text on `--accent` |
| `--accent-ink` | `#174c8c` | `#8dbcff` | links, tags, chip text |
| `--accent-soft` | `#e2ecf8` | `#1d3350` | chip fill, chosen example |
| `--good` / `--good-soft` | `#1c7036` / `#e4f2e8` | `#5fc285` / `#16301f` | "correct" |
| `--bad` / `--bad-soft` | `#b3261e` / `#fbe8e6` | `#ff8b7e` / `#3a1916` | "does not match", errors |
| `--warn-ink` / `--warn-soft` / `--warn-rule` | `#7a4f00` / `#fdf1d2` / `#a87400` | `#f2c35b` / `#33290f` / `#b8860b` | store notices, plant-load line, fallback line |
| `--focus` | `#c45a00` | `#ffb14a` | focus ring |
| `--signal` | `#2a66c4` | `#76a9f0` | diagram signal links (dashed, as in the PDF) |
| `--series-1/2/3` | `#0072b2` / `#d55e00` / `#009e73` | `#56b4e9` / `#e69f00` / `#2ec4a0` | charts (Okabe–Ito colour-blind-safe set); each series also has its own marker shape |
| `--grid` | `rgb(23 32 42 / 0.05)` | `rgb(229 234 239 / 0.05)` | header graph-paper lines |

**Contrast (WCAG 2.x relative-luminance formula, computed by scratch `contrast.py`, 2026-10-16).** Light: ink on
paper 14.93; muted on surface-2 6.12 (the lowest text pair); accent-ink on accent-soft 7.18; on-accent on accent
6.85; good on good-soft 5.31; bad on bad-soft 5.54; warn-ink on warn-soft 6.34; rule-strong on paper 3.55; focus on
paper 3.96; warn-rule on surface 4.07; series 5.19 / 3.87 / 3.42 on surface. Dark: ink on paper 15.01; muted on
surface-2 6.51; accent-ink on accent-soft 6.56; on-accent on accent 7.39; good / bad on their soft fills 6.46 / 6.95;
rule-strong on surface 3.90; focus on paper 10.07; series ≥ 7.12. Every text pair ≥ 4.5 (AA body text); every
outline, focus ring and chart mark ≥ 3 (AA non-text). A first light `--warn-rule` (`#c98a00`, 2.95) failed and was
darkened.

**Type** — system stacks only; no web font, no CDN:

| Token | Value |
|---|---|
| `--font-ui` | `system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` |
| `--font-label` | `Bahnschrift, "DIN Alternate", "Segoe UI", system-ui, sans-serif` (DIN-like, ships with Windows 10+; the title-block voice for field labels and headings) |
| `--font-mono` | `ui-monospace, "Cascadia Mono", Consolas, "Liberation Mono", Menlo, monospace` (tags, DWG numbers, figures, Cypher) |
| `--fs-xs/sm/md/lg/xl/2xl` | `0.75 / 0.875 / 1 / 1.25 / 1.625 / 2rem` |
| `--lh-tight` / `--lh-body` | `1.25` / `1.5` |

Everything is in `rem`, so presentation mode scales the page by `html { font-size: 125% }`. `font-variant-numeric:
tabular-nums` on every figure.

**Space, shape, motion**

| Token | Value |
|---|---|
| `--sp-1…--sp-7` | `0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3rem` |
| `--r-1` / `--r-2` | `2px` / `4px` (crisp, technical; the flag chip is the only non-rectangular shape) |
| `--rule-w` / `--rule-w-strong` | `1px` / `2px` |
| `--dur-fast` / `--dur` / `--ease` | `120ms` / `180ms` / `cubic-bezier(.2, 0, 0, 1)` |
| `--header-h` | `3.5rem` |

`@media (prefers-reduced-motion: reduce)` sets both durations to `0ms` and replaces the running bar's animation with
the static timer text. Motion is used only for hover/focus colour, the tooltip fade and `<details>` chevrons.

**Focus:** `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }` on every interactive element,
never removed. Targets at least 24 × 24 CSS px (WCAG 2.2 target size, AA).

### 19.3 Layout

```
┌ title block: Plant-scale P&ID questions │ PLANT [D100 · 101 sheets|D1000 · 1000 sheets] │ GRAPH DB holds D1000 │ SPEND $0.02 / $5.00 │ [Ask|Results] │ What is this? │ Present │ ◐ ┐
├ drawing column ─────────────────────────────┬ panel ─────────────────────────────────────┤
│ [Find on the drawings: sheet or tag      ⏎] │ (What is this? box, dismissible)          │
│ ┌ PDF iframe (the paper stays white) ─────┐ │ store notice (if selection ≠ database)    │
│ │                                         │ │ Question [textarea]            [Ask]      │
│ └─────────────────────────────────────────┘ │ ▸ Example questions (36)                  │
│                                             │ result card (step list, route view)       │
└─────────────────────────────────────────────┴───────────────────────────────────────────┘
```

- CSS grid. ≥ 1280 px wide: columns `minmax(0, 3fr) minmax(22rem, 2fr)` (drawing ≈ 60 %, as today). 1024–1279 px:
  `1fr 1fr`. < 1024 px: one column, the drawing first at `60vh`, the panel below. At 1366 × 768 (common laptop) and
  1280 × 720 (common projector) the first rule applies; the header is one row of `--header-h`.
- The panel scrolls on its own; the drawing column never scrolls away.
- The **Results** tab replaces both columns (charts need the width); **Ask** brings them back with the PDF page
  unchanged (the iframe is hidden, not removed).
- Below 1024 px "What is this?", "Present" and the theme toggle fold into a "⋯" menu button.

### 19.4 Components

| Component | Look | States |
|---|---|---|
| **Header (title block)** | `--paper` with the 8 px `--grid` graph-paper background; 2 px `--ink` bottom rule; cells split by 1 px `--rule` verticals; each cell = `--fs-xs` upper-case `--font-label` label in `--ink-muted` above a `--fs-md` value | GRAPH DB cell shows the held plant; spend value turns `--warn-ink` above 80 % of the cap |
| **Plant switch** | segmented control of two radio buttons in the PLANT cell, each "D100 · 101 sheets" (`n_sheets` from status); selected = `--accent` fill, `--on-accent` text | selecting the other plant starts the load: phase text "Loading D100 into the graph database… 1.4 s (last time 2.3 s)" with the indeterminate bar, the ask panel disabled; done: "D100 loaded in 2.6 s"; error: `--bad` text with the folded message |
| **Tabs** | two buttons in the header, `role="tab"`, `aria-selected`; active = 2 px `--accent` underline | ← → move between tabs |
| **Theme toggle** | one icon button cycling auto → light → dark; `aria-label` from strings ("Theme: automatic / light / dark"); choice in `localStorage` key `pgdemo.theme` | — |
| **Intro box ("What is this?")** | `--surface` card, 4 px `--accent` left rule, heading in `--font-label`; three sentences; three steps numbered in 1.75rem circles drawn like ISA instrument bubbles (1 px `--ink` ring, mono digit); "Got it, hide this" text button | hidden state in `localStorage` key `pgdemo.introHidden`; the header's "What is this?" reopens it; never shown in presentation mode |
| **Store notice** | `--warn-soft` fill, 1 px `--warn-rule` border, `--warn-ink` text | only when the selection and the database disagree (after a failed switch) or on a store problem |
| **Ask panel** | label "QUESTION" (`--font-label`, xs); textarea `--surface`, 1 px `--rule-strong`, 3 rows growing to 6; primary button `--accent`; Ctrl+Enter asks | running: button disabled, 2 px indeterminate bar under the textarea plus "Asking… 4.3 s" (reduced motion: text only) |
| **Example list** | `<details>` "Example questions (36)"; topic headings `--fs-xs` upper-case `--font-label`, `--ink-muted`, with a 1 px rule; each question a full-width left-aligned text button, tag words in `--font-mono` | hover `--surface-2`; chosen = `--accent-soft` fill + 2 px `--accent` left rule; open until the first ask |
| **Result card** | `--surface`, 1 px `--rule`, 2 px `--ink` top rule; a title-block row of field labels (ANSWER · STEP · TIME · COST); answer `--fs-xl` semibold; sections "How does it know?", "Check" (examples), folded "Details" (tiers, Cypher query, agent steps, calls) and "How it works"; toolbar top right: "Copy" | fallback answer gets the amber line; `cache_hit_detected` gets a red line; `aria-live="polite"` region |
| **Cypher block** | `--surface-2`, `--font-mono` `--fs-sm`, `white-space: pre-wrap`, 1 px `--rule`, copy button | — |
| **Verdict pill** | `--fs-sm` semibold "correct" / "does not match" on `--good-soft` / `--bad-soft`, text `--good` / `--bad`; the word carries the meaning, colour repeats it | — |
| **Sheet chip** | button with a flag-shaped `::before` background (`clip-path: polygon(0 0, 85% 0, 100% 50%, 85% 100%, 0 100%)`, `--accent-soft`), text "DWG 464" in `--font-mono`, `--accent-ink`; the focus outline sits on the rectangular button, so the clip-path cannot cut it | hover: fill `--accent`, text `--on-accent`; `title` lists the tags on that sheet |
| **Tag token** | inline `--font-mono`, `--accent-ink`, 1 px dotted underline; a button | click jumps to its sheet (§20.3) |
| **Glossary term** | inline span, 1 px dotted `--ink-muted` underline, `cursor: help`, `tabindex="0"` | tooltip (§21.2) |
| **Glossary tooltip** | one shared element: `--surface`, 1 px `--ink` border, `--r-2`, max-width 22rem, `--fs-sm`, 6 px arrow; fade `--dur-fast` | hover after 150 ms, focus at once; Escape / blur / mouse-leave hide; flips above when there is no room below |
| **Status line** | under the ask button, `--fs-sm` `--ink-muted`: load state, policy | errors in `--bad` with a folded "Technical details" |
| **Tier and call tables** | horizontal rules only (engineering table), header `--surface-2`, `--font-label` xs upper-case; figures right-aligned mono | — |
| **Charts** (DP-T10) | inline SVG; axes and ticks 1 px `--ink-muted`; grid `--rule`; `--series-1…3` with markers circle / square / triangle; whiskers 1.5 px; labels `--fs-xs` | `<title>` hover text |
| **Route view** (DP-T19) | the PDF's glyph vocabulary: equipment rectangle, valve bow-tie, instrument circle; flow link solid `--ink` with arrowhead, signal link dashed `--signal`; a sheet-crossing edge carries a small flag glyph; the current step's items outlined `--accent`, answer items `--good` / `--bad` | §21.5 |
| **Presentation bar** | full-width strip under the header: "2 / 5", "◀ Back", "Next ▶", "Exit"; `--fs-lg` | §21.4 |

### 19.5 Files and checks

`static/tokens.css` (tokens, themes, base type; target ≤ 150 lines) and `static/app.css` (layout and components,
≤ 400 lines); DP-T10 adds `static/results.css`. Manual check in DP-T6: both themes and the toggle; a keyboard-only
walk-through (Tab reaches every control, focus always visible); 1366 × 768 and a 1000 px-wide window.

## 20. P&ID-engineer tools (P14)

### 20.1 What the demo can already reach (read 2026-10-16)

| Value | Where it lives | Notes |
|---|---|---|
| Tag → items | `LoadedCorpus.item_graph.ids_for_tag(tag)` (`qa/plant_api/item_graph.py`), folded by `normalize_scalar` | public, read-only use of frozen code |
| Item's class, unit, sheets | `ItemGraph.item(id)` → `ItemRecord.node_class`, `.unit_id`, `.sheets` (sorted) | |
| Every item (suggestions) | `ItemGraph.all_ids()` + `.item(id).tag` | |
| Direct edges | `ItemGraph.steps(id, direction, "any")` → `(neighbour, ItemEdge)`; `ItemEdge.relation` ∈ {send_to, send_signal_to, control, measured_by}; `ItemEdge.via` = off-page stub keys crossed; `sheet_of_key(key)` gives a stub's sheet | |
| Sheet → PDF page | `LoadedCorpus.pages` (from `drawings.index.json`; D100 101 pages, D1000 1,000) | |
| Tags of answer and question, with sheets | `DemoAnswer.answer_sheets[].tags` (`evidence.answer_tags`: question tags first, then answer tags) | already sent to the page |
| Sheets the agent read | `DemoAnswer.read_sheets` (from `LiveAnswer.trace_sheets`) | the steps themselves come from the recorded trace |
| The whole trace: Cypher query, rows as the model saw them, tool calls, observations | `DemoAnswer.trace` (§17.3, recorded by the demo's HTTP transport) | rows only as far as the prompt held them (the tier's row cap) |
| Answer type, final answer | `LiveAnswer.answer_type`, `.final_answer.answer` | SHEET_SET answers are sheet ids |
| Class families for glyphs | `graph.schema.EQUIPMENT_CLASSES`, `VALVE_CLASSES`, `GENERATOR_CLASSES` | |

### 20.2 Decisions

| Tool | Verdict | Reason | Task |
|---|---|---|---|
| **Tag lookup** ("where is P-151-1?") | **yes** | the first thing an engineer does with a drawing set; instant, no model call (it is a drawing-index lookup, not an answer); shows the cross-sheet identity the thesis resolves (one item, several sheets) | DP-T15 |
| **Plain-English class names** | **yes, Must** | `ProcessSignalGeneratingFunction` (the reference answer of "What type of item is LT-19-3?") means little to a visitor; shown as "sensor / transmitter (ProcessSignalGeneratingFunction)" — the system's own word stays visible | DP-T7 |
| **Clickable tags and sheet ids in the answer** | **yes** | the answer is where the eye is; uses tags the server already resolved — no second matching rule | DP-T16 |
| **Session history** | **dropped** (user, 2026-10-16: "why would we need it?") | — | — |
| **Copy answer** | **yes** | engineers paste answers into notes or tickets; one button | DP-T16 |

### 20.3 Specifications

**Tag lookup (DP-T15).** The drawing bar's "go to DWG" box becomes **one search box** ("Find on the drawings: sheet
number or tag"). Input matching `^(DWG\s*)?\d+$` that names a page in the index → jump (today's behaviour). Anything
else → `GET /api/corpora/{id}/tags?q=<text>`.

```python
# demo/app/tag_lookup.py; the response types live in api_models.py
class TagHit(BaseModel):
    item_id: str; tag: str | None; node_class: str; unit_id: str | None
    sheets: tuple[SheetLink, ...]                     # page order
class TagLookup(BaseModel):
    query: str; hits: tuple[TagHit, ...]; suggestions: tuple[str, ...]   # ≤ 10, folded-prefix match
@dataclass(frozen=True)
class TagIndex:                    # sorted (folded tag, tag) pairs over all_ids(); built once per corpus
    @classmethod
    def build(cls, item_graph: ItemGraph) -> TagIndex
    def suggest(self, query: str, limit: int = 10) -> tuple[str, ...]      # bisect on the folded prefix
def lookup(query: str, item_graph: ItemGraph, index: TagIndex, pages: Mapping[str, int]) -> TagLookup
```

`AppState.tag_lookup(corpus_id, q)` builds the corpus's `TagIndex` on first use and keeps it (the D1000 build time is
**not measured**; the coder logs it once). `q`: `Query(min_length=1, max_length=64)`; the page never sends a blank.
Errors: existing `unknown_corpus`, `corpus_not_ready`. Screen, under the bar:

```
P-151-1 · centrifugal pump · unit 151 · on 2 sheets:  [DWG 12] [DWG 13]
```

No hit → "No item with this tag in this plant." plus "Did you mean:" with up to 10 suggestion buttons.

**Clickable tags (DP-T16).** `tagtext.js` exports a pure `splitByTags(text, tags) -> [{text, tag | null}]` that
matches the exact tag strings of `answer_sheets[].tags`, longest first, with alphanumeric look-around boundaries. A
tag token's click jumps to its first sheet in page order; a further click cycles through its sheets; `title` = "On 3
sheets: DWG 12, 40, 41 — click again for the next". SHEET_SET answers render each value as a sheet chip (page from
the drawing index).

**Copy (DP-T16).** "Copy" on every card writes plain text built by `STRINGS.copyText(...)`: question, plant (with
sheet count), answer, sheets ("DWG 12, DWG 40"), who answered, time, cost. `navigator.clipboard.writeText` (127.0.0.1
is a secure context); failure → "Copying failed."; success → "Copied" for 2 s.

**Class names (DP-T7).** `labels.en.json` section `class_names` covers `GENERATOR_CLASSES` (12 classes,
`graph/schema.py`) plus `UnresolvedOffPageConnector` and `GenericItem`; a pytest checks it. `format.className(c)` →
`"{name} ({c})"`; a missing class shows the raw name with a console warning. Drafts: CentrifugalPump "centrifugal
pump", Compressor "compressor", Tank "tank", PressureVessel "pressure vessel", ProcessColumn "process column",
HeatExchanger "heat exchanger", GlobeValve "globe valve", BallValve "ball valve", CheckValve "check valve",
ProcessSignalGeneratingFunction "sensor / transmitter", ProcessInstrumentationFunction "instrument / control-loop
function", ActuatingFunction "actuator", UnresolvedOffPageConnector "unpaired off-page connector", GenericItem "other
item". Free-text answers are shown as they come.

## 21. The five extra ideas

### 21.1 "What is this?" intro box (P15) — DP-T6

```
┌▌What is this? ──────────────────────────────────────────────────────┐
│ (three sentences)                                                   │
│ (1) Pick a plant   (2) Ask   (3) Click a DWG label                  │
│                                              [Got it, hide this]    │
└─────────────────────────────────────────────────────────────────────┘
```

- **Data:** `n_sheets` of each plant from `/api/status` (no number typed). Texts in `strings.js` (drafts):
  > This demo turns the piping and instrumentation diagrams (P&IDs) of a generated chemical plant into a graph:
  > equipment, valves and instruments are the nodes, pipes and signal lines are the edges. Every question you ask is
  > answered live by a language model working on the graph of the whole plant, even when the answer runs across
  > many drawing sheets — what you see is the real time and cost. Next to every answer you see which sheets it came
  > from, and one click takes you there.
  1. Pick a plant: {n_a} or {n_b} drawing sheets.
  2. Click an example question, or type your own.
  3. Click a DWG label: the drawing on the left jumps to that sheet.
- "generated" is required: both plants come from the generator (title block "simplified generated drawing",
  demo-app.md §4.2).
- **API:** none. **Tests:** string scan (every `STRINGS.*` key used exists). **Manual (coder):** shown on first
  visit; "Got it, hide this" hides it across reloads; "What is this?" shows it again; numbers equal `/api/status`.

### 21.2 Glossary tooltips (P15) — DP-T7

- **Markup:** `glossary.js` exports `term(key, visibleText)` → `<span class="term" data-term="key" tabindex="0"
  aria-describedby="glossary-tip">`. One shared tooltip `#glossary-tip` (`role="tooltip"`), wired by event delegation
  on `document` (`mouseover`, `focusin`, `mouseout`, `focusout`, `keydown` Escape), so terms added later need no
  re-wiring. Touch: a tap toggles it.
- **Data:** `labels.en.json` section `glossary` (key → 1–2 plain sentences); `Labels` gains `glossary: dict[str,
  str]`. The visible word stays in the `strings.js` sentence.
- **Terms and drafts:**

| key | text (draft) |
|---|---|
| `pid` | P&ID (piping and instrumentation diagram): the engineering drawing of a plant, showing equipment, valves and instruments and the pipes and signal lines that connect them. A large plant's P&ID is split over many sheets. |
| `sheet` | Drawing sheet: one page of the P&ID, identified by its DWG number. Each page of the PDF on the left is one sheet. |
| `off_page_connector` | Off-page connector: the flag-shaped symbol at a sheet's edge ("TO DWG 12") saying that a pipe or signal line continues on another sheet. The system uses these flags to join all sheets into one graph. |
| `tag` | Tag: the identifier of an item on the drawing, such as P-151-1. The same item can appear on several sheets; the system treats them as one item. |
| `unit` | Process unit: a section of the plant that belongs together, with its own number. |
| `loop` | Control loop: a measurement, a controller and the valve it moves, working together — for example a level loop measures a tank's level and opens or closes a valve. |
| `graph_db` | Graph database (Neo4j): stores the whole plant as a graph so it can be queried. It holds one plant at a time, so switching plants reloads it. |
| `cypher` | Cypher: the query language of the Neo4j graph database. In step 1 the language model writes such a query, and the database answers it from the graph of the whole plant. |
| `agent` | Graph agent: step 2. The language model explores the plant graph step by step with tools (search, neighbours, path), sheet by sheet. |
| `cascade` | Cascade: the two steps in order. The database query tries first; if the system does not accept its answer, the question goes to the graph agent. |
| `k` | k: how many links in the correct answer's evidence cross from one drawing sheet to another — through an off-page connector, or because the same item is drawn on both sheets. The larger k, the more the question spans sheets. |
| `u` | u: how many links in the correct answer's evidence cross from one process unit to another. |
| `model_time` | Model time: the time of the language-model calls plus local computing, counted the way the evaluation counts it. |
| `wall_time` | Answer time: how long this answer took on this machine, from pressing Ask to the result (without loading a plant). |
| `wilson` | Wilson interval: the 95 % confidence band around a measured accuracy; it is wider when there are few questions. |
| `context_wall` | Context wall: the number of sheets above which the text of the whole drawing set no longer fits into the language model's input. |
| `context_rag` | ContextRAG: the published method measured on single sheets — it puts the whole graph as text into the model's input. |

- The `k` / `u` texts follow the `Question` field definitions (`qa/models.py`), correcting revision 1.
- **Tests:** `test_demo_labels.py` — every glossary text non-empty; `test_demo_page.py` — every `term("…")` and
  `data-term="…"` key in `static/*.js|html` exists in `glossary`, and every glossary key is used. **Manual (coder):**
  hover and Tab-focus each term; Escape closes; readable in both themes; flips above near the bottom edge.

### 21.3 "Same question on the other plant" (P16) — dropped (user, 2026-10-16)

Dropped (ADR-0056 7B): a comparison needs both plants within one interaction, which contradicts the user's model —
*one plant chosen deliberately, then all questions go to it; no bouncing between D100 and D1000*. The measured scale
effect stays on the Results tab (EXP-0001 ladder, EXP-0002 H100 vs H1000). The pairing analysis (same family, same
ordinal: D100 TK-3-3 → T-47-4, k = 7 ↔ D1000 E-19-2 → C-395-7, k = 103) is kept here only as a record. DP-T17 is
dropped; its number is not reused.

### 21.4 Presentation mode (P17) — DP-T20 (confirmed by the user, 2026-10-16)

- **Status:** confirmed; DP-T20 stays last.
- **Rules:** one plant per sequence (no reload mid-sequence; the presenter selects the plant before starting,
  which is the normal plant switch of §17.2); every step asks live; nothing pre-stored.
- **Data:** a list in the **local** `demo_config.json` (the ids name local, git-ignored example files):

```python
class PresentationStep(BaseModel):            # config.py
    kind: Literal["example", "results"] = "example"
    question_id: str | None = None            # kind="example" needs it
class PresentationSequence(BaseModel):
    corpus_id: str                            # the one plant of the sequence
    title: str
    steps: tuple[PresentationStep, ...]
class DemoConfig: ...; presentation: tuple[PresentationSequence, ...] = ()

class PresentationItem(BaseModel):            # api_models.py
    index: int; kind: Literal["example", "results"]; question_id: str | None; text: str | None
    missing: Literal["unknown_question", "corpus_not_ready"] | None
class PresentationView(BaseModel):
    sequences: tuple[tuple[str, str, tuple[PresentationItem, ...]], ...]   # (corpus_id, title, items)
```

  `GET /api/presentation` resolves the steps against the loaded corpora. The "Present" button offers the sequences of
  the plant the database holds; another plant's sequence asks the visitor to switch plant first.
- **Screen:** "Present" in the header, or `/?mode=present`. `html.present` sets `font-size: 125%`, hides the intro
  box and the example list; columns become `1fr 1fr`; the answer is `--fs-2xl`; the "Asking… 4.3 s" phase text is
  large, so the waiting is part of the story. The bar: "2 / 4 · ◀ Back · Next ▶ · Exit". "Next" fills the example
  and asks (or opens the Results tab). Keys: → / PageDown next, ← / PageUp back (presentation clickers send these),
  Escape exits.
- **Draft sequences** (the user may change them in the local config):
  - D1000 (the default plant): `D1000:LOOKUP_TYPE:V-361-5` (a one-sheet lookup, plain class name);
    `D1000:CONNECTED:E-19-2|C-395-7` (k = 103); `D1000:FLOW_PATH:CHV-5-18|P-419-1` (k = 17, a 64-item reference path;
    both recorded tiers answered it correctly — a live answer may still differ; shows the route view); `results`.
  - D100: `D100:LOOKUP_TYPE:LT-19-3`; `D100:FLOW_PATH:BV-1-9|GV-13-2` (k = 7, a 44-item reference path); `results`.
- **Tests:** `tests/test_demo_presentation.py` — config validator (one corpus per sequence, example steps need ids);
  `missing` resolution over a fake state; `[]` when unset. **Manual:** coder — bar, keys, resolution with the fake
  transport; user (live) — one sequence at 1280 × 720.

### 21.5 "How the model got there": the interactive route view (P18) — DP-T18 (data), DP-T19 (view)

High priority for the user (2026-10-16). It replaces revision 2's first "answer diagram": with the recorded trace
(§17.3) the demo can show the route the system **actually** took, not only the answer's items.

**What is drawn, and from where.**

| Layer | Source | Honest because |
|---|---|---|
| Items the model saw, step by step | `AskTrace.agent[i].items` (args and observations of each tool call); for the Cypher tier, the items named in the rows | they are in the requests the model received (§17.3) |
| The answer's items, and for a `TAG_PATH` answer their order | `LiveAnswer.final_answer` | it is the answer |
| Edges between shown items | **direct** edges of the demo's loaded `ItemGraph` (`steps(id, "any", …)`), with `via` stubs → sheet-crossing marks (`sheet_of_key`) | they are drawing connections between items the model actually saw; no path search |
| Path hops of a `TAG_PATH` answer | consecutive answer items: solid if a direct edge exists, dashed "no direct connection on the drawings" otherwise | it checks the answer against the drawings, it does not invent one |

Still **out:** a demo-computed shortest path presented as the model's reasoning.

```python
# demo/app/route.py — pure functions over ItemGraph and AskTrace, no I/O (replaces the first diagram.py design)
NodeFamily = Literal["equipment", "valve", "instrument", "other"]
class RouteNode(BaseModel):
    item_id: str; tag: str | None; node_class: str; family: NodeFamily; unit_id: str | None
    sheets: tuple[SheetLink, ...]
    first_step: int | None            # the step that first showed it to the model; None = only in the question/answer
    in_answer: bool; in_question: bool
class RouteEdge(BaseModel):
    source: str; target: str
    relation: Literal["send_to", "send_signal_to", "control", "measured_by", "none"]   # "none" = path gap
    crossed_sheets: tuple[str, ...]
    on_answer_path: bool
class RouteView(BaseModel):
    steps: tuple[str, ...]            # one short label per step ("find {tag: E-28-2}", "Cypher query"), for the slider
    nodes: tuple[RouteNode, ...]; edges: tuple[RouteEdge, ...]
    answer_path: tuple[str, ...]      # item ids in answer order (TAG_PATH), else ()
    omitted_nodes: int
def route_view(question_text: str, live: LiveAnswer, trace: AskTrace,
               item_graph: ItemGraph, pages: Mapping[str, int]) -> RouteView | None
```

`DemoAnswer` gains `route: RouteView | None` (None when no item is named anywhere). Caps: 150 nodes (the earliest
steps and every answer item kept first; the rest counted in `omitted_nodes`), 300 edges; the step list in Details stays
complete. Reference sizes for scale (example files, counted 2026-10-16): answer paths up to 64 items, tag sets up to 52.

**The view (`route.js`, inline SVG, no library).**
- **Layout:** deterministic "time layers" — column = the step that first showed the item (items only in the question
  sit in column 0, answer-only items in a last column); rows in order of appearance within a step. No force layout
  (jittery, not reproducible). For a `TAG_PATH` answer a toggle "Answer path" re-lays the answer items as the snake
  chain (rows of 6) with the hops of the table above.
- **Stepping:** "◀ Step · Step ▶ · Play" and a slider over `steps`; at step i only items with `first_step ≤ i` and
  edges among them are drawn; the items of step i are outlined in `--accent`; the step list in Details is synced (a
  click on a step moves the slider). At the end the answer items get a 3 px `--good` outline (or `--bad` when the
  example's verdict says "does not match") and the answer path's edges are thickened.
- **Nodes:** the PDF's glyphs (equipment rectangle, valve bow-tie, instrument circle), tag in mono. Hover/focus →
  tooltip: tag, plain class name, unit, sheets. Click → jumps the PDF to the item's first sheet (a second click cycles
  its sheets). Edges: flow solid `--ink`, signal dashed `--signal`, a flag glyph and "DWG 3 → DWG 8" where the edge
  crosses sheets.
- **Keyboard and motion:** nodes are focusable in step order; ← → step; Play advances once a second and is replaced
  by manual stepping under `prefers-reduced-motion`.
- **Cypher-only answers:** one step ("query → N rows"); the items named in the rows are the nodes.

**Tests:** `tests/test_demo_trace.py` (DP-T14) over recorded fake exchanges: query and rows parsed; observations
paired with the right tool call, the last one taken from the final request; unparsable parts kept and flagged; join
by response id; abandoned call ignored. `tests/test_demo_route.py` (DP-T18) over the toy graph
`tests/qa_plant_api_toy.py`: `first_step` assignment; only direct edges; path gaps; caps; `None` without items.
**Manual:** coder — a fake-transport agent answer of 3 steps on the toy plant steps through correctly; user (live) —
a D1000 FLOW_PATH example and a NEIGHBOURS_DOWNSTREAM example; hover, click-to-sheet, both themes.

## 22. API changes (revision 2)

| Route / type | Change | Task |
|---|---|---|
| label table | `labels.en.json` (done, `b068363`); error codes `no_api_key` (DP-T12), `plant_not_loaded`, `plant_load_failed` (DP-T13); job state `needs_paid` removed (DP-T12) | DP-T11…T13 |
| `AskRequest` | `tier2_only` removed | DP-T12 |
| `JobStatus` | `needs_paid` state and field removed; `+ phase`, `+ open_s` | DP-T12 |
| `CorpusStatus` | `open_s` (dict by mode) removed; `store` derived from the cached held ids | DP-T12, DP-T13 |
| `POST /api/plant`, `GET /api/plant`; `AppStatus.plant` | new — the plant switch | DP-T13 |
| `DemoAnswer` | `+ trace: AskTrace`, `+ cache_hit_detected` (DP-T14); `+ route: RouteView` (DP-T18) | DP-T14, DP-T18 |
| `DemoConfig` | `cache_path` removed (DP-T12); `+ presentation` (DP-T20) | |
| `Labels` | `+ class_names`, `+ glossary` | DP-T7 |
| `GET /api/corpora/{id}/tags?q=` | new → `TagLookup` | DP-T15 |
| `GET /api/presentation` | new → `PresentationView` | DP-T20 |

A FastAPI validation error (422, list-shaped `detail`) is shown with the generic `STRINGS.unexpectedError` text.

## 23. Files (after revision 2)

```
src/plantgraph/demo/app/{live_cascades,store_loader,trace_recorder,ask_trace,route,tag_lookup,presentation,results}.py  new
src/plantgraph/demo/app/{cascade_pool,seed_cache,coverage}.py                           deleted
src/plantgraph/demo/app/{config,api_models,answering,jobs,state,corpus_runtime,store_probe,server,labels,topics,__main__}.py  edited
src/plantgraph/demo/app/demo_config.example.json                                        edited
src/plantgraph/demo/app/static/index.html                                               edited (module entry, skeleton only)
src/plantgraph/demo/app/static/{tokens,app,results}.css                                 tokens, results new
src/plantgraph/demo/app/static/strings.js                                               ES module, English
src/plantgraph/demo/app/static/{app,api,dom,labels,format,theme,intro,ask,plant,answer,details,
    glossary,viewer,lookup,tagtext,route,present,results,charts}.js                     ES modules
src/plantgraph/demo/app/static/labels.en.json                                           (DP-T11)
tests/test_demo_{app,page,labels}.py                                                    edited
tests/test_demo_{seed_cache,coverage}.py                                                deleted
tests/test_demo_{live,store_loader,trace,route,tags,presentation,pdf_route,results}.py  new
data/runs/cv1/demo/demo_config.json                                                     local: presentation sequences
```

Every file ≤ 400 lines; `answer.js` keeps the card and delegates the tier table and step list to `details.js` and
the graph to `route.js`.

## 24. Tests and self-measurement (revision 2)

- **Live path** (`test_demo_live.py`, DP-T12, fake transport): two identical asks send two network requests (no cache
  read); the cascade is closed after each job; every `n_cached` is 0; a forced cached call sets
  `cache_hit_detected`; no API key → corpus `error` / `no_api_key`; the reservation is released with the real spend.
- **Plant switch** (`test_demo_store_loader.py`, DP-T13, fake loader and probe): switching to the held plant does
  nothing; to the other plant wipes then loads, in that order, timed; an ask during a switch → 409 `busy`; an ask on
  a plant not held → `plant_not_loaded` with no model call; a failed load → `plant_load_failed`, the held-ids cache
  refreshed. **Measured locally by the coder (free, Neo4j only, no model call):** wipe + load seconds D1000 → D100
  and D100 → D1000, 3 times each, ending with D1000 loaded; reported in the chat.
- **Trace** (`test_demo_trace.py`, DP-T14) and **route** (`test_demo_route.py`, DP-T18): §21.5.
- **Page invariants** (`test_demo_page.py`, string scans over all static files): every API path any module calls
  exists (widened from `app.js` to `static/*.js`); no file over 400 lines; offline — no `http://` or `https://`
  except the SVG namespace `http://www.w3.org/2000/svg`; no Hungarian leftovers — none of `áéíóöőúüű` (either case)
  in `strings.js`, `labels.en.json` or `index.html`; every `STRINGS.<key>` used is defined; every `label("<section>",
  "<key>")` literal exists; glossary keys used ⇔ defined; one `type="module"` entry script; no replay /
  `needs_paid` display path left.
- **Labels:** `class_names` ⊇ `GENERATOR_CLASSES ∪ {UnresolvedOffPageConnector, GenericItem}`; glossary non-empty;
  every new error code has a text.
- **Server:** tag lookup, presentation, `Cache-Control` and the versioned PDF URL (DP-T8, new
  `test_demo_pdf_route.py`; `test_demo_app.py` is at 400 lines and only shrinks in DP-T12).
- **JavaScript logic** has no automated test (a Node runner would need files outside the freeze's allowed paths);
  pure functions (`format.js`, `tagtext.js`, the layout function of `route.js`) stay free of DOM code.
- **Who checks what by hand.** Coders make no paid call: their manual checks use the fake transport or no model.
  Every check that needs a live answer is marked "user, live" and runs when the user tries the demo after DP-T7.

## 25. Coder tasks (revision 2, re-cut 2026-10-16 after the user's decisions)

Sonnet, one at a time, one commit each; ruff, `mypy --strict`, pytest green; offline; no paid call; ES modules, no
build step, no external code; never stop the running server — the user restarts it.

| # | Task | Files | Tests / acceptance | Size |
|---|---|---|---|---|
| DP-T11 | **English switch.** §18 | — | **done** (`b068363`) | S |
| DP-T12 | **Live only.** §17.1, §17.4 (spec unchanged; in progress) | `live_cascades.py` (new; replaces `cascade_pool.py`), `jobs.py`, `state.py`, `corpus_runtime.py`, `api_models.py`, `config.py`, `__main__.py`, `labels.en.json`; delete `seed_cache.py`, `coverage.py` and their tests; `tests/test_demo_app.py` (shrinks), `tests/test_demo_live.py` (new) | §24 live path; median open seconds of 5 opens per plant (fake transport) reported | M |
| DP-T13 | **Plant switch = load.** §17.2 | `store_loader.py` (new), `state.py`, `jobs.py` (the `plant_not_loaded` check), `server.py` (`/api/plant`), `api_models.py`, `store_probe.py`, `labels.en.json`, `tests/test_demo_store_loader.py` (new) | §24 plant switch; local wipe + load measurement, ending on D1000 | S/M |
| DP-T14 | **Recorded trace.** §17.3; includes the follow-up change to `live_cascades.py` (`AskHandle` with the recorder) | `trace_recorder.py` (new), `ask_trace.py` (new), `live_cascades.py`, `jobs.py` (log offset, snapshot before close), `answering.py`, `api_models.py`, `tests/test_demo_trace.py` (new) | §21.5 trace tests; the slow-response timeout test | M |
| DP-T6 | **Page restructure, design system, header, plant switch, intro box, ask panel.** §5.1, §17.2 (page side), §19, §21.1 | `index.html`, `tokens.css` (new), `app.css`, `strings.js`, `app.js`, `api.js`, `dom.js`, `labels.js`, `format.js`, `theme.js`, `intro.js`, `ask.js`, `plant.js` (new: switch, load phase, polling), `answer.js` (today's rendering, labels via `labels.js`), `viewer.js` (today's jump moved), `tests/test_demo_page.py` | page invariants; **manual (coder):** starts on the held plant; selecting the other plant shows the load phase and its seconds, asking disabled meanwhile (fake loader in a test server); examples by topic; click fills, edit clears; intro hide/show; theme follows the system, toggle works; keyboard walk; 1366 × 768 and < 1024 px | M |
| DP-T7 | **Result card, step list, glossary, class names.** §7 (k/u per §21.2, en-US money), §17.3 card facts and step list, §20.3 class names, §21.2 | `answer.js`, `details.js` (new: tier table, step list with Cypher block, rows table and agent steps, call table), `glossary.js` (new), `format.js`, `strings.js`, `labels.en.json`, `labels.py`, `app.css`, `tests/test_demo_labels.py`, `tests/test_demo_page.py` | label coverage; glossary keys; **manual (coder, fake transport):** card, step list, money, glossary. **→ the user tries the demo here (live):** D1000 examples answered by step 1 and by step 2 with their real query, rows and tool calls; a switch to D100 and a D100 question; a typed question | M |
| DP-T18 | **Route data.** §21.5 | `route.py` (new), `api_models.py`, `answering.py`, `tests/test_demo_route.py` (new) | §21.5 route tests | S/M |
| DP-T19 | **Interactive route view.** §21.5, §19.4 | `route.js` (new), `answer.js`, `details.js` (step sync), `strings.js`, `app.css` | manual §21.5 (coder with a fake 3-step answer; user live) | M |
| DP-T8 | **PDF jumps.** §8 | `viewer.js`, `server.py` (header), `tests/test_demo_pdf_route.py` (new) | header; versioned URL; manual Edge + Chrome, 5 jumps on D1000 → `PDF_JUMP`, reported | S **Done** (`799249d`): fresh iframe per jump (the fragment-only mode failed in headless Edge and Chrome, so `PDF_JUMP` was dropped); user manual test 2026-10-16: jumps work in Edge and Chrome; route view confirmed good by the user the same day. |
| DP-T9 | **Results projection + route.** §9.1 (unchanged) | `results.py`, `config.py`, `server.py`, `tests/test_demo_results.py` | as revision 1 | M |
| DP-T10 | **Results tab.** §9.2, English captions, §19 chart styling, glossary `wilson`, `context_wall`, `context_rag` | `results.js`, `charts.js`, `results.css` (new), `index.html`, `strings.js` | as revision 1, plus both themes and marker shapes | M |
| DP-T15 | **Tag lookup.** §20.3 | `tag_lookup.py` (new), `api_models.py`, `state.py`, `server.py`, `viewer.js` (search box), `lookup.js` (new), `strings.js`, `app.css`, `tests/test_demo_tags.py` (new) | server tests; **manual (coder):** "P-151-1" on D1000 → class, unit, sheet chips; "464" still jumps; "P-15" → suggestions; unknown → message | S/M |
| DP-T16 | **Answer tools: clickable tags, sheet-id answers, copy.** §20.3 (no history) | `tagtext.js` (new), `answer.js`, `strings.js`, `app.css` | page invariants; **manual (coder, fake transport):** tag click cycles its sheets; SHEET_SET chips jump; copy pastes the template. **Note (2026-10-16):** also carries the store guard §17.6 (`store_loader.py`, `state.py`, `server.py`, `labels.en.json`, `ask.js`); tags take their sheets from `answer_sheets[].tags` (already complete per tag, page order), so no `/tags` call per click | S |
| DP-T21 | **Live progress + lost time.** §17.5 (added 2026-10-16 after the first live try) | see §17.5 Files | §17.5 tests; manual: fake transport with a blocking reply and two failed attempts | S/M |
| DP-T20 | **Presentation mode** (confirmed). §21.4 | `config.py`, `presentation.py` (new), `api_models.py`, `server.py`, `present.js` (new), `app.css`, `strings.js`, `demo_config.example.json`, `tests/test_demo_presentation.py` (new); **locally:** the sequences into `demo_config.json` (backup first) | tests §21.4; manual §21.4 | M |
| ~~DP-T17~~ | ~~Same question on the other plant~~ | — | **dropped** (user, 2026-10-16: no bouncing between plants; ADR-0056) | — |

**Order:** DP-T12 → DP-T13 → DP-T14 → DP-T6 → DP-T7 (**the user tries the demo, live**, with the step-by-step trace
as text) → DP-T18 → DP-T19 (the interactive route view, right after the first try) → DP-T21 (live progress, from the first try) → DP-T8 → DP-T9 → DP-T10 →
DP-T15 → DP-T16 → DP-T20. DP-T18/DP-T19 move ahead of DP-T8 because the route view is the user's high-priority item;
it is too large to fit into DP-T7, so the first try shows the same trace as a step list and the graph follows next.

## 26. Open questions

None blocking. The user decided on 2026-10-16 (ADR-0056): plant switch by explicit selection; comparison dropped;
presentation mode kept; session history dropped; English drafts accepted as written; theme follows the system
setting (with the toggle). The presentation sequences in §21.4 are drafts the user may edit in the local config.

## 27. Sources (revision 2)

| Figure | Source |
|---|---|
| 400 lines of `tests/test_demo_app.py`; 341 lines of `app.js` | `wc -l`, 2026-10-16 |
| Session cap $5.00 | `data/runs/cv1/demo/demo_config.json` |
| Read-through cache in the paid client; no read-off switch | `qa/cascade/live_build.py`, `qa/harness/clients.py`, `llm/cache.py`, `llm/client.py` (read 2026-10-16) |
| `Path(":memory:")` gives an in-memory SQLite database, no file | scratch check, Python 3.12, 2026-10-16 |
| Call-log fields and purpose counts (cypher 289, answer 554, agent_step 940) | `data/runs/cv1/demo/calls.jsonl`, counted 2026-10-16 |
| Cache stores key + response only; the SDK gets the demo's `http_client`; `httpx2` 2.13.1 with `BaseTransport` / `HTTPTransport`; no streaming; agent observations as `user` messages; Cypher rows in the final-step context | `llm/cache.py`, `llm/client.py`, `qa/harness/clients.py`, `qa/agent/loop.py`, `qa/strategies/cypher_rag.py`; `import httpx2` check, 2026-10-16 |
| Ingest 3.1 / 26.1 s | `docs/private/30-experiments/_results.md` row INFRA-1 |
| `load_total` 2.25 / 8.59 s; `load_wipe` 0.02 s at D1000 | `data/runs/cv1/neo4jplant/{D100,D1000}/ingest.json` `stage_seconds` |
| $0.01865 for 36 live D1000 asks, median 7.5 s; ≈ $0.0005 per ask | ADR-0055 outcome log 2026-10-12; division = arithmetic |
| $0.00071 per question | `_results.md` row EXP-0002-H1000 (revision 1 §16) |
| PARA-R1 hu 142/144, en 102/108 | `_results.md` row PARA-R1 |
| 18 families × 2 examples per plant; k values; 44 / 64 / 52 reference sizes; example ids and texts | `data/runs/cv1/demo/examples/{D100,D1000}.jsonl`, `data/runs/cv1/paraphrase_base_D100.json`, counted 2026-10-16 |
| 36/36 PARA base ids in the D100 dev file with equal text; 6/36 overlap of per-family-2 | scratch checks over `data/runs/cv1/questions/D100/questions.jsonl` and `select_per_family`, 2026-10-16 |
| CHV-5-18 → P-419-1 correct in `CYPL2-D1000` and `AGL3-D1000` | `data/runs/cv1/runs/{CYPL2,AGL3}-D1000/answers.jsonl` |
| D100 101 / D1000 1,000 pages | `data/runs/cv1/drawings/D*/drawings.index.json` |
| Contrast ratios | architect scratch `contrast.py` (WCAG 2.x formula), 2026-10-16 |
| 12 generator classes | `graph/schema.py` (`NodeClass` docstring, `GENERATOR_CLASSES`) |
| k, k_connector, k_identity, u definitions | `qa/models.py` `Question` field comments |
