---
component: llm/* + qa/* (LLM client, strategies, question generator, harness, judge)
status: draft — awaiting review
related: [ADR-0001, ADR-0007, ADR-0010, ADR-0011, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0017, ADR-0018, ADR-0021, kg-construction.md]
date: 2026-09-26
revised: 2026-09-26 — reconciled with the built resolver, store and ingest code, and with ADR-0021 (§2.1, §18.1)
author: architect (Opus 5.5)
---

# Design: the Q&A system and its evaluation

> **In five lines.**
> 1. There is **one harness** for two experiments. EXP-0001 reproduces ChatP&ID: 19 questions, LLM judge. EXP-0002 is the plant-scale sweep plus the headline, with programmatic ground truth.
> 2. There are **five strategies**: ContextRAG, VectorRAG, PathRAG, CypherRAG and Hierarchical, plus an optional Agentic one. All of them end in **one shared JSON final-answer step**. "Did not fit" is recorded as an outcome in its own right.
> 3. **Questions are generated from the ground-truth plant graph.** The reference functions are plain Python over networkx, and every question is stratified by k, the number of off-page connectors in its evidence.
> 4. **LLM calls go through one cached client.** It talks to OpenRouter ~~and a local backend~~, and every reported call can be replayed without API access. *(revised 2026-09-26, local runtime check: no local LLM runtime is installed on this machine, §6. Every coder acceptance check runs on a fake transport or the replay cache; **no paid call runs without the user's explicit approval**.)*
> 5. **A pilot comes before any reported run.** It measures the context wall, cost, latency and variance, and only then are the question counts fixed.
>
> *(revised 2026-09-26, ADR-0021)* EXP-0001 scores only ChatP&ID's questions that need no equipment data. The datasheet questions are listed as **out of scope — not part of this thesis**, and the comparison with 0.91 is made on the scored group only (§10).
>
> The coder task list is §18; what the built code changed in it is §18.1. The pre-registered headline criteria are §13.3.

## 1. What this is, and which part of the claim it serves

The claim (`00-index.md`) is that the retrieval optimum is a function of corpus scale, and that ChatP&ID's single-sheet optimum (ContextRAG, 0.91) inverts at plant scale. This note builds three things:

- **The system under test.** This is the second half of the title, "skálázható Q&A rendszer".
- **The yardstick.** Questions with executable reference answers, stratified by cross-sheet difficulty.
- **The harness.** It measures accuracy, tokens, cost, latency and the context wall per strategy × size × k.

Without it, the claim can be argued but not measured. ADR-0015 makes its ~100- and ~1,000-sheet runs the thesis headline.

## 2. Inputs, outputs, and what this note assumes from `kg-construction.md`

**This note does not specify** the importer, the resolver or the Neo4j loader. They are in `kg-construction.md`~~, which is being written in parallel~~. *(revised 2026-09-26, built code: they are now built — `resolution/`, `eval/`, `store/`, and `ingest/`, which is in progress — and §2.1 reconciles every requirement below with that code.)* The Q&A side assumes two things:

- a **loaded Neo4j store per corpus**;
- the **in-memory ground-truth plant graph** (`nx.DiGraph`, the unsplit generator output), together with its `SplitManifest` and `list[SheetGraph]`.

**Requirements on the KG-construction side.** Each is to be confirmed against that note (open question OQ1). *(revised 2026-09-26: confirmed or corrected in §2.1.)*

| # | Requirement | Why the Q&A side needs it |
|---|---|---|
| R1 | Every item occurrence in the store carries `tag`, `node_class` (as labels), `unit_id` and its sheet (an `is_drawn_on` edge or a `sheet_id` property) | Hierarchical routing; ContextRAG serialization |
| R2 | Cross-sheet links are materialized as `continues_as` / `same_tagged_item_as` edges from exactly one source per run (`asserted_by`, `plant-generator.md` §4.3) | sheet adjacency; CypherRAG traversal |
| R3 | Only **visible** properties are in the store (`schema.VISIBLE_NODE_PROPERTIES`, `VISIBLE_EDGE_PROPERTIES`); `node_id` and `stream_kind` never are (§4.4) | the answer key must not leak into retrieval |
| R4 | One corpus per database at a time, with a marker node (`DrawingSet`) carrying the `corpus_id` | CypherRAG queries need no corpus filter; the harness refuses to run if the marker does not match |
| ~~R5~~ | ~~The EX01 import keeps the **data attributes** that ChatP&ID's graph-query questions ask about: equipment design data, and valve nominal diameter, piping class and fluid code (App. Table 1, pp. 28–32)~~ **Void** *(revised 2026-09-26, ADR-0021)* | ~~10 of the 19 EXP-0001 questions, see §10~~ |
| R6 | The pipeline's stage timings (generate, split, resolve, load) are written per corpus to a JSON file the harness can read | the headline table reports end-to-end cost (§13.2) |

### 2.1 Reconciliation with the built store and resolver *(revised 2026-09-26, built code and `kg-construction.md` §7)*

R1–R6 were written before this note's author had seen `kg-construction.md`, assuming a sheet-level store. The code as built (read 2026-09-26) is the reference below.

**What exists.**

- `resolution.resolve(localized_sheets) -> Resolution`: `plant` (the **merged** `nx.DiGraph`, node ids are local keys `"sheet_id:occ_id"`, paired stubs removed, unpaired stubs kept), `connector_pairs` (outgoing stub key → incoming stub key, `original_edge=None`), `identity_groups` (`home`, `references`), `unresolved`, `report`.
- `store.neo4j_plan.build_load_plan(corpus_id, localized_sheets, resolution) -> LoadPlan` (rows from `store.neo4j_rows`), and `store.neo4j_loader.load_corpus` / `wipe_corpus`. The store holds **the occurrence graph**, not the merged plant: every localized sheet's items and connector stubs, `(:DrawingSet)-[:has_sheet]->(:Sheet {sheet_id})`, `(occurrence)-[:is_drawn_on]->(:Sheet)`, topology relationships named by `relation`, plus the resolver's `continues_as` (FlowOut stub → FlowIn stub; `asserted_by`, `match_rule`) and `same_tagged_item_as` (reference → home; `asserted_by`). Every node also carries the bookkeeping label `CorpusNode` and the properties `uid = "{corpus_id}|{local_key}"` and `corpus_id`.
- `store.neo4j_settings.from_env()` reads `NEO4J_*` from the environment, then fills gaps from the git-ignored repository-root `.env` (`python-dotenv`, `override=False`); the password is a `SecretStr`.
- `eval.graph_equality` (`visible_view`, `to_original_ids`, `graph_differences`) and `eval.resolution_scoring`.
- `ingest.pipeline.run_synthetic` / `run_proteus` return an `IngestResult` (printed as JSON by `python -m plantgraph.ingest`). They **do not return** the plant, the sheets, the manifest or the `Resolution`; the step that builds the plant (`_generate_plant_graph`) is private. §18 T0 closes this gap.

**R1–R6 against the built code.**

| # | Verdict | What the built code does | Consequence for the Q&A side |
|---|---|---|---|
| R1 | **holds, with one shape change** | `tag`, `unit_id` and the other V properties are node properties; `node_class` becomes the `labels_for` label chain (and, for EX01's `GenericItem`s, the `dexpi_labels` chain first). **An occurrence has no `sheet_id` property in Neo4j**: its sheet is reached through `is_drawn_on` → `(:Sheet {sheet_id})`. In memory, the sheet is the prefix of the local key. Stubs carry no `unit_id`; EX01 carries no `unit_id` at all (`kg-construction.md` §3) | CypherRAG's schema paragraph says "the sheet of an item is the `Sheet` it `is_drawn_on`". `sheets_of_unit(U)` = the sheets of the occurrences whose `unit_id = U` (there are no `PlantSection` nodes; `is_located_in` is deferred). On EX01 Hierarchical routes by tag only |
| R2 | **holds** | `continues_as` and `same_tagged_item_as` come only from `Resolution`, with `asserted_by="resolver"`. The oracle path (`asserted_by="oracle"`) exists as a parameter but **no oracle `Resolution` is built** (`kg-construction.md` §10, "Deferred") | sheet adjacency = the sheets at the two ends of each `continues_as` (in memory: the sheet prefixes of `pair.from_key` and `pair.to_key`). At the headline `duplication_rate=0.0` there are no identity groups, so no `same_tagged_item_as` |
| R3 | **holds** | `localize` keeps V properties only; rows add only `uid` and `corpus_id`; `tests/test_neo4j_plan.py` checks that no row carries `stream_kind` or a non-V key. Gold `node_id`s never reach the store (occurrence ids are `sha1` hashes) | the serializer and the CypherRAG schema text omit `CorpusNode`, `uid` and `corpus_id` (bookkeeping, not gold, but noise for the model) |
| R4 | **half holds** | the marker exists: `(:CorpusNode:DrawingSet {corpus_id, drawing_set_id})`. **"One corpus per database" is not enforced**: `wipe_corpus` / the load's wipe delete only their own `corpus_id`, so other corpora stay | the harness enforces it before any CypherRAG call: `MATCH (d:DrawingSet) RETURN d.corpus_id` must return **exactly one** row, equal to the run's corpus, else it refuses and names `wipe_corpus` (§11). `NEO4J_DATABASE` lets the user put each corpus in its own database if the edition allows (OQ7) |
| R5 | **void** — ADR-0021 (accepted 2026-09-26) | no equipment or datasheet data anywhere. Only identifiers are kept: `tag`, and on imported valves `piping_component_name` (e.g. "66KL21"); the safety-valve tag falls back to `positionNumber` ("SV 104.01") | EXP-0001 splits ChatP&ID's questions into `scored` and `out_of_scope_datasheet` (§10) |
| R6 | **half holds** | `IngestResult.stage_seconds` has `generate` (the whole pyDEXPI round trip), `split`, `localize`, `resolve`, `check` (with `--check`), `plan`, and `load_wipe` … `load_total` (with Neo4j). It is **printed to stdout, never written to a file** | §18 T0 adds an `--out PATH` flag so the JSON is written as UTF-8 to `data/corpora/<corpus_id>/ingest.json` (a PowerShell `>` redirect may write UTF-16, so redirection is not the documented route). `CorpusRecord.stage_seconds` is read from there |

**Which graph each consumer reads.** *(decision D8/D9, §19)*

| Consumer | Graph | Built from |
|---|---|---|
| ContextRAG, Hierarchical, VectorRAG, PathRAG | the **in-memory occurrence graph** (`NetworkxGraphView`) — the same nodes, relationships and visible properties as the Neo4j store | `localized_sheets` + `Resolution.connector_pairs` + `Resolution.identity_groups` (T0, T3) |
| CypherRAG | the **Neo4j occurrence graph** (`Neo4jGraphView.run_cypher`) | `build_load_plan` + `load_corpus` of the same corpus |
| Question generator, reference functions, `k`, `evidence_sheets` | the **unsplit ground-truth plant** (`nx.DiGraph`, gold `node_id`s) + the `SplitManifest` + the raw splitter `list[SheetGraph]` | the generator and splitter, rebuilt deterministically by T0. **Never the store, never `Resolution.plant`** (ADR-0013 points 1–2) |
| The G1 gate only | `Resolution.plant` (merged) | `eval.graph_equality`, as `ingest --check` already does |
| Hierarchical routing recall (harness) | gold `evidence_sheets` vs routed `S` | sheet ids are identical before and after `localize` (`localize.py` keeps `sheet_id`), so they compare directly |

T3's acceptance proves the two occurrence-graph views are the same graph: the in-memory view's node-label and relationship-type counts equal `LoadPlan.expected_node_labels` / `expected_relationship_types`, which `load_corpus`'s verify step already checks against Neo4j.

**How `k` is computed, and on which graph.** On the ground truth only: `cut` is the set of `original_edge`s in `manifest.connector_pairs` (gold ids of the unsplit plant), and `k = |evidence_edges ∩ cut|` (§9). In the occurrence graph, one cut edge `(u, v)` appears as `u → FlowOut stub -continues_as-> FlowIn stub → v`. So **when G1 holds** (the resolver reproduced every pair), `k` equals the number of `continues_as` relationships that the evidence crosses in the store. That equality is a cross-check in T12, never the definition.

**Outputs of this component:**

- question sets (`data/questions/<corpus_id>.jsonl`);
- run folders (`data/runs/<run_id>/`: config, answers, calls, summary);
- markdown rows for `30-experiments/_results.md`;
- the release bundle (§14.4).

## 3. Package layout

The existing 400-line file cap applies (see the `graph/schema.py` docstring). Every module here stays well under it.

```
src/plantgraph/llm/
    models.py        # ModelPin, ChatMessage, ChatRequest, ChatResponse, CallRecord, ContextWall; exceptions
    cache.py         # SqliteCache: key function, get/put, replay mode
    client.py        # ChatClient: OpenAI-compatible HTTP (OpenRouter or local), retries, run log
    embed.py         # Embedder: OpenAI-compatible /embeddings, cached through the same cache
    openrouter_settings.py  # (revised 2026-09-26, settings) OpenRouterSettings.from_env(): OPENROUTER_API_KEY, env then .env
    local_settings.py       # (revised 2026-09-26, settings) LocalLLMSettings.from_env(): LOCAL_LLM_BASE_URL, optional
    fake_transport.py       # (revised 2026-09-26, no local runtime) scripted transport for tests and dry runs; no network
src/plantgraph/qa/
    corpus.py        # (revised 2026-09-26, built code) CorpusArtifacts: gold plant + manifest + raw sheets, localized sheets, Resolution (T0)
    models.py        # Question, QuestionFamily, AnswerType, FinalAnswer, Outcome, QuestionResult, RunConfig, CorpusRecord
    graph_view.py    # GraphView protocol, ItemRecord, EdgeRecord, NetworkxGraphView
    neo4j_view.py    # Neo4jGraphView (read-only session), schema text for CypherRAG
    serialize.py     # visible-only GraphML serializer (ContextRAG and Hierarchical share it)
    final_answer.py  # shared final step: prompt render, JSON extraction, parse-failure outcome
    fit.py           # context-wall pre-check, applied to every strategy's final prompt
    strategies/      # context_rag.py, cypher_rag.py, hierarchical.py, vector_rag.py, path_rag.py, agentic.py
    questions/       # families.py (templates + reference functions), evidence.py (k, sheets), sample.py, cli.py
    scoring.py       # normalization, exact / set / path / abstention scoring
    judge.py         # EXP-0001 rubric judge; judge-agreement check
    harness.py       # questions × strategies × repeats → answers.jsonl; resume; replay
    report.py        # aggregation, bootstrap CIs, _results.md rows, CSV
    pilot.py         # wall probe, cost / latency / variance runs
    prompts/         # *.txt templates, one per step; the sha256 of each file is recorded in RunConfig
```

**New dependencies:**

- `openai`, the OpenAI-compatible SDK. OpenRouter documents its API as OpenAI-compatible, with the base URL `https://openrouter.ai/api/v1`.
- ~~`neo4j`, the driver. It may already be added by kg-construction.~~ *(revised 2026-09-26, built code)* `neo4j` (`>=6.3.1`) and `python-dotenv` (`>=1.2.3`) are already in `pyproject.toml` (working tree, from kg-construction T7). Only `openai` is new here.
- `numpy`, for cosine top-k, and only from the VectorRAG task onward.

## 4. Data model (Pydantic)

`llm/models.py`:

- **`ModelPin`**
  - `backend: Literal["openrouter", "local"]`, `model_id: str`
  - `route_provider: str | None`, the OpenRouter provider slug. It is sent as `provider={"order": [slug], "allow_fallbacks": False}` so that one model id cannot silently be served by different hosts. OpenRouter's provider-routing docs say fallbacks must be disabled to restrict routing to `order`.
  - `temperature: float | None`, `seed: int | None`, `max_output_tokens: int`, `extra: dict[str, Any]` (for example a reasoning-effort setting)
  - `pin_hash() -> str`
- **`ChatRequest`**: `pin`, `messages: list[ChatMessage]`, `json_mode: bool`, `purpose: str` (`answer` | `cypher` | `route` | `judge` | `probe` | `pathrag_step` | `embed`). **`purpose` is logged but is not part of the cache key.**
- **`ChatResponse`**
  - `text`, `prompt_tokens`, `completion_tokens`
  - `cost_usd: float | None`, as **reported by the provider**. OpenRouter returns a `usage` block with a cost field. It is never computed from a remembered price.
  - `latency_s`, `provider_response_id`, `finish_reason`, `from_cache: bool`, `created_at`
- **`CallRecord`**: one line of `calls.jsonl`. It holds `run_id`, `question_id`, `strategy`, `purpose`, `cache_key`, `pin_hash`, `prompt_sha256`, the response fields, and `error_kind: None | "context_overflow" | "provider_error"`.
- **`ContextWall`**: `pin_hash`, `max_ok_chars`, `min_rejected_chars | None`, `measured_at`, `probe_corpus_ids`.
- **Exceptions:** `ContextOverflow`, `ProviderError`, `CacheMiss`.

`qa/models.py`:

- **`QuestionFamily(str, Enum)`**: see the §9 table.
- **`AnswerType(str, Enum)`**: `CLASS_NAME`, `UNIT_ID`, `TAG`, `TAG_SET`, `UNIT_SET`, `TAG_PATH`, `COUNT`, `FREE_TEXT` (EXP-0001 only).
- **`Question`**
  - identity: `question_id`, `corpus_id`, `family`, `template_id`, `template_version`, `text`, `answer_type`
  - answer: `answerable: bool`, `reference: str | int | list[str] | None`
  - evidence: `evidence_tags: list[str]`, `evidence_sheets: list[str]`, `k: int | None`, `anchors: list[str]`, `generator_seed: int`
  - `evidence_*` and `k` are **gold**. The harness reads them; strategies never do.
- **`FinalAnswer`**: `answer: str | int | list[str] | None`, `not_present: bool`.
- **`Outcome(str, Enum)`**: `ANSWERED`, `DID_NOT_FIT`, `PARSE_FAILURE`, `RETRIEVAL_ERROR`, `PROVIDER_ERROR`.
- **`RetrievalResult`**: `context: str | None`, `failure: Outcome | None`, `trace: dict[str, Any]`. The trace holds routed sheets, Cypher text, row count, truncation and anchors.
- **`QuestionResult`**: `run_id`, `question_id`, `strategy`, `repeat`, `outcome`, `final_answer | None`, `correct: bool`, `f1: float | None`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_s`, `context_chars`, `trace`.
- **`CorpusRecord`**: `corpus_id`, `role: Literal["dev", "test"]`, the generator and split configs, `n_units`, `n_sheets`, `n_nodes`, `n_edges`, `n_connector_pairs`, `source_graph_hash`, `stage_seconds` (R6).
  - *(revised 2026-09-26, built code)* The sizes and `stage_seconds` are copied from the corpus's `IngestResult` (`data/corpora/<corpus_id>/ingest.json`, §2.1 R6), not re-measured: `counts.n_sheets`, `counts.n_nodes` (store rows), `counts.n_connector_pairs_predicted`, and `stage_seconds` verbatim. `n_nodes` and `n_edges` of the **ground-truth plant** come from `CorpusArtifacts.plant`, and both kinds are reported, labelled.
- **`RunConfig`**: `run_id`, `experiment`, `reported: bool`, `corpora`, `strategies` with their params, `answer_pin`, `judge_pins`, `prompt_hashes`, `question_set_sha256`, `context_wall`, `git_commit`, `git_dirty`, `created_at`. It is written **before the first call**, which implements the ADR-0014 freeze.
  - *(revised 2026-09-26, paid-call approval)* plus `allow_paid_calls: bool = False` (§6). It is set only by an explicit CLI flag the user types; it is never read from the environment or `.env`.

## 5. Graph view and serialization

**`GraphView`** is a Protocol and the only way strategies see the store. It exposes:

- `corpus_id()`, `items()`, `edges()`, `sheets()`
- `find_by_tag(tag)`: normalized, connector tags excluded *(revised 2026-09-26, ADR-0021: also matches `piping_component_name`, the printed valve name such as "66KL21", which ChatP&ID's flow-path questions use; it is an identifier, not data)*
- `unit_ids()`, `sheets_of_unit(unit_id)` *(revised 2026-09-26, built code: from the `unit_id` property of occurrences; the store has no `PlantSection` nodes)*
- `sheet_neighbours(sheet_id)`: via `continues_as`, both directions
- `subgraph(sheet_ids) -> nx.DiGraph`: visible properties only
- `run_cypher(query, timeout_s, row_cap)`: Neo4j only; `NetworkxGraphView` raises `NotImplementedError`

Two implementations:

- ~~**`Neo4jGraphView`** is primary. It uses a read-access session.~~ *(revised 2026-09-26, built code; D9)* **`Neo4jGraphView`** serves **CypherRAG only**: `corpus_id()`, the one-corpus marker check (§2.1 R4), `schema_text()` and `run_cypher()`, in a read-access session. Its other protocol methods raise `NotImplementedError` until a strategy needs them.
- **`NetworkxGraphView`** runs over the ~~resolved sheet-level graph~~ *(revised 2026-09-26, built code)* **in-memory occurrence graph**, built from `localized_sheets` and the `Resolution`'s pairs and identity groups (§2.1): one node per occurrence keyed by its local key `"sheet_id:occ_id"`, with `sheet_id` as an attribute, topology edges, and `continues_as` / `same_tagged_item_as` edges. It holds the same content as the Neo4j store (checked in T3). ~~It is used by unit tests, and it is the **fallback** if Neo4j cannot load ~1,000 sheets inside kg-construction's kill threshold (`thesis-phase-plan.md` P2, "Fails if"). ContextRAG, Hierarchical, VectorRAG and PathRAG then run on it, and only CypherRAG needs Neo4j.~~ *(revised 2026-09-26, D9)* ContextRAG, Hierarchical, VectorRAG and PathRAG **always** run on it, and only CypherRAG needs Neo4j. If K-NEO fires, only CypherRAG loses scale points (`kg-construction.md` §7.6, fallback 1); the other strategies are unaffected.

**Serializer** (`serialize.py`). It uses `networkx.generate_graphml` on a copy that holds only:

- visible properties (R3) *(revised 2026-09-26, built code: never `uid`, `corpus_id` or the `CorpusNode` label; imported `GenericItem`s keep `dexpi_class`, `category` and `dexpi_labels`, which are visible)*;
- the opaque occurrence id;
- `sheet_id` as a node attribute. Structure nodes are folded into attributes, which keeps the prompt smaller than serializing `Sheet` nodes and `is_drawn_on` edges;
- cross-sheet edges.

This is ChatP&ID's "graph mode": labels, tags and properties, with internal identifiers and embeddings stripped (`2603.22528`, §3.3.1). The agent-chosen topology mode is not used; one mode is fixed. **The 2026-09-25 size measurement (≈400 characters per node) serialized the unsplit plant graph.** Sheet-level serialization adds connector nodes, so the pilot re-measures size with this serializer.

## 6. LLM client, cache, run log, embeddings

**Client** (`client.py`):

- **One class for both backends,** because OpenRouter and the usual local servers both speak the OpenAI chat API.
  - ~~The base URL and key come from environment variables: `OPENROUTER_API_KEY` (already in the user's setup, `00-index.md` Next action), plus `LOCAL_LLM_BASE_URL` for development.~~
  - ~~No key is ever written to a file or a log.~~
  - *(revised 2026-09-26, settings: reuse the `store/neo4j_settings.py` pattern, one settings module per backend)*
    - `llm/openrouter_settings.py`: `OpenRouterSettings(api_key: SecretStr, base_url: str = "https://openrouter.ai/api/v1")`, frozen, plus `missing_required_vars() -> list[str]` and `from_env() -> OpenRouterSettings | None`. The rule is the same as `Neo4jSettings`: real environment variables win, then `load_dotenv(<repo root>/.env, override=False)` fills what is missing; `None` if `OPENROUTER_API_KEY` is still unset. The `.env` file is git-ignored (`.gitignore`: "local secrets (Neo4j and OpenRouter credentials)").
    - `llm/local_settings.py`: `LocalLLMSettings(base_url: str)`, `from_env()` reading `LOCAL_LLM_BASE_URL` by the same rule; `None` if unset. It is optional: nothing in §18 depends on it.
    - The pattern is copied (about 10 lines), not factored out of `store/neo4j_settings.py`, so no built module changes.
  - **The key never leaves the settings object** except as the SDK's `api_key` argument, read once with `get_secret_value()` inside `client.py`. It never appears in:
    - any `repr`/`str` (`SecretStr`; `ChatClient.__repr__` names the backend and base URL only);
    - `calls.jsonl` (`CallRecord` has no header, auth or settings field);
    - the cache (the key function reads only the pin, `json_mode` and `messages`; the stored value is the `ChatResponse`);
    - exception text and logs: every provider exception is re-raised as `ProviderError` / `ContextOverflow` with its message passed through `_redact(text, secret)`, which replaces the key's value with `***` before the message is stored anywhere.
- **Paid calls need the user's approval.** *(revised 2026-09-26, paid-call approval)* The client makes a network call only if it was constructed with `allow_network=True`, and every CLI that can spend money (`pilot`, `harness`, `judge`) sets that only from an explicit `--allow-paid-calls` flag, recorded in `RunConfig.allow_paid_calls`. Otherwise the client runs in `replay` mode: a cache miss raises `CacheMiss` and nothing is sent. Because `.env` is loaded automatically, **a key being present is never taken as permission**. The coder never passes the flag; the user runs those commands.
- **Local backend: reality check** *(revised 2026-09-26, checked read-only on this machine)*. **No local OpenAI-compatible LLM runtime is installed.** `ollama` is not on PATH (PATH lists `%LOCALAPPDATA%\Programs\Ollama`, but that folder does not exist); `~/.ollama/models` exists and is empty; no LM Studio folder (`~/.lmstudio`) or `lms` command; nothing answers on `localhost:11434` (Ollama's port) or `localhost:1234` (LM Studio's). The `local` backend stays in `ModelPin` because it costs nothing to keep, but **no acceptance check depends on it**. Development uses `llm/fake_transport.py`: a scripted transport (canned replies keyed by `purpose` and message hash, scripted HTTP 429 / 5xx, and a configurable context wall that rejects prompts over N characters with a fixed overflow message), injected into `ChatClient` in place of the HTTP transport.
- **OpenRouter extras:**
  - `provider` routing pinned as in §4.
  - `require_parameters: true`, so a host that would ignore `temperature` or `seed` is not chosen silently. The provider-routing docs say that by default unsupported parameters are ignored.
  - `json_mode` sends `response_format={"type": "json_object"}`. The docs say `response_format` is only a soft preference, which is why parse failures are counted (§8).
- **Retries** happen only on transport errors (HTTP 429 and 5xx), with backoff. They are logged, with a bounded count set in the config. **Nothing is retried on content**: a bad answer is data.
- **Context overflow.** A provider error that says the context length was exceeded is raised as `ContextOverflow`. The pilot records the exact error text per model, so the matcher is written against observed messages, not guessed ones.

**Cache** (`cache.py`):

- **Storage:** SQLite (stdlib `sqlite3`), one file, `data/llm-cache/cache.sqlite`.
- **Key:** `sha256` of canonical JSON containing `backend`, `model_id`, `route_provider`, all generation params, `json_mode` and the full `messages`, which is ADR-0014's key.
- **Stored value:** the full `ChatResponse`, including provider-reported tokens and cost, so a replayed run reports the original cost.
- **Modes:**
  - `live`: read-through.
  - `replay`: cache only; a miss raises `CacheMiss`. This is how the professor re-scores without API access (ADR-0013, Enables).

**Run log.** Every call, whether cached or not, appends a `CallRecord` to `data/runs/<run_id>/calls.jsonl`.

**Embeddings** (`embed.py`):

- `Embedder` uses the OpenAI-compatible `/embeddings` endpoint. OpenRouter documents one at `/api/v1/embeddings`; local servers commonly offer one too.
- Embeddings are cached under the same key scheme, with `purpose="embed"`.
- **The model is chosen in the pilot** (§12). No provider is assumed.

## 7. Strategies

**The fairness rules** apply to every strategy:

- **Retrieval sees only `question.text`.** It never sees `family`, `answer_type`, `k` or any evidence field.
- **Every strategy ends in the same final step** (§8). The only thing that differs between strategies is the context.
- **Each strategy runs once per question**, with no iterative refinement, as ChatP&ID's "each tool can be called only once per test" (§4.1). Agentic is the stated exception and is a could-item.
- **The final prompt of every strategy goes through the same fit check** (`fit.py`, below).

| Strategy | Retrieval | LLM calls before the final step | Parameters (source) |
|---|---|---|---|
| **ContextRAG** | serialize the whole corpus view (§5) | 0 | none; graph mode fixed (§3.3.1) |
| **CypherRAG** | schema text + question → one Cypher query → read-only execution → rows as JSON lines, plus the query text, as context | 1 | single attempt (§4.1, Algorithm 4); `timeout_s`, `row_cap` set in the pilot on dev corpora |
| **Hierarchical** | plant → unit → sheet → item routing (below), then the routed subgraph is serialized | 0, or 1 if the router fallback is used | `sheet_hops`, `max_context_chars`, `max_sheets`, tuned on **dev corpora only** |
| **VectorRAG** | cosine top-k over node cards, returning the cards | 0 (plus 1 query embedding) | `top_k`. ChatP&ID leaves `topK` optional and states no value (Algorithm 2), so it is set on dev corpora |
| **PathRAG** | ChatP&ID Algorithm 3: global vector search for `maxBreadth` start nodes, then an LLM-guided hop per step, then selecting the best path | several; the pilot measures the mean | **breadth 2, depth 3** (§4.1) |
| **Agentic** (could) | a tool loop over `find_tag`, `neighbours`, `sheet`, `cypher`, with at most `max_steps` steps | ≤ `max_steps` | `max_steps` set on dev corpora |

**Fit check** (`fit.py`). The pilot measures a `ContextWall` for each answering model (§12). Then:

- If `len(final_prompt) >= min_rejected_chars`, the outcome is **`DID_NOT_FIT`** and no call is made.
- If the prompt falls between `max_ok_chars` and `min_rejected_chars`, the call is made, and a `ContextOverflow` becomes `DID_NOT_FIT` with `trace["overflow_on_call"]=True`.
- `DID_NOT_FIT` is an **outcome, not an error**. It is scored wrong in end-to-end accuracy and excluded from conditional accuracy (§11).
- Characters, not tokens, are the unit. Every serialized context uses one format, and the wall is measured in characters with that format, so no tokenizer is assumed.

**CypherRAG schema text** is generated from `graph/schema.py`, and so stays in step with the code:

- labels (`labels_for`), relation types and visible property keys;
- one fixed paragraph describing sheets, off-page connectors and `continues_as`, worded against the store shape that kg-construction fixes (OQ1).
- *(revised 2026-09-26, built code; OQ1 answered)* The label and relationship lists are taken from **this corpus's** `LoadPlan.expected_node_labels` and `expected_relationship_types` keys, minus `CorpusNode`. So EX01's `GenericItem` chains (e.g. `PipeTee`) appear, and classes absent from the corpus do not. Each entry is still checked against `labels_for` / `schema.Relation` or the `^[A-Z][A-Za-z0-9]*$` generic-label rule. The fixed paragraph states the built shape (§2.1): `(:DrawingSet)-[:has_sheet]->(:Sheet {sheet_id})`; every item `-[:is_drawn_on]->` its `Sheet`, and items have no `sheet_id` property; a pipe or signal that leaves a sheet ends in a `FlowOut…OffPageConnector` whose `-[:continues_as]->` leads to the `FlowIn…OffPageConnector` on the other sheet, from which the line continues; `same_tagged_item_as` links a repeated drawing of an item to its main occurrence; `unit_id` is a property (there are no unit nodes). `uid` and `corpus_id` are not mentioned.

Execution:

- runs in a read-access session;
- rejects any query containing a write clause (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`) before it is sent;
- records truncation at `row_cap`.

A Cypher error returns `RETRIEVAL_ERROR` without a final-step call. **The Cypher error rate and the empty-result rate are reported.**

**Hierarchical** is the design contribution. It is ContextRAG applied to a **routed sub-corpus**: it uses the same serializer and the same final step, and only the selection of context differs. So when the whole plant fits, Hierarchical degenerates towards ContextRAG by construction. Steps:

1. **Anchors.**
   - Tags are found by normalized token lookup against `find_by_tag`. The question is tokenized on whitespace and punctuation other than `-` and `.`; adjacent token pairs are also tried, for tags written with a space, as in ChatP&ID's `SV 104.01`.
   - Unit ids are found by matching `unit <id>` against `unit_ids()`.
2. **Router fallback.** Used only when there are no anchors. One LLM call receives a plant map, with one line per unit (unit id plus its equipment tags), and returns unit ids. **The fallback rate is reported.**
3. **Sheet selection** (`S`):
   - the anchor sheets;
   - the sheets of the anchor units;
   - with two or more anchor sheets, the sheets on the shortest path between the first anchor and each other anchor in the undirected **sheet-adjacency graph**. That graph is built from `sheet_neighbours`, which is the resolver's output and not the manifest;
   - the `sheet_hops`-hop neighbours of the anchor sheets.
4. **Budget.** If the serialized `S` exceeds `max_context_chars`, the outermost hop ring is dropped first and `trace["truncated"]=True` is recorded.
5. **Serialize `S`.** Connectors whose partner sheet is outside `S` keep their visible labels, so the model can see that a line continues.

**Node cards** (VectorRAG and PathRAG) are deterministic text built from visible properties, in the form: `"{node_class} {tag}, unit {unit_id}, sheet {sheet_id}; sends to: …; receives from: …; signals: …"`.

- This **replaces ChatP&ID's GPT-4o-written local and global descriptions** (`2603.22528.md`, Method). Generating those would take one LLM call per node or more, at up to 43,043 nodes (SMOKE-02).
- PathRAG's "local" and "global" indexes are the same card embedding in our version. The next hop is the cosine-best unvisited neighbour against the LLM's next-hop query embedding.
- This deviation is decision D1 (§19) and a stated EXP-0001 threat.
- The index is an in-memory numpy matrix (D2).

## 8. Shared final-answer step

- **One template** (`prompts/final_answer.txt`), in this order: system instruction; **context**; question; answer-format instruction.
  - The context comes before the question so that a provider-side prompt-prefix cache can reuse ContextRAG's identical corpus prefix across questions. No saving is assumed; the pilot reports it if the provider's `usage` shows one.
  - The answer-format instruction is one fixed string per `AnswerType`. `CLASS_NAME` lists the allowed class names from `schema.NodeClass`. `TAG_PATH` says "equipment and valve tags only, omit off-page connectors".
- **Output:** JSON `{"answer": ..., "not_present": bool}`.
- **Parsing:**
  1. Strict `json.loads`.
  2. Otherwise, the first balanced `{…}` block, including a fenced code block.
  3. Validate against `FinalAnswer` and against `answer_type` (for example, `COUNT` needs an int or a numeric string).
  4. Anything else is **`PARSE_FAILURE`**. It is scored wrong and reported as its own rate (ADR-0013 point 5). **There is no retry.**
- **EXP-0001** uses the same step with `AnswerType.FREE_TEXT`, where `answer` is a string, so the judge scores text.

## 9. Question generator (EXP-0002; ADR-0013 E2/E3)

**Inputs:**

- the ground-truth plant `nx.DiGraph`, keyed by gold `node_id` with `tag`, `node_class` and `unit_id`;
- the corpus's `SplitManifest` and `list[SheetGraph]`;
- a seed and the per-stratum counts from the pilot.

*(revised 2026-09-26, built code)* All three gold inputs come from `CorpusArtifacts` (T0): `plant` (the unsplit generator output, before `localize`), `manifest`, and the **raw** splitter `sheets` — never the localized sheets, the store, or `Resolution.plant` (§2.1).

**Reference functions** are plain Python over networkx on the ground-truth graph. They never touch the store under test (ADR-0013 points 1–2). Answers are expressed in **tags**, never in node ids.

**Evidence and k** (`evidence.py`):

- Each family defines an **evidence subgraph**: the nodes and edges that its reference function reads.
- `cut = {tuple(p.original_edge) for p in manifest.connector_pairs if p.original_edge}`.
- **`k = |evidence_edges ∩ cut|`.** For path families this is exactly ADR-0013's "number of off-page connectors on the reference answer's path".
- `evidence_sheets` is the set of sheets that show an evidence node, taken from the `SheetGraph`s.
- Unanswerable questions have `k = None` and are reported in their own column, never in the k curve.

| Family | Template (one phrasing each; paraphrases are a could-item) | Answer type | Reference (ground-truth graph) | Evidence | Mirrors |
|---|---|---|---|---|---|
| `LOOKUP_TYPE` | "What type of item is {tag}?" | `CLASS_NAME` | `node_class` | the node; k = 0 | ChatP&ID graph query (topology-only form) |
| `LOOKUP_UNIT` | "Which unit is {tag} located in?" | `UNIT_ID` | `unit_id` | the node; k = 0 | — |
| `NEIGHBOURS_DOWNSTREAM` | "Which equipment items and valves receive flow directly from {tag}?" | `TAG_SET` | `send_to` successors | those edges | ADR-0013: neighbour across a `continues_as` pair (k ≥ 1 when cut) |
| `LOOP_ACTUATED_VALVE` | "Which valve is actuated by control loop {loop_tag}?" | `TAG` | PIF →`send_signal_to` AF →`control` valve | 2 signal edges | signal connectors |
| `LOOP_MEASURED_EQUIPMENT` | "Which equipment item does control loop {loop_tag} measure?" | `TAG` | equipment →`measured_by` PSGF →`send_signal_to` PIF | 2 edges | signal connectors |
| `FLOW_PATH` | "Trace the process flow path from {A} to {B}. List every equipment item and valve in order." | `TAG_PATH` | shortest `send_to` path, ties broken by the lexicographic tag sequence | the path edges | ChatP&ID "Trace the flow path from tank T4750 to pump P4712" |
| `UPSTREAM_ISOLATION` | "To isolate {X} from all upstream equipment, which valves must be closed?" | `TAG_SET` | walk `send_to` predecessors from X; on each route, take the first `OPERATED_VALVE_CLASSES` node and pass through check valves. **Precondition:** every route has one | the walked edges | ChatP&ID "isolate tank T4750 from all upstream equipment" (its reference lists the globe valves) |
| `CROSS_UNIT` | "Which other units receive process flow directly from unit {U}?" | `UNIT_SET` | `{unit_id(v) : (u, v) send_to, unit_id(u) = U ≠ unit_id(v)}` | those edges | ADR-0013 cross-sheet family |
| `COUNT_IN_UNIT` | "How many {class plural} are in unit {U}?" | `COUNT` | count by `node_class` and `unit_id` | the unit-induced `send_to` subgraph | ADR-0013: counts over a `PlantSection` that spans sheets |
| `UNANSWERABLE_TAG` | a `LOOKUP_TYPE`, `NEIGHBOURS_DOWNSTREAM` or `FLOW_PATH` template naming a well-formed tag (`{prefix}-{unit}-{seq}`, generator grammar) that **is not in the plant** | `not_present` | — | none; k = None | ADR-0011 item 3 (EXP-0005 folded in) |
| `NO_PATH` | the `FLOW_PATH` template with A and B both present and **B unreachable from A** | `not_present` | `not nx.has_path` | none; k = None | cross-sheet abstention |
| `SHEETS_OF_TAG` (should) | "On which sheets is {tag} drawn?" | `TAG_SET` of sheet ids | `IdentityGroup` occurrences | — | ADR-0013; needs `duplication_rate > 0`, and the headline corpora use 0.0 |

*(added 2026-09-26, ADR-0018 — accepted as A1)* **No family reads an equipment attribute.** Generated plants
carry none (`plant-generator.md` §4.8 stays struck). ADR-0018's A2 families (`LOOKUP_ATTRIBUTE`,
`ATTRIBUTE_VIA_PATH`) and its numeric-with-unit scoring are **not adopted**, and no task in §18 builds
them. Every family above reads only `tag`, `node_class`, `unit_id` and topology. ~~Attribute questions exist
only in EXP-0001 on EX01 (§10, `needs_data_attributes`). Whether EX01's attributes reach the store at all
is R5 / OQ2, and it is still open (`kg-construction.md` open question 1d).~~ *(revised 2026-09-26, ADR-0021)*
There are **no attribute questions anywhere** in this thesis. ADR-0021 removes equipment data from imported
files too (T1c/T1d cancelled), so R5 is void and OQ2 is closed. ChatP&ID's datasheet questions are listed in
EXP-0001 as **out of scope — not part of this thesis** and are not asked (§10).

**Sampling** (`sample.py`):

- **Enumerate candidates** per family, with a bound. `FLOW_PATH` samples source nodes and runs a bounded forward BFS with `max_path_edges`, rather than enumerating all pairs.
- **Bin by k** into `{0, 1, 2, ≥3}`, plus an unanswerable bin.
- **Draw** the per-bin count from the pilot (§12), round-robin over the families available in that bin, seeded.
- **Write an availability report** (`candidates per family × k-bin`) beside the JSONL. A bin with fewer candidates than its target takes all of them and is flagged **underpowered**.
- The same seed, corpus and counts give **byte-identical JSONL**.

**Scoring** (`scoring.py`):

- **Normalization:** uppercase, strip, collapse internal whitespace; for `UNIT_ID`, also strip a leading `UNIT`/`U`.
- **Scalars:** `CLASS_NAME`, `UNIT_ID` and `TAG` use exact match. `COUNT` uses integer equality, with numeric strings accepted.
- **Sets:** precision, recall and F1. **`correct` means an exact set.**
- **`TAG_PATH`:**
  - First remove the corpus's connector tags (known from the manifest). Any other tag that is not in the ground truth makes the path invalid.
  - `correct` means the path starts at A, ends at B, and every consecutive pair is a ground-truth `send_to` edge. Any valid path is accepted.
  - `f1` is the set F1 against the reference path.
- **Unanswerable:** correct if and only if `not_present` is true. An answerable question answered with `not_present` is wrong, and counts towards the **false-abstention rate**.

## 10. EXP-0001 harness: the ChatP&ID reproduction

**Transcription** (a coder task; the user checks it). The file is `data/external/chatpid_ex01_qa.jsonl`, next to the EX01 file, untracked until the user decides (OQ5). There is one row per App. Table 1 entry, in table order. Fields (`ChatPidQA` model):

*(revised 2026-09-26, git ignore rule)* `data/external/` is **git-ignored** (commit `d9c2c60`), so the file stays local on the user's machine; publishing it would need a separate decision (OQ5), not a `git add`. The thesis never cites our file. It cites the source, **arXiv:2603.22528v1, App. Table 1, pp. 28–36** (and the journal version, OQ5), and states the file's `sha256`, which is also recorded in `RunConfig.question_set_sha256` and in the EXP-0001 run note. Anyone holding the paper can re-transcribe the table and check the hash; the `scope` tag of each row (below) is listed in a thesis appendix table by `qid`, so the scored group is auditable without the file.

| Field | Content |
|---|---|
| `qid` | `CP01` … `CP19` |
| `task_type` | verbatim: `Graph Query (Single)`, `Graph Query (Multi)`, `Path Exploration`, `Knowledge Inference`, `Graph Summarization` |
| `question` | verbatim from **App. Table 1**. Not from §4.2, whose samples are reworded (§4.2 "design volumetric flow rate of pump P4712" vs the table's "design volume flow rate") |
| `reference_answer` | verbatim; line breaks as `\n`; units as printed |
| `source` | `"arXiv:2603.22528v1, App. Table 1"` |
| `source_page` | int, 28–36 |
| ~~`needs_data_attributes`~~ | ~~`true` for the 8 single and 2 multi graph-query rows~~ |
| `scope` *(revised 2026-09-26, ADR-0021)* | `Literal["scored", "out_of_scope_datasheet"]`. **`out_of_scope_datasheet`** if the question or its reference answer needs any equipment or datasheet value (design data, dimensions, power, nominal diameter, piping class, set pressure, material, …). **`scored`** if it can be answered from identifiers (tags, printed names such as "66KL21", position numbers such as "SV 104.01") and topology alone. A row that mixes both is `out_of_scope_datasheet`: it cannot be answered in full. *(revised 2026-10-01, user decision, QA-T15 built)* **Exception:** when the scored answer is a tag set or tag path and the data values only decorate it (CP12 isolation valves, CP13 flow path, which mention DN sizes), the row is `scored` on its tags alone. Result: **5 scored** (CP11–CP15), 14 out of scope. The paper gives **no per-question scores** (App. Tables 2–4 are per task type), and the table runs to **p. 37**, not 36. EXP-0001 is therefore a sanity check on one real sheet, not a per-question reproduction of 0.91. The split is decided **row by row** from the question and its reference answer, not by `task_type`. The earlier "8 single + 2 multi" reading is struck because it went by task type, and at least one Knowledge Inference reference cites chamber pressures (`kg-construction.md`, T1d row) |
| `scope_reason` *(revised 2026-09-26, ADR-0021)* | one line: which datasheet value the row needs, or `"identifiers and topology only"` |
| `transcribed_by`, `checked_by_human` | the coder, and a bool the **user** sets after comparing the file with the PDF *(revised 2026-09-26: the user checks the `scope` tags in the same pass)* |

**Runs:**

- ChatP&ID's configuration is **2 runs per config** (§4.1).
- *(revised 2026-09-26, ADR-0021)* **Only `scored` rows are asked.** `out_of_scope_datasheet` rows are not sent to any strategy or judge. They are listed in the report with their `qid`, task type and `scope_reason`, under the heading "out of scope — not part of this thesis".
- Strategies: ContextRAG and CypherRAG (must); VectorRAG and PathRAG (should); Hierarchical (should). On one sheet, Hierarchical shows what the hierarchy costs at small scale.
- *(revised 2026-09-26, built code)* The corpus is `python -m plantgraph.ingest proteus data/external/C01V04-VER.EX01.xml` (single sheet, `sheet_id = "123/A93"`, no `unit_id`), loaded like any other corpus.
- The graph is the EX01 import. **Threat:** it has 214 complete and 36 conceptual nodes, where ChatP&ID reports 212 → 53, and the gap is unexplained (`00-index.md`, Next action 5).

**Judge** (`judge.py`):

- **Rubric:** ChatP&ID Table 1 (§4.3; adapted from Schulze Balhorn et al. 2024), with four criteria (relatedness, completeness, correctness, coherence) scored 1–5.
- **Input:** the question, the reference answer and the response. The judge must give a **step-by-step justification** before its scores, as ChatP&ID requires.
- **Output:** JSON.
- **Rescaling:** `(s − 1) / 4`, then the mean of the four criteria per answer, then the mean over questions and runs.
- ChatP&ID's judge prompt text was not found in the paper read, so ours is written from the rubric and **its hash is reported**.
- **Primary judge:** GPT-5-mini through OpenRouter, if its listing offers it at pilot time (ADR-0013 point 8).
- **Sensitivity judge:** one model from another family.
- ~~**Reporting:** overall, per task type, and on the **topology-only subset** (the 9 rows with `needs_data_attributes = false`). If R5 fails, only that subset is comparable, and the thesis says so.~~
- **Reporting** *(revised 2026-09-26, ADR-0021)*: on the **scored group** only, overall and per task type, with the group's size stated. The comparison with ChatP&ID's **0.91** (ContextRAG) and 0.86 (CypherRAG) is made **on the scored group only**, and the thesis states the mismatch plainly: ChatP&ID's figures are means over all 19 questions, ours over the scored group. If App. Table 1 or the paper gives per-question scores, the comparison also uses ChatP&ID's own mean over the scored `qid`s; whether it does is **unverified** and is checked in T15. The group sizes are counted from the checked file and are not written here before that.

**Judge agreement** (ADR-0013 point 7):

- Take a seeded sample of EXP-0002 answers from the ~10-sheet dev corpus. The sample size is set in the pilot and is limited by cost.
- The judge scores each answer against the programmatic reference, rendered as text.
- Report the distribution of the judge's correctness score per programmatic label, and a confusion table at the cut "correctness ≥ 4". The cut is chosen here and stated as a choice.

**Not reproduced:** ChatP&ID's semantic-similarity metric. It depends on their embedding model (Voyage-3.5-lite), which our pilot may not choose. This is a could-item.

## 11. Harness, metrics, outputs

**Harness** (`harness.py`):

- It loads `RunConfig` and **refuses to start a `reported` run** unless:
  - the pin, the prompt hashes, the question-set hash and the wall are all present;
  - the corpus marker matches (R4).
  - *(revised 2026-09-26, built code)* For any run that includes CypherRAG: the database holds **exactly one** `DrawingSet`, its `corpus_id` equals the run's corpus, and the store's node-label and relationship-type counts for that `corpus_id` equal the in-memory `LoadPlan.expected_*` of the rebuilt `CorpusArtifacts` (so the store and the in-memory view are the same corpus). Otherwise it refuses and names `store.neo4j_loader.wipe_corpus` and the ingest command.
  - *(revised 2026-09-26, paid-call approval)* Without `--allow-paid-calls` the harness runs in `replay` mode and stops at the first `CacheMiss`. With it, it prints the planned call count and the pilot's cost-per-question estimate before the first call.
- It iterates corpus → strategy → question → repeat, sequentially.
- It appends `QuestionResult` to `answers.jsonl`.
- **Resume:** it skips `(question_id, strategy, repeat)` rows that already exist.
- **Replay:** the same code runs with the cache in `replay` mode.
- A provider error that persists after the transport retries is recorded as `PROVIDER_ERROR`, re-queued once at the end of the run, and then excluded from accuracy and **listed with a count**.

**Metrics** (`report.py`), per strategy × corpus × k-bin, per family as a secondary view, and per unanswerable bin:

| Metric | Definition |
|---|---|
| **End-to-end accuracy** (primary) | correct / all questions; `DID_NOT_FIT`, `PARSE_FAILURE` and `RETRIEVAL_ERROR` count as wrong |
| Conditional accuracy | correct / questions whose outcome is not `DID_NOT_FIT` |
| Did-not-fit rate · parse-failure rate · retrieval-error rate | per strategy and corpus |
| Set / path F1 | means, as the lenient view |
| Correct-abstention rate · false-abstention rate | on the unanswerable and answerable sets |
| Tokens in and out per question | mean and p50, summed over all calls for the question |
| Cost per question | sum of provider-reported `cost_usd`; `None` rows counted and flagged |
| Latency per question | p50 and p90 of the wall-clock sum of the question's calls |
| Component metrics | §17 |
| Pipeline stage times per corpus | from R6 (*revised 2026-09-26*: `IngestResult.stage_seconds`, §2.1), plus embedding time |

**Confidence intervals:**

- 95% percentile bootstrap over questions, with a seeded resample count B. B is a configuration choice, not a measurement.
- **Differences between strategies use the paired bootstrap** over the same questions.

**Files** in `data/runs/<run_id>/`: `run_config.json`, `answers.jsonl`, `calls.jsonl`, `summary.json`, `summary.csv`, and `results_rows.md`. The last holds rows in `_results.md`'s column format, for example:

`| EXP-0002-H1000 | <date> | End-to-end QA at ~1,000 sheets | test corpus s0/u<N>: <sheets> sheets, <nodes> nodes; <model pin>; 3 strategies; <n> questions | end-to-end accuracy [95% CI] per strategy; did-not-fit rate | … | EXP-0002-plant-scale-qa.md |`

The main session writes the detail note `30-experiments/EXP-0002-plant-scale-qa.md`. Its **first table is the headline table** (§13.2).

## 12. Pilot (ADR-0014): before any reported run

The pilot runs on **dev corpora only**: generator seed 1 and split seed 1, at about 10 and about 100 sheets. Its results go to `30-experiments/PILOT-01-llm.md` as a `PILOT-01` row. Like SMOKE, it is a tooling run and uses no EXP number.

*(revised 2026-09-26, built code: `python -m plantgraph.ingest synthetic` takes one `--seed` for both the generator and the splitter, so "seed 1 / seed 1" is `--seed 1`, and the test corpora are `--seed 0`. The CLI's `--budget` defaults to 16, while `SplitConfig`'s own default is 10, so T0 always passes the budget explicitly.)*

*(revised 2026-09-26, paid-call approval)* Steps 2–5 call a real model. They are **run by the user, paid, and need the user's approval** before each run (`--allow-paid-calls`). Step 1 reads OpenRouter's public listing, which is not a model call; it is still run by the user. The coder's acceptance for every step uses the fake transport (§6).

1. **Listing snapshot.** Save OpenRouter's model listing (ids, context lengths and prices *as the listing states them*) with its date, as JSON. This is the source for any window or price mentioned later, never memory.
2. **Wall probe.** For each candidate answerer, binary-search over dev-corpus ContextRAG prompts of increasing size with `max_output_tokens=1`, recording `max_ok_chars`, `min_rejected_chars` and the exact overflow error text. **Probes near the wall are the most expensive calls in the thesis**, so the search is capped at a fixed number of steps.
3. **Cost and latency.** Run the must-strategies on a small fixed pilot question set on both dev corpora, and record tokens, provider-reported cost and latency.
4. **Variance.** Run the same set twice at the chosen fixed temperature, and record the answer-flip rate `f`.
5. **Embedding model** for VectorRAG (if should-items are reached): pick from what OpenRouter's `/embeddings` or a local server offers, by anchor hit@k on the dev corpora (§17).
6. **Fix the counts.**
   - **Per-bin question count:** the largest count the budget allows, with a **floor of 97 per k-bin**. That is the arithmetic of `n ≥ (1.96 × 0.5 / δ)²` for a worst-case 95% half-width `δ = 0.10`. A half-width of 0.05 would need 385.
   - **Repeats:** 1 if `f < δ/2`, otherwise 2 with both reported. ChatP&ID used 2.
   - **Budget estimate:** Σ over sizes, strategies and repeats of `n_questions × mean measured cost per question`, plus judge calls. It is written down with its basis, before the sweep (ADR-0014 step 3).
7. **Freeze.** Model, parameters, prompts, question sets and walls go into a follow-up **ADR-0019 (model pin)**, as ADR-0014 requires.

## 13. The headline evaluation (ADR-0015)

### 13.1 Corpora

Each target size is reached by a deterministic search: **the smallest `n_units` whose split gives `n_sheets ≥ target`**. The realized sheet, node and connector counts are recorded in `CorpusRecord`.

~~The split configuration is the one SMOKE measured, for continuity: `flow_greedy`, `sheet_equipment_budget=4`, …~~ *(revised 2026-09-26, ADR-0017)* The split configuration is ADR-0017's headline split: **`flow_greedy` with the depth-first `_flow_order`** (`kg-construction.md` T4b), **`sheet_equipment_budget=16`**, `duplication_rate=0.0`, `exact_match_tags=True`, `connector_label_detail=FULL`. Budget 16 is matched to EX01's nodes per sheet and OPEN100's connector stubs per sheet (`splitter.md` §3, "Density calibration"). No headline corpus is split before T4b lands, and SMOKE-06 has re-measured the density. SMOKE-01…03 (budget 4) stand for time, memory and round trip only.

*(revised 2026-09-26, ADR-0017: every size below is for budget 16)*

| Point | Role | Target sheets | `n_units` (estimate) | Nodes (estimate) | Tier |
|---|---|---|---|---|---|
| A10 | test, seed 0 | ~10 | ≈ 29 | ≈ 430 | must: the point where ContextRAG is expected to fit |
| H100 | test, seed 0 | ~100 | ≈ 290 | ≈ 4,300 | **must, headline** |
| H1000 | test, seed 0 | ~1,000 | ≈ 2,900 | ≈ 43,043 (SMOKE-02's plant; generation measured feasible at budget 4) | **must, headline** |
| H4000 | test, seed 0 | ~4,000 | ≈ 11,600 | ≈ 170,000 (**unmeasured; needs a new smoke before it is scheduled**) | should, first in line |
| sweep | test, seed 0 | log-spaced points between those above | search | — | should |
| D10, D100 | dev, seed 1 | ~10, ~100 | search | — | pilot and tuning only |

**Basis of the estimates.** *(revised 2026-09-26, ADR-0017)* All four rows are **linear estimates**. H100, H1000 and H4000 are ADR-0017's figures. A10 is the same scaling divided by ten (arithmetic from H100). Nodes per unit come from SMOKE-02 (43,043 / 2,900 ≈ 14.84) and do not depend on the budget. Sheets per unit at budget 16 come from the architect's scratch diagnostic (42.6 nodes per sheet), which is **not yet re-measured on the fixed code**. **They are estimates. SMOKE-06 and the search give the real values.**

The generated sheets hold about **42.6 nodes per sheet** at budget 16 (scratch, ADR-0017), against EX01's **36** and OPEN100's mean of **386**. *(revised 2026-09-26, ADR-0017; the old figure was 10.7 at budget 4.)* The consequences:

- **The thesis never writes "1,000 pages" without the node count.**
- ~~Only H4000 reaches ADR-0001's estimate of ~38,000 nodes for a real 100-page document.~~ *(revised 2026-09-26, ADR-0017)* ~~**H1000 already reaches ADR-0001's estimate** of ~38,000 nodes for a real 100-page document. In node terms, H1000 is therefore about **one** real document at OPEN100 density, not ten.~~ *(corrected by the main session 2026-09-26)* ADR-0001's ~38,000 is **not comparable**: it multiplies PID2Graph's ~382 nodes/page, and PID2Graph counts line crossings and connector points as nodes. Our sheets are calibrated per page against a real DEXPI sheet in our own pipeline (EX01, 36 conceptual nodes; ADR-0017), so **the page count is the comparable unit: H1000 ≈ 1,000 pages ≈ ten ~100-page documents**, as ADR-0015 frames it. Report nodes next to sheets anyway. H4000 stays the first should-item because it extends the curve past H1000. It is unmeasured at every stage, so a new smoke comes before it is scheduled.
- ContextRAG's wall comes about 4× earlier in sheets than at budget 4 (ADR-0017), because each sheet holds about 4× the nodes.

Dev and test corpora never share a seed. **No prompt, parameter or template is tuned on a test corpus.**

### 13.2 The headline table

There is one row per test corpus × strategy:

- corpus: sheets, nodes, connector pairs, and the resolver gate (pass, or oracle fallback);
- questions per k-bin;
- end-to-end accuracy [95% CI], and accuracy at k = 0 and at k ≥ 1;
- did-not-fit, parse-failure and retrieval-error rates;
- tokens, cost and latency per question;
- the pipeline time from ingest to ready (R6).

The table stands on its own in the thesis, ahead of the sweep curves.

### 13.3 Pre-registered success criteria

These are fixed by this note and ADR-0015 **before the first reported run**. After that they are not edited; a change needs a new ADR.

**Validity gates.** A reported number is valid only if all of these hold.

| Gate | Condition | If it fails |
|---|---|---|
| G1 | the resolver gate `resolve(split(plant)) == plant` holds on the corpus (ADR-0010) *(revised 2026-09-26, built code: checked by `python -m plantgraph.ingest synthetic … --check`, `IngestResult.gate_equal`)* | rerun on the oracle graph and **report both** (ADR-0010 decision 3). *(revised 2026-09-26: the oracle `Resolution` is not built — `kg-construction.md` §10 "Deferred" — so a G1 failure first triggers that task; it is not in T0–T17)* |
| G2 | the run was frozen before its first call: `RunConfig` complete, `reported=True` | the run is not reported |
| G3 | no tuning on test corpora (§13.1) | the run is not reported |
| G4 | parse failures are at most half of a strategy's errors in a cell | the cell is flagged **format-bound** and excluded from ranking claims (ADR-0013, Revisit) |

**Claims and their tests.** All intervals are paired-bootstrap 95% CIs over questions.

| # | Claim | Supported if | Reported either way |
|---|---|---|---|
| C1 | **ContextRAG has a wall inside the swept range** | the did-not-fit rate is 100% at H1000, or at H4000 if that runs | the measured wall in characters and nodes for the pinned model |
| C2 | **The ranking inverts before the wall** (strong claim) | at some test point where ContextRAG's did-not-fit rate is 0, another strategy's end-to-end accuracy exceeds ContextRAG's and the CI of the difference excludes 0 | the difference at every point |
| C3 | **Crossing sheets costs accuracy** | for at least one flat strategy, accuracy(k ≥ 2) − accuracy(k = 0) has a CI that excludes 0 on the negative side | the per-k curve for every strategy |
| C4 | **The hierarchy survives past the wall** | at H1000, Hierarchical is at least as accurate as every other strategy: "better" if the CI excludes 0 in its favour, "not worse" if the CI contains 0 | the winner and margin at every point, **including when it is not Hierarchical** (for example CypherRAG) |
| C5 | **The baseline anchor holds** | the EXP-0001 ranking of ContextRAG and CypherRAG matches ChatP&ID (0.91 > 0.86) *(revised 2026-09-26, ADR-0021: our ranking is measured on the `scored` group only; ChatP&ID's is over all 19 questions, and the thesis says so)* | the full ranking and the gap to 0.91, **reported and not tuned** (`thesis-phase-plan.md` P3), *(revised 2026-09-26)* with the size of the scored group and the list of out-of-scope `qid`s |

**What the thesis says for each outcome.**

| Outcome | Wording |
|---|---|
| C1 and C2 | "The single-sheet optimum inverts at plant scale, and does so before the context wall." |
| C1, not C2 | "ContextRAG stays best while it fits, then becomes unavailable. **The wall is the crossover.**" "Inverts" is not used (`thesis-phase-plan.md` P4, Fails if). |
| not C1 (the model's window holds the whole H1000 prompt) | only "stops winning" is testable, via C2. Say so (ADR-0014 open question 5). |
| C4 "not worse" | "the hierarchy matches the best flat strategy at scale", **not** "beats" |
| G1 failed on a corpus | report the resolved and oracle rows side by side; the headline uses the resolved row, labelled |

**Sample size.** The floor is 97 questions per k-bin (§12, step 6). If the budget cannot pay for the floor, **first collapse the bins to `{0, ≥1}`, then drop H4000, and never drop H100 or H1000.**

## 14. Ladder, calendar, slip rule, release

### 14.1 Ladder

- **Must:**
  - EXP-0001: ContextRAG and CypherRAG, 2 runs, primary and cross-family judge, judge agreement;
  - the pilot and ADR-0019 (model pin);
  - A10, H100 and H1000 with ContextRAG, CypherRAG and Hierarchical under one pinned model;
  - the headline table;
  - the release bundle.
- **Should, in reinstatement order:**
  1. H4000 *(revised 2026-09-26, ADR-0017: ≈ 11,600 units ≈ 170,000 nodes, a linear estimate that needs a new smoke first; H1000 is now the node-comparable point)*;
  2. VectorRAG;
  3. PathRAG;
  4. a second model family at H100 and H1000. Each family is its own frozen sweep, and no sweep is reported across a model change (ADR-0014);
  5. the intermediate sweep points;
  6. a third family;
  7. Hierarchical, VectorRAG and PathRAG on EXP-0001;
  8. a DOI for the release.
- **Could:**
  - Agentic;
  - the drawing-reading demo ("if we will have time", ADR-0011 outcome log);
  - `SHEETS_OF_TAG` with `duplication_rate > 0`;
  - paraphrased templates;
  - LLM-written node descriptions for EXP-0001, to match ChatP&ID's method;
  - the semantic-similarity metric.

**Recommendation on the single coder queue.** QA must → the minimal EXP-0004 (OPEN100's 23 pairs, ADR-0010) → QA should-items. EXP-0004 is the second novelty line (`00-index.md`, supporting contribution 2). The QA should-items refine a claim that the must-items already test. The user decides.

> *(revised 2026-09-29)* **Headline corpora use `connector_label_detail=DRAWING_ONLY`** (ADR-0023) in addition to depth-first `flow_greedy` at budget 16 (ADR-0017). A demo application follows the headline (ADR-0024).

### 14.2 Calendar

These are plan dates set against the roadmap in `00-index.md`: P3 in W41, P4 in W42–W43, P5 in W43, write-up to W44. They are **not measured durations**; nobody has measured a coder's pace on tasks like these.

| Checkpoint | Date | Done means |
|---|---|---|
| CP1 | Sun 2026-10-04 | kg-construction chain (its note); T1–T4 here, so the **first measured context wall** exists *(revised 2026-09-26: QA-T0 included; the wall itself is measured only when the user approves and runs the paid probe, §18.2)* |
| CP2 | Sun 2026-10-11 | T5–T13; pilot (T14); ADR-0019 (model pin) frozen |
| CP3 | Sat 2026-10-17 | T15–T16; EXP-0001 run; A10, H100 and H1000 run; rows in `_results.md` |
| CP4 | Sat 2026-10-24 | should-items that fit; EXP-0004 (ADR-0010). **Last experiment date** |

### 14.3 Slip rule

- **CP1 missed:** move PathRAG, VectorRAG and all should-items to future work now.
- **CP2 missed:** drop the cross-family EXP-0001 judge (stated as a limitation) and use the `{0, ≥1}` bins.
- **CP3 missed:** run H100 and H1000 at the floor count with ContextRAG and Hierarchical only, and CypherRAG only if it is ready.
- **Never cut:** H1000, ContextRAG, Hierarchical, or the pre-registered criteria.

### 14.4 Release bundle (the field-level contribution)

A script, `qa/release.py` (task T17), collects the following into `release/<version>/`, with a `SHA256SUMS` file and a data card (README):

- generator and split configs, and seeds;
- per corpus: the `SplitManifest`, the sheet graphs (JSON) and the `CorpusRecord`;
- the question JSONL and availability reports;
- the harness version (git commit);
- the scored `answers.jsonl` and `summary.csv`;
- `calls.jsonl` and the cache, **only if the provider's terms allow it** (ADR-0014 open question 3).
- *(revised 2026-09-26, git ignore rule and settings)* **Never inside:** `.env`; anything under `data/external/` (the EX01 file and the ChatP&ID transcription, unless OQ5 is decided otherwise); the `CorpusArtifacts` gold objects other than the manifest and sheet graphs listed above. The EXP-0001 part of the bundle holds the `qid`s, `scope` tags and scores, not the transcribed question text.

The code is already public under AGPL-3.0. The **data licence** and the DOI are the user's decisions (OQ4). `docs/` is never part of the release (tooling files are local only).

## 15. What the headline can and cannot claim

**Can** claim, subject to `/lit-gap-check` staying clean (the last check on 2026-09-26 found the claim open, **narrowed to P&IDs and process plants**, because AEC-Bench 2603.29199 has cross-sheet tasks on building drawings):

- **The first multi-sheet P&ID question-answering evaluation with executable cross-sheet ground truth.** Scale is measured in **interconnected** sheets, where each answer may cross k off-page connectors. By contrast:
  - ChatP&ID has 1 sheet and 19 questions;
  - PIDQA has 500 unrelated single sheets and 64,000 questions;
  - 2609.05880 has 3,000 questions, "every instance is one sheet" (`_novelty-log.md`).
- **A measured context wall** for a named, pinned model, and per-k accuracy curves for five retrieval strategies.
- **An end-to-end pipeline measured at ~1,000 sheets**, from ingest to answer, with stage times.
- **A public, regenerable benchmark** that anyone can re-score without API access.

**Cannot** claim:

- **Realism.** The plants are synthetic (ADR-0007 P2). There are no utilities and no equipment data (ADR-0018, accepted as A1, revised 2026-09-26; *revised 2026-09-26: and ADR-0021, not on imported files either*), and each corpus is one plant.
- **Attribute lookups at scale** *(added 2026-09-26, ADR-0018)*. ~~Attribute questions exist only in EXP-0001 on EX01, so the sweep and ChatP&ID's 0.91 are measured on different question mixes. This is ADR-0018's stated cost of A1.~~ *(revised 2026-09-26, ADR-0021)* **Anything that needs equipment or datasheet values**, at any scale: such questions are out of scope — not part of this thesis. ChatP&ID's 0.91 is over all 19 of its questions, and our EXP-0001 score is over the scored group only, so the two are measured on different question mixes. This is ADR-0021's stated cost.
- **"1,000 pages" in the everyday sense.** ~~Sheets are about 36 times sparser than OPEN100 (10.7 vs 386 nodes per sheet)~~ *(revised 2026-09-26, ADR-0017)* At budget 16, sheets are close to EX01 (42.6 vs 36 nodes per sheet, scratch figure until SMOKE-06) but about 9 times sparser than OPEN100 (42.6 vs 386). The node count is therefore always given alongside.
- **Resolver quality.** At default labels, resolution is trivial by construction (ADR-0010 decision 2). Its evaluation is EXP-0004.
- **That human questions behave like template questions.**
- **Anything about pixels.** DEXPI input carries no digitization error (ADR-0008).
- **Generality across models**, unless the should-families run.

## 16. Testing

- **Unit tests use no network and no database.**
  - A `FakeChatClient` returns canned responses keyed by `purpose` and message hash.
  - Toy plants come from the existing test-only builder (`tests/graph_plant_builder.py`) and are split by the real splitter.
  - Hand-built plants of 10 nodes or fewer with a known split check every reference function and every k by hand.
- **Property tests:**
  - on a 1-sheet corpus, every question has k = 0;
  - the same seed gives byte-identical question JSONL;
  - a serialized context never contains a gold key (`node_id`, `stream_kind`).
- **Integration tests** are marked `neo4j`, and run only when `NEO4J_URI` is set. On the 4-unit corpus loaded by the kg-construction loader, hand-written Cypher answers a sample of generated questions and must equal the networkx reference. **This is an independent cross-check of the ground truth by a second engine**, and not a source of truth (ADR-0013 point 2). *(revised 2026-09-26, built code: they reuse `tests/test_neo4j_integration.py`'s rule — skipped unless `store.neo4j_settings.missing_required_vars()` is empty, i.e. `NEO4J_URI`, `NEO4J_USERNAME` and `NEO4J_PASSWORD` are set in the environment or `.env` — and they use their own `corpus_id` and wipe it in a `finally`.)*
- ~~**Live tests** are marked `live_llm` and run only with a key. There is one smoke call per backend.~~ *(revised 2026-09-26, paid-call approval)* **Live tests** are marked `live_llm` and run **only when pytest is given `--live-llm`**, never merely because `OPENROUTER_API_KEY` is set: `.env` is loaded automatically, so a key-only rule would spend money on every `pytest` run. The option is registered in `tests/conftest.py`; without it the tests are skipped with a message saying they are paid. There is one OpenRouter smoke call, **run by the user, paid, needs approval**. No local-backend live test exists (§6: no local runtime).
- **Key hygiene test** *(revised 2026-09-26, settings)*: with a fake key `"sk-or-TEST-SECRET"` and a fake transport whose error echoes its request headers, the key string appears in none of: `repr(settings)`, `repr(client)`, the raised exception's `str`, `calls.jsonl`, or the bytes of the SQLite cache file.
- **Replay test:** a run with a fake client, repeated in `replay` mode, reproduces a byte-identical `answers.jsonl`.
- **Answer-key import ban** *(revised 2026-09-26, built code; mirrors `tests/test_resolution_imports.py`)*: an `ast` test asserts that no module in `qa/strategies/`, `qa/graph_view.py`, `qa/serialize.py`, `qa/final_answer.py` or `qa/fit.py` imports `qa.corpus`, `qa.questions`, `benchmark.splitter`, `benchmark.rejoin`, `eval`, or references `SplitManifest` or `OccurrenceMap`.

## 17. How each component reports its own accuracy

| Component | Its own metric, against ground truth |
|---|---|
| Question generator | hand-checked toy cases (§16); the networkx-vs-Cypher agreement rate on the ~~oracle~~ store (§16) *(revised 2026-09-26, built code: the resolver-built store with G1 asserted; no oracle store exists)*; `k` vs `continues_as` hops (QA-T12) |
| Final step | parse-failure rate |
| ContextRAG | did-not-fit rate; the measured wall |
| CypherRAG | Cypher error rate, empty-result rate, truncation rate |
| Hierarchical | **routing recall**: the share of questions with `evidence_sheets ⊆ S`, computed by the harness from gold fields; fallback rate; truncation rate |
| VectorRAG, PathRAG | **anchor hit@k**: the share of questions whose anchor tag is among the retrieved nodes |
| Judge | agreement with the programmatic score (§10) |
| Client and cache | cache hit rate; replay reproduces results byte for byte |

## 18. Ordered coder task list

One coder at a time (Sonnet, ADR-0006). Each task is one hand-off, ends green on `ruff`, `mypy --strict` and `pytest`, and has an acceptance check. The tasks marked **Must** are ~~T1–T17~~ *(revised 2026-09-26, built code)* T0–T17.

*(revised 2026-09-26, built code and paid-call approval)*
- **Task ids here are QA-T0 … QA-T20.** They are not `kg-construction.md`'s T1–T8 (its T8 is the ingest CLI). Hand-offs name them "QA-T3", and so on.
- **Every acceptance check below runs with no network and no paid call:** fake transport (§6), replay cache, and Neo4j only in the opt-in `neo4j` tests. A step that needs a real model is written as **"run by the user, paid, needs approval"**; it is never part of a coder's acceptance, and the coder never passes `--allow-paid-calls`.
- **Order for tonight:** QA-T1 → QA-T2 → QA-T5 → QA-T8 have no dependency on `ingest/`, so they start at once. QA-T0 goes after `kg-construction.md` T8 (the ingest CLI, in progress) is finished and green, because it edits `ingest/pipeline.py` and `ingest/__main__.py`. Then QA-T3, QA-T4, QA-T6 onward in table order.

| # | Task | Acceptance check |
|---|---|---|
| **T0** *(added 2026-09-26, built code)* | Make the built corpus available in memory. (a) In `ingest/pipeline.py`: a public `build_synthetic_corpus(generator_config, split_config) -> SyntheticCorpus` (a dataclass: `plant`, `sheets`, `manifest`, `localized_sheets`, `occurrence_map`, `resolution`, plus the stage timings) and `build_proteus_corpus(path) -> ProteusCorpus`, with `run_synthetic` / `run_proteus` rewritten to call them; `_generate_plant_graph` becomes public. No behaviour change. (b) `--out PATH` on both ingest subcommands: also write the `IngestResult` JSON as UTF-8 to `PATH`. (c) `qa/corpus.py`: `CorpusArtifacts` (the above plus `corpus_id`, the configs and `load_plan_counts`) and `load_corpus_artifacts(corpus_id, ingest_json_path)`, which rebuilds from the configs stored in `ingest.json` | every existing `tests/test_ingest_*.py` test is unchanged and green; building the same 4-unit corpus twice gives identical `LoadPlan.expected_*` and identical node `uid`s; on it, `graph_differences(to_original_ids(resolution.plant, occurrence_map), visible_view(plant)) == []`; `--out` writes a file that parses back into `IngestResult` and equals stdout; `load_corpus_artifacts` refuses when the rebuilt counts differ from `ingest.json`'s `counts` |
| **T1** | `llm/models.py` + `llm/cache.py`: pin, request/response, SQLite cache, key function, `live`/`replay` modes | same request gives the same key; any param or message change gives a different key; put/get round-trips; a replay-mode miss raises `CacheMiss` |
| **T2** | `llm/client.py`: OpenAI-compatible client (OpenRouter + local), provider pin, `require_parameters`, JSON mode, transport-only retries, `ContextOverflow`, `calls.jsonl` log; add `openai` to `pyproject.toml`. *(revised 2026-09-26, settings)* Plus `llm/openrouter_settings.py`, `llm/local_settings.py` (the `Neo4jSettings` env-then-`.env` pattern, §6), `llm/fake_transport.py`, the `allow_network` guard, `_redact`, and the `--live-llm` pytest option in `tests/conftest.py` | fake-transport tests for success, 429-then-success, overflow and a cache hit; ~~one live call per backend run **by the user**, logged~~ *(revised 2026-09-26)* `from_env` returns `None` with the variable absent from both the environment and a temporary `.env`, and reads it from either; the §16 key-hygiene test; with `allow_network=False` a cache miss raises `CacheMiss` and the fake transport records **zero** requests. The one OpenRouter smoke call (`pytest --live-llm`) is **run by the user, paid, needs approval** |
| **T3** | `qa/graph_view.py` (`NetworkxGraphView`) + `qa/serialize.py` | a split 4-unit corpus serializes with **no gold keys**; `sheet_neighbours` is symmetric and matches the resolver's `continues_as` pairs. *(revised 2026-09-26, built code)* The view is built from `localized_sheets` + `Resolution` (§5), at `duplication_rate` 0.0 and 0.5; its node counts per `labels_for` label and edge counts per relation (incl. `continues_as`, `same_tagged_item_as`, and `is_drawn_on` / `has_sheet` counted from the sheet attribute) equal `build_load_plan(...).expected_node_labels` / `expected_relationship_types` minus `CorpusNode`; no serialized text contains `uid`, `corpus_id` or `CorpusNode` |
| **T4** | `qa/pilot.py` part A: listing snapshot + wall probe (binary search, `max_output_tokens=1`) → `ContextWall` JSON | ~~runs end to end against the local backend on D10; the user runs it on OpenRouter, which gives the **first measured wall**~~ *(revised 2026-09-26, no local runtime)* runs end to end on D10 against the fake transport with a scripted wall of N characters: the search returns `max_ok_chars < N ≤ min_rejected_chars`, stops within its step cap, and records the scripted overflow text; the listing snapshot is tested on a saved fixture JSON. The real probe on OpenRouter, which gives the **first measured wall**, is **run by the user, paid, needs approval** |
| **T5** | `qa/models.py` + `qa/scoring.py` | table-driven tests: case and whitespace, empty set, duplicates, `UNIT` prefix, a path containing connector tags, an invalid path, correct and false abstention |
| **T6** | `questions/evidence.py` + families `LOOKUP_*`, `NEIGHBOURS_DOWNSTREAM`, `LOOP_*`, `FLOW_PATH` | on a hand-built split toy plant, each reference answer and each k equals the hand value; on a 1-sheet corpus, every k is 0 |
| **T7** | families `UPSTREAM_ISOLATION`, `CROSS_UNIT`, `COUNT_IN_UNIT`, `UNANSWERABLE_TAG`, `NO_PATH` + `sample.py` + CLI + availability report | the same seed gives byte-identical JSONL; unanswerable tags are absent from the ground truth; `NO_PATH` pairs have no path; the report sums to the candidate counts |
| **T8** | `qa/final_answer.py` + `prompts/final_answer.txt` + `qa/fit.py` | canned outputs (valid, fenced, prose, truncated, wrong type) map to the right `Outcome`; the template hash is stable; the fit check covers both paths (pre-call and on-call overflow) |
| **T9** | `strategies/context_rag.py` + the `Strategy` protocol | with a fake client: a small corpus gives `ANSWERED`; a prompt over `min_rejected_chars` gives `DID_NOT_FIT` with **zero calls made** |
| **T10** | `qa/harness.py` + `RunConfig` + resume + replay | a toy run end to end; a replay gives an identical `answers.jsonl`; an interrupted and resumed run has no duplicate rows; a `reported` run refuses to start without a frozen config. *(revised 2026-09-26, paid-call approval)* Without `--allow-paid-calls` the harness never builds a network client (fake transport records zero requests); `CorpusRecord` is filled from a fixture `ingest.json` |
| **T11** | `qa/report.py`: aggregation, seeded paired bootstrap, `summary.csv`, `results_rows.md` | on a synthetic `answers.jsonl` with known counts, accuracies and rates equal the hand values; fixed seed gives identical CIs |
| **T12** | `qa/neo4j_view.py` + `strategies/cypher_rag.py` | a `neo4j` integration test on the loaded 4-unit ~~oracle~~ corpus *(revised 2026-09-26, built code: the resolver's output at defaults, loaded with `load_corpus`, G1 asserted first — no oracle `Resolution` exists)*: hand-written Cypher matches the networkx reference for sampled questions; a write clause is rejected unsent; a syntax error gives `RETRIEVAL_ERROR`. *(revised 2026-09-26)* Also: for sampled `FLOW_PATH` questions, the number of `continues_as` relationships on the hand-written Cypher path equals the question's `k` (§2.1); the one-corpus marker check refuses a database holding two `DrawingSet`s; the schema text lists no `CorpusNode`, `uid` or `corpus_id`. Unit tests (no Neo4j) cover the write-clause filter and the schema text from a `LoadPlan`; the Cypher-writing LLM is the fake transport |
| **T13** | `strategies/hierarchical.py` | on dev toy corpora, **routing recall is reported**; anchor extraction finds tags written with a space; the context stays within `max_context_chars`; with no anchors, the fallback is used and counted. *(revised 2026-09-26)* Anchors also match `piping_component_name`; on a corpus with no `unit_id` (EX01-shaped) routing works by tag alone |
| **T14** | `qa/pilot.py` part B: cost, latency and variance runs + the counts rule of §12 step 6 → pilot JSON | ~~runs on the local backend; the user runs it on OpenRouter~~ *(revised 2026-09-26, no local runtime)* runs end to end on the fake transport with scripted token counts, costs and answers (including scripted answer flips, so the rule "1 repeat if `f < δ/2`" is exercised both ways); the counts rule reproduces the §12 arithmetic (97 at δ = 0.10). The OpenRouter run is **run by the user, paid, needs approval**; the main session writes `PILOT-01` and ADR-0019 (model pin) |
| **T15** | EXP-0001 data: transcribe the 19 rows from `docs/Academic_papers/2603.22528-ChatPID.pdf` pp. 28–36 into `data/external/chatpid_ex01_qa.jsonl` + `ChatPidQA` loader | 19 rows; task-type counts 8/2/5/3/1; every row has `source_page`; `checked_by_human` stays `false` until the user checks. *(revised 2026-09-26, ADR-0021)* Every row has `scope` ∈ {`scored`, `out_of_scope_datasheet`} and a `scope_reason` (§10 rule); the loader's summary prints the count per group (**reported, not asserted**: the split is not known before the rows are read) and whether the paper gives per-question scores; the file is written under the git-ignored `data/external/` and its `sha256` is printed; the loader test uses a 3-row fixture under `tests/`, not the real file, and skips the real-file check if the file is absent |
| **T16** | `qa/judge.py`: rubric prompt, JSON scores with justification, rescaling, two judge pins, the agreement script | canned judge outputs parse; 1 → 0 and 5 → 1; agreement is computed correctly on a synthetic sample. *(revised 2026-09-26)* `out_of_scope_datasheet` rows are never sent to the judge (fake transport records no request for them) and appear in the report as listed, not scored. Real judge runs are **run by the user, paid, need approval** |
| **T17** | `qa/release.py`: bundle, `SHA256SUMS`, data card | the bundle rebuilds from seeds and configs alone; checksums verify; nothing from `docs/` and no gold key is inside unless it is labelled gold. *(revised 2026-09-26)* No `.env`, nothing from `data/external/`, and no string matching `OPENROUTER_API_KEY`'s value is inside |
| T18 | `llm/embed.py` + `strategies/vector_rag.py` (should) | anchor hit@k is reported on dev corpora; embeddings are served from the cache on the second run |
| T19 | `strategies/path_rag.py` (should) | a fake LLM that always picks the first neighbour gives a deterministic path; breadth 2 and depth 3 are enforced |
| T20 | `strategies/agentic.py` (could) | `max_steps` is enforced; the observations reach the shared final step |

### 18.1 What the built code made wrong or unnecessary in this list *(revised 2026-09-26, built code)*

1. **A missing task (QA-T0).** Nothing public returned the gold plant, the manifest, the sheets or the `Resolution`: `run_synthetic` returns only `IngestResult`, and `_generate_plant_graph` is private. Without T0, QA-T3, QA-T6/T7 and QA-T10 would each re-implement the pipeline, and the in-memory corpus could silently differ from the loaded one.
2. **R6 was not delivered as specified.** Stage timings exist (`IngestResult.stage_seconds`) but only on stdout. T0 adds `--out`.
3. **"Oracle corpus" in QA-T12 does not exist.** The oracle `Resolution` is deferred in `kg-construction.md` §10. QA-T12 uses the resolver's output with G1 asserted.
4. **`Neo4jGraphView` is smaller than planned (D9).** Only CypherRAG reads Neo4j, so the view needs `schema_text`, `run_cypher` and the marker check, not the full `GraphView` protocol.
5. **The one-corpus rule (R4) moves to the harness.** The loader's wipe is per `corpus_id` and does not clear other corpora.
6. **The CypherRAG schema paragraph is now fixed** (§7), because OQ1 is answered: occurrence graph, sheet via `is_drawn_on`, no `sheet_id` property on items, no unit nodes.
7. **`needs_data_attributes`, the "10 of 19", the "9-row topology-only subset", R5 and OQ2 are void** (ADR-0021). QA-T15 tags `scope` per row instead; QA-T16 judges only `scored` rows.
8. **"Runs against the local backend" (QA-T2, QA-T4, QA-T14) cannot be met**: no local runtime is installed (§6). Replaced by fake-transport checks.
9. **The live test's trigger changed** from "a key is set" to `--live-llm`, because `.env` is auto-loaded (§16).
10. **The `neo4j` dependency is already added** (§3); QA-T2 adds only `openai`.
11. **The ingest CLI exposes fewer split flags than `kg-construction.md` §8 lists** (no `--duplication-rate`, `--label-detail`, `--numbering`, `--grid`). The headline corpora need none of them (`SplitConfig` defaults are `duplication_rate=0.0`, `exact_match_tags=True`, `connector_label_detail=FULL`), but the could-item `SHEETS_OF_TAG` (`duplication_rate > 0`) needs `--duplication-rate` first.
12. **Task-id collision** with `kg-construction.md` T1–T8, resolved by the "QA-" prefix.
13. *(added 2026-10-01, QA-T7 built, uncommitted)* Choices the coder made where the spec was silent:
    unanswerable questions keep their template's answer type with `answerable=False`, `reference=None`,
    `k=None` (no `not_present` member exists); question ids include `template_id`; candidate-pool caps
    `UPSTREAM_ISOLATION` 6 hops (a longer route fails the precondition), `NO_PATH` 3 pairs per source,
    `UNANSWERABLE_TAG` 20 tags (module constants, not sample counts); X/A/B are equipment only;
    `COUNT_IN_UNIT` counts equipment and valves; `CROSS_UNIT` evidence = the cross-unit edges only and skips
    empty answers; `NO_PATH` reachability over `send_to` only; absent tags = highest sequence + 1 per
    (prefix, unit). Per-bin counts are required CLI flags (`--n-k0 … --n-unanswerable`), no default.
    Measured 2026-10-01, 25 units, budget 16, seed 0: 3,828 candidates; per bin 0: 2,419, 1: 716, 2: 134,
    3+: 46, unanswerable: 513; `CROSS_UNIT` only 13 — the 3+ bin is the thin one.

### 18.2 Steps that need a real model — run by the user, paid, need approval *(revised 2026-09-26, paid-call approval)*

None of these is a coder acceptance check. Each is started by the user with `--allow-paid-calls` (or `pytest --live-llm`), after approving it for that run.

| Step | Task | Why it needs a real model |
|---|---|---|
| OpenRouter smoke call | QA-T2 | proves the key, provider pin and `require_parameters` work |
| Listing snapshot | QA-T4 (§12 step 1) | network read, not a model call; listed here because it is run by the user |
| Wall probe | QA-T4 (§12 step 2) | the first measured context wall; probes near the wall are **the most expensive single calls** in the thesis (§12) |
| Cost, latency, variance | QA-T14 (§12 steps 3–4) | fixes the counts and the budget |
| Embedding-model choice | QA-T18 (§12 step 5), should | anchor hit@k on dev corpora |
| EXP-0001 runs and judges | after QA-T15/T16 | the baseline anchor (C5) |
| Judge agreement | QA-T16 | needs real EXP-0002 answers from D10 |
| EXP-0002 sweep and headline | after ADR-0019 | the thesis result |

## 19. Decisions taken in this note

Each has a real alternative. If the professor contests one, it becomes an ADR.

| # | Decision | Alternative | Why this one |
|---|---|---|---|
| D1 | Deterministic node cards | ChatP&ID's GPT-4o local and global descriptions per node | one or more LLM calls per node at up to 43,043 nodes, for a should-tier strategy; the deviation is stated as an EXP-0001 threat |
| D2 | In-memory numpy vector index | Neo4j vector index, as ChatP&ID uses | boring, no index configuration, works on the networkx fallback; 43,043 vectors fit on one machine |
| D3 | SQLite cache | one JSON file per call | a single file, atomic writes, thousands of entries |
| D4 | Every strategy is forced; no agent chooses | ChatP&ID's agent picks a tool | ChatP&ID's per-tool numbers are also single-tool; tool choice is a confound for the crossover. Agentic is a could-item |
| D5 | Hierarchical routes deterministically first | an LLM router always | cheaper and measurable (routing recall); the LLM router is the counted fallback |
| D6 | The fit check uses characters | tokens | no tokenizer is assumed across families; the wall is measured in the same unit |
| D7 | Cypher errors end the question (`RETRIEVAL_ERROR`) | pass the error to the final step | one clean diagnostic; saves a call; single attempt as in ChatP&ID |
| D8 *(added 2026-09-26, built code)* | ContextRAG (and Hierarchical) serialize the **occurrence graph**: stubs, `continues_as`, sheet per node | serialize `Resolution.plant`, the merged graph, with stubs removed | every strategy then sees the same corpus as the store, and Hierarchical stays "ContextRAG on a routed subset" by construction. The merged graph would hand ContextRAG a pre-resolved, smaller corpus that no other strategy gets. **Cost:** the stubs add characters, so ContextRAG's wall comes earlier than with the merged view; the pilot measures by how much, and the thesis states the direction. If the professor contests it, it becomes an ADR, with the merged view as a sensitivity run |
| D9 *(added 2026-09-26, built code)* | Only CypherRAG reads Neo4j; the other strategies read the in-memory occurrence view | every strategy reads through `Neo4jGraphView` | same content (QA-T3 proves it against `LoadPlan`), no database round trips while serializing up to H1000, and a K-NEO failure then costs CypherRAG points only. The store is still the system's store: CypherRAG and the harness's pre-check read it |

## 20. Open questions

- ~~**OQ1 (kg-construction).** Is the store sheet-level (occurrences plus `continues_as`) or merged? Do R1–R6 hold? The CypherRAG schema paragraph and `Neo4jGraphView` are written against the answer.~~ *(revised 2026-09-26, built code: **answered** — the occurrence graph; §2.1 gives R1–R6 one by one.)*
- ~~**OQ2 (R5, EX01 data attributes).** If the EX01 import drops them, 10 of the 19 EXP-0001 questions are unanswerable by construction, and only the 9-row topology-only subset is comparable.~~ *(revised 2026-09-26, ADR-0021: **closed** — no equipment data anywhere; §10 `scope`.)*
- **OQ3 (user).** What is the OpenRouter credit cap? It sets the budget line in §12, step 6.
- **OQ4 (user).** Which licence covers the released data? The code is AGPL-3.0; for comparison, PIDQA uses CC0 and Enginuity CC BY 4.0. Are pyDEXPI-generated corpora affected (ADR-0003)? Does OpenRouter's or the model provider's terms allow publishing responses (ADR-0014 open question 3)?
- **OQ5 (user).** May the transcribed ChatP&ID QA pairs go into the public repo? The licence of the arXiv version was not checked. Also cite the journal version, AIChE J., doi 10.1002/aic.70540 (`_novelty-log.md` 2026-09-26). App. Table 1's page numbers refer to arXiv v1. *(revised 2026-09-26, git ignore rule: until decided, the file stays local — `data/external/` is git-ignored since `d9c2c60` — and the thesis cites the paper's table plus the file's hash, §10.)*
- **OQ6 (pilot).** Does OpenRouter's listing offer GPT-5-mini, and can it be pinned to one provider? If not, EXP-0001 compares method, not model (ADR-0013 point 8).
- **OQ7 (user).** Does the Neo4j Desktop edition allow one database per corpus, or does the harness reload between corpora (R4)? *(revised 2026-09-26, built code: either works. `NEO4J_DATABASE` selects a database per corpus if the edition allows it; otherwise the user wipes the previous corpus and loads the next, and the harness's one-`DrawingSet` check (§11) enforces it. The reload time per corpus is what SMOKE-05 measures against K-NEO.)*
- **OQ8 (teaching).** The user has not met pre-registration, paired bootstrap confidence intervals or stratified sampling. Hungarian `/explain` notes are recommended before the user reads §13.3.
- **OQ9 (user)** *(added 2026-09-26)*. `data/questions/`, `data/runs/` and `data/llm-cache/` are **not** git-ignored today (only `data/external/` and `.env` are; checked with `git check-ignore`). Should run folders and the cache be committed, released only in the bundle, or ignored? This decides where the professor finds the replay cache (ADR-0013, Enables) and touches the provider-terms question in OQ4.
- **OQ10 (user)** *(added 2026-09-26)*. No local LLM runtime is installed (§6). None is needed for any coder task. Installing one (for example Ollama) would give free development calls with a real model; that is the user's choice, and nothing in this note assumes it.
## 21. Figures in this note and their sources

| Figure | Source |
|---|---|
| ContextRAG 0.91, CypherRAG 0.86, PathRAG 0.83, VectorRAG 0.82; 19 questions, 2 runs | `10-literature/2603.22528.md`; arXiv 2603.22528v1 §4.1 |
| PathRAG breadth 2, depth 3; one call per tool per test | arXiv 2603.22528v1 §4.1 |
| 8/2/5/3/1 question split; App. Table 1 on pp. 28–36 | ADR-0013 outcome log; PDF pp. 28–36, read 2026-09-26 |
| EX01: 214 complete / 36 conceptual; ChatP&ID 212 → 53 | `00-index.md`; brief of 2026-09-26 |
| ≈400 GraphML characters per node (5,829 / 27,769 / 296,943 / 5,990,747 characters at 1 / 4 / 50 / 1,000 units) | `50-progress/2026-W39.md`, measured 2026-09-25 |
| SMOKE-01: 1,000 units, 1,378 sheets, 14,687 nodes, 6,162 pairs | `30-experiments/_results.md` |
| SMOKE-02: 2,900 units, 4,015 sheets, 43,043 nodes | `30-experiments/_results.md` |
| OPEN100: mean 386 nodes per sheet | `00-index.md`, measured 2026-09-10 |
| ~38,000 nodes for a real 100-page document | ADR-0001 (an estimate from 100 × ~382) |
| PIDQA: 500 sheets, 64,000 questions; 2609.05880: 3,000 questions, single-sheet | `make7020039-pidqa.md`; `_novelty-log.md` 2026-09-26 |
| OpenRouter: OpenAI-compatible base URL; `usage` with cost; `provider.order` + `allow_fallbacks`; `require_parameters`; `/embeddings` | openrouter.ai/docs (API overview, provider routing, embeddings), fetched 2026-09-26 |
| 97 and 385 questions per bin | arithmetic: `(1.96 × 0.5 / δ)²` for δ = 0.10 and 0.05 |
| ~~10.7 nodes per sheet; ≈ 7 / 73 / 726 units; ≈ 100 / 1,070 / 10,700 nodes; ×36 sparser~~ | ~~derived from SMOKE-01 and SMOKE-02 by linear scaling~~; superseded 2026-09-26 by ADR-0017 (the row below) |
| *(revised 2026-09-26, ADR-0017)* budget 16: 42.6 nodes and 9.1 stubs per sheet; H100 ≈ 290 units ≈ 4,300 nodes; H1000 ≈ 2,900 units ≈ 43,043 nodes; H4000 ≈ 11,600 units ≈ 170,000 nodes | ADR-0017 (scratch diagnostic plus linear scaling: **estimates**, re-measured by SMOKE-06) |
| A10 ≈ 29 units ≈ 430 nodes; ≈ 14.84 nodes per unit; ×9 sparser than OPEN100; ≈ 4× nodes per sheet vs budget 4 | arithmetic: H100 ÷ 10; 43,043 / 2,900; 386 / 42.6; 42.6 / 10.7 |
| EX01: 36 conceptual nodes on one sheet; OPEN100: 96 connectors on 12 sheets (8.0 per sheet) | `kg-construction.md` §2; `splitter.md` §3 |
| *(revised 2026-09-26, ADR-0021)* ~~10 of 19 EXP-0001 rows need data attributes; 9-row topology-only subset~~ | ~~architect's reading of App. Table 1 by task type~~; void — the scored / out-of-scope split is counted in QA-T15 from the checked file |
| *(added 2026-09-26)* No local LLM runtime: `ollama` not on PATH, `%LOCALAPPDATA%\Programs\Ollama` absent, `~/.ollama/models` empty, no `~/.lmstudio`, nothing on `localhost:11434` or `localhost:1234` | read-only check by the architect on this machine, 2026-09-26 |
| *(added 2026-09-26)* `neo4j>=6.3.1`, `python-dotenv>=1.2.3` in dependencies; `data/external/` and `.env` git-ignored; `data/questions`, `data/runs`, `data/llm-cache` not ignored | `pyproject.toml` (working tree), `.gitignore`, `git check-ignore`, read 2026-09-26 |
| *(added 2026-09-26)* Store shape, `uid` format, `IngestResult.stage_seconds` keys, CLI flags and defaults (`--budget 16`, one `--seed`) | `src/plantgraph/store/neo4j_rows.py`, `neo4j_plan.py`, `neo4j_settings.py`, `ingest/pipeline.py`, `ingest/__main__.py`, `benchmark/split_models.py`, read 2026-09-26 |
