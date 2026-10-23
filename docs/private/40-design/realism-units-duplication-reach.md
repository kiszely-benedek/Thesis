---
component: benchmark realism pass — units that span sheets, duplication, signal labels, unit nodes in the store, question reach; utilities parked
status: draft — awaiting review
related: [ADR-0025, ADR-0026, ADR-0027, ADR-0028, ADR-0029; ADR-0010, ADR-0013, ADR-0015, ADR-0017, ADR-0023]
date: 2026-10-01
---

# Design — realism pass before the first paid run

Triggered by UNITS-01 (2026-10-01): units are smaller than a sheet. User decisions (2026-10-01): make units larger;
turn duplication on; keep tags 1:1; park utilities; let questions reach far across sheet and unit boundaries; the
store must hold faithful, queryable content (speed is not a criterion). No paid run has happened, so every change
here is cheap now and expensive after the headline (ADR-0010 ordering is respected: KG construction first, then
the question side, then the pilot).

## 0. Recommendation

| # | Item | Decision (ADR) | Effort, **estimate** (coder pace is unmeasured, ADR-0015) |
|---|---|---|---|
| 1 | Units span ~~2–4~~ **1–2** sheets (user, 2026-10-01), one unit per sheet | ~~24–72~~ **18–36** equipment/unit; `by_unit` with unit-aware clustering and balanced chunks at budget 18; headline sizes stay in sheets (ADR-0025) | 2 coder tasks (RU-T2, RU-T3) |
| 1b | **Found while measuring:** G1 fails at DRAWING_ONLY today (8 / 30 unresolved signal connectors at 1,000 / 2,900 units) | Signal flags print the loop number (ADR-0027) | 1 small task (RU-T1) |
| 1c | Units in Neo4j | `PlantSection` / `ProcessPlant` nodes, `is_located_in`, a `unit_id` index (ADR-0026) | 1 task (RU-T4) |
| 2 | Utilities | **Parked** (user, 2026-10-01). §6 holds the evidence only | — |
| 3 | Duplication | On in every headline corpus at 0.25, exact tags; `k` counts identity crossings; `SHEETS_OF_TAG` must (ADR-0028) | 2 tasks (RU-T7, RU-T8) |
| 4 | Inexact tags | Stay in EXP-0004, out of the headline (ADR-0028) | none |
| 5 | Question reach | No hop caps, doubling k-bins, per-bin availability gate, sample-before-build enumeration (ADR-0029) | 2 tasks (RU-T5, RU-T6) |

Total: 8 coder tasks, one at a time, plus 5 main-session runs (§7), each a few minutes of machine time (the H1000
probe built, split, resolved and gate-checked in 43.0–51.5 s).

## 1. Which part of the claim it serves

- **Hierarchical routing (plant → unit → sheet) only means something if a unit is a group of sheets.** It is the
  design contribution the headline tests (C4).
- **`k` is the claim's x-axis** (ADR-0013). It must count every sheet boundary, including identity crossings, and
  must reach as far as the plant allows. Otherwise the regime where a queryable KG should beat ContextRAG is cut
  away.
- **G1 must hold end to end at DRAWING_ONLY** (ADR-0023). Today it does not (§2).

## 2. Evidence (architect scratch probes, 2026-10-01)

**Method.**
- Scripts live in the session scratchpad and are not in the repository:
  `units_probe.py`, `signalfix_probe.py`, `patches.py`, `patches_unitcluster.py`, `reach_probe.py`,
  `reach_dup_probe.py`, `dup_probe.py`, `enum_timing.py`, `units_rule*.py`.
- They call the repository's `ingest.pipeline.build_synthetic_corpus` and `_check_gate`, and the QA family code.
- Proposed code is imitated by **monkeypatches**: the loop number, balanced chunks and unit-aware clustering.
- Seed 0 unless stated. Every figure is re-measured on the real code by the runs in §7, and only those are cited
  from then on.

| Finding | Number | Where |
|---|---|---|
| The probe reproduces SMOKE-06 | 1,000 u: 345 sheets, 42.57 nodes/sheet, 9.08 stubs/sheet, 1,566 pairs. 2,900 u: 1,004 sheets, 4,558 pairs | ADR-0027 |
| UNITS-01's counting rule | All nodes with `unit_id` reproduce it exactly (mode 5 on 132 sheets; 440/430/85/45). Equipment-only gives 476/430/70/24 | ADR-0025 |
| G1 at DRAWING_ONLY, today's code | false: 8 unresolved at 1,000 u, 30 at 2,900 u; inspected ones are all signal | ADR-0027 |
| Units-per-sheet fix | 24–72 eq, `by_unit` b18 balanced + unit-aware clustering: 1 unit on every sheet; 37.53–39.69 nodes/sheet, 7.38–7.55 stubs/sheet (~H100, seeds 0–2); H1000 = 320 u → 999 sheets, 39,231 nodes, 39.27 nodes/sheet | ADR-0025 |
| Duplication 0.25 at H1000 | 766 identity groups, 2,896 pairs, 5.80 stubs/sheet, G1 true, identity P = R = 1.0 | ADR-0028 |
| `k` under duplication | Connector-only `k` shifts mass to low bins. Home-sheet `k` at rate 0.25 equals `k` at rate 0.0, bin for bin | ADR-0028 |
| Question reach | Within 6 hops: 16.7 % (~H100) and 12.7 % (H1000) of reachable pairs; max k 11 / 16; max units crossed 5 / 8 | ADR-0029 |
| Enumeration cost today | H1000: `LOOKUP_TYPE` 119.6 s, `LOOKUP_UNIT` 134.7 s; `FLOW_PATH` unfinished inside a 900 s limit | ADR-0029 |

## 3. Data model and interfaces

### 3.1 Splitter (`benchmark/strategies.py`, `benchmark/connectors.py`, `benchmark/models.py`)

**`by_unit`** (ADR-0025). Two changes, local to this strategy:
- **Unit-aware owners.** `_cluster_owners(plant, classes, *, same_unit: bool = False)`. With `same_unit=True`, the
  BFS never assigns a node that carries `unit_id` U to an owner whose `unit_id` differs from U. Nodes without
  `unit_id` keep today's rule. `flow_greedy`, `modularity`, `utility_aware` and `random` pass `False`, so their
  output is byte-identical to today.
- **Balanced chunks.**
  - `_balanced_sizes(n_equipment: int, budget: int) -> list[int]` gives m = ⌈n/B⌉ sizes that differ by at most 1,
    larger first.
  - `_chunk_by_sizes(order, equipment_owners, sizes) -> list[list[str]]` cuts the unit's owner order at those
    equipment counts. Non-equipment owners ride along, as in `_chunk_by_budget`.

**Signal loop number** (ADR-0027).
- `OffPageConnector.loop_tag: str | None = None`.
- In `_cut_one_edge`, for a `SIGNAL` cut, `loop_tag` is the source's `loop_tag`, else the target's. It is written on
  both stub nodes and both `OffPageConnector`s.
- `loop_tag` is already in `schema.VISIBLE_NODE_PROPERTIES`, so `localize` keeps it.
- Pipe stubs are unchanged.

### 3.2 Resolver (`resolution/connector_labels.py`, `resolution/pairing.py`)

- `ConnectorLabel.loop_tag: str | None`, read from the stub node.
- `_group_key` appends `loop_tag`. Nothing else changes, and pair precision stays 1.0 by the §5.2 property of
  `kg-construction.md`.

### 3.3 Headline preset and size search (`ingest/headline.py`, new; `ingest/__main__.py`)

```python
class HeadlinePreset(BaseModel):          # frozen; the single source of truth for headline corpora
    equipment_per_unit_min: int = 18   # amended 2026-10-01: 1–2 sheets per unit (was 24)
    equipment_per_unit_max: int = 36   # (was 72)
    strategy: str = "by_unit"
    sheet_equipment_budget: int = 18
    connector_label_detail: ConnectorLabelDetail = ConnectorLabelDetail.DRAWING_ONLY
    duplication_rate: float = 0.25
    exact_match_tags: bool = True
    def generator_config(self, n_units: int, seed: int) -> GeneratorConfig: ...
    def split_config(self, seed: int) -> SplitConfig: ...

class SizeSearchResult(BaseModel):
    target_sheets: int; n_units: int; predicted_sheets: int

def smallest_n_units(target_sheets: int, preset: HeadlinePreset, seed: int) -> SizeSearchResult: ...
```

**Size search.** Under `by_unit`, a corpus's sheet count is Σ over units of ⌈equipment(u) / B⌉. Unit sizes are drawn
in §3.3 step 1 for all units before any stream, so they form a prefix-stable sequence in `n_units`. The search
therefore:
1. runs `plan_plant` once, at an upper bound, with a `_CountingBuilder` that implements the `PlantBuilder` protocol,
   counts equipment per unit and builds nothing (no pyDEXPI, fast);
2. takes the smallest prefix whose sum reaches the target.

The CLI then builds the corpus and **asserts** that the realized `n_sheets ≥ target` and that `n_units − 1` would
fall short. The search is a convenience; the build is the truth.

**CLI.** `ingest synthetic` gains:
- `--headline`, which applies the preset;
- `--target-sheets N`, an alternative to `--n-units` that runs the search;
- `--eq-min/--eq-max`, for non-headline runs.

`GeneratorConfig`'s defaults (3/8) stay, so no existing test changes.

### 3.4 Store (`store/neo4j_rows.py`, `store/neo4j_plan.py`) — ADR-0026

- **New rows.** `PlantSection {uid: f"{corpus_id}|unit:{unit_id}", corpus_id, unit_id}` per distinct visible
  `unit_id`, and `ProcessPlant {uid: f"{corpus_id}|plant:{plant_id}", …}` per distinct `plant_id`.
- **New relationships.** `is_located_in` from every occurrence that carries `unit_id` to its `PlantSection`, and from
  each `PlantSection` to its `ProcessPlant`.
- **New index.** `CREATE INDEX corpus_node_unit_id IF NOT EXISTS FOR (n:CorpusNode) ON (n.unit_id)`.
- **Verify.** `expected_node_labels` and `expected_relationship_types` include the new elements, and the loader's
  verify step checks them. **This is the store's faithfulness check:** every unit and every membership in the
  sheets is in the store, and nothing else is.
- **In memory.** `NetworkxGraphView` and `serialize.py` are unchanged (structure folded into attributes). The QA-T3
  equality test adds `PlantSection`, `ProcessPlant` and `is_located_in` to its exclusion list.

### 3.5 Questions (`qa/models.py`, `qa/questions/*`) — ADR-0028, ADR-0029

**`Question`** gains three gold fields: `k_connector: int | None`, `k_identity: int | None` and `u: int | None`,
the units crossed. `k` keeps its name and becomes the home-sheet count.

**`evidence.py`:**
- `class SheetIndex` is built once per corpus. It holds `home: dict[node_id, sheet_id]` (from
  `IdentityGroup.home`, else the node's only sheet), `sheets_of: dict[node_id, frozenset[sheet_id]]`, and the
  connector cut.
- `crossings(evidence, index, plant) -> Crossings(k, k_connector, k_identity, u)`:
  - `k` counts evidence edges whose endpoints' home sheets differ;
  - `k_connector = |edges ∩ cut|`;
  - `k_identity = k − k_connector`;
  - `u` counts edges whose endpoints carry different `unit_id`s.
- `evidence_sheets` reads `sheets_of`, at O(|evidence nodes|) per question.

**Bins (`availability.py`).**
- `KBin` = `K0, K1, K2, K3_4, K5_8, K9_16, K17_32, K33_PLUS, UNANSWERABLE`. The enum is fixed, and an empty bin
  reports 0.
- `BinTargets` becomes `per_bin: int` plus `unanswerable: int`. The CLI flags are `--n-per-bin` and
  `--n-unanswerable`.
- `AvailabilityReport` gains `powered: dict[KBin, bool]` (at least 97 candidates after the cap), a
  `u_histogram`, and `build_seconds`.

**Families.**
- **`FLOW_PATH`:** no hop cap. For each source, one forward BFS records `(target, path)`; each target is binned by
  `k`; one target per (source, bin) is drawn with `random.Random(f"{seed}:{source}")`; and only those become
  `Question`s.
- **`UPSTREAM_ISOLATION`:** walks with a visited set and no hop cap. The precondition is unchanged.
- **`UNANSWERABLE_TAG`:** no cap, one absent tag per (prefix, unit). `NO_PATH` is unchanged.
- **`SHEETS_OF_TAG`** (new, `families_identity.py`):
  - template "On which sheets is {tag} drawn?", with `AnswerType.SHEET_SET`;
  - reference = sorted home and reference sheet ids;
  - k = number of reference occurrences;
  - candidates = every identity group, plus an equal number of single-sheet equipment items drawn with a seeded
    rng (k = 0).
- **`scoring.py`:** `SHEET_SET` is set-matched like `TAG_SET`.
- **`final_answer`:** one new instruction string, "sheet ids as printed on the sheets".

### 3.6 What does not change

The generator's topology rules, ids and tags; `localize`; `merge`; identity grouping; the CypherRAG and ContextRAG
designs except the one schema sentence (ADR-0026); `flow_greedy` and the other strategies, which stay available as
non-headline splits.

## 4. How it is tested (every task offline: ruff, mypy --strict, pytest green)

| Component | Unit tests |
|---|---|
| signal loop number | Two loops cut between the same sheet pair in the same direction pair correctly at DRAWING_ONLY. A 4-unit plant at DRAWING_ONLY gives pair precision 1.0 and G1 true. Pipe stubs carry no `loop_tag`. The manifest JSON round-trips |
| `by_unit` | No sheet mixes units, counted over **every** node with `unit_id`. Within a unit, sheet equipment counts differ by at most 1, and the sheet count is ⌈n/B⌉. Other strategies give byte-identical manifests to before (golden hash on a fixed plant). It raises without `unit_id` |
| preset and search | `smallest_n_units` equals a brute-force linear scan on 3 small targets. The preset round-trips into `ingest.json`. `--headline` with `--n-units` writes the preset values |
| store | The new rows have unique uids. `expected_*` counts include `PlantSection` and `is_located_in` and equal counts taken independently from the sheets. Reference occurrences and stubs have no `is_located_in`. The schema statements include the `unit_id` index. The opt-in Neo4j test verifies the counts |
| `k` and `SheetIndex` | On a hand-built split toy plant with one duplicated item: `k`, `k_connector`, `k_identity` and `u` equal the hand values. At duplication 0, `k == k_connector`. `evidence_sheets` equals the old scan's output on 3 seeds |
| reach and bins | A 12-hop chain toy plant yields a k = 9–16 candidate, which the old cap would have dropped. At most one question per (family, anchor, bin). The same seed gives byte-identical JSONL. `powered` follows the 97 rule |
| `SHEETS_OF_TAG` | The reference equals the manifest's group sheets. k = 0 controls exist. Scoring is order-insensitive |

**How each reports its accuracy.**
- **Splitter:** units per sheet, sheets per unit, density.
- **Resolver:** G1, plus pair and identity P/R.
- **Store:** verify counts.
- **Question generator:** hand-checked toy values, the availability report, and QA-T12's Cypher-vs-networkx
  agreement.

## 5. Interactions to watch

- **`CROSS_UNIT` gets thin.** It has 20 candidates at ~H100 (33 units), against 160 today. That is not a problem
  for bins (families mix), but per-family accuracy at H100 rests on 20 questions. Report that, do not hide it.
- **`COUNT_IN_UNIT` moves to high k.** Every candidate sits at k ≥ 3 at ~H100 (297 of 297), because a unit spans
  2–4 sheets. That is the intended "aggregate over a unit that spans sheets" (ADR-0013).
- **ContextRAG's prompt shrinks slightly.** At ~H100 it falls from 2,067,229 to 1,950,991 characters, because the
  plant has 4,009 nodes instead of 4,145 (measured before the unit-aware clustering refinement). Duplication 0.25 takes it a further −2.6 %. The wall is re-probed in the
  pilot anyway.
- **A10 shrinks.** About 10 sheets is 3–4 units, so unit families there are tiny. A10 is the "ContextRAG fits"
  anchor, not a unit test.
- **QA-T7 is built (`5ea63b5`).** RU-T5 and RU-T6 modify it. `qa-system.md` §18.1 item 13 (caps of 6 hops and 20
  tags) is superseded by ADR-0029.

## 6. Utilities — parked (user, 2026-10-01: wanted "by the end", after the simpler things work)

**Not designed here.** Kept: the evidence and what it would touch.

**OPEN100 evidence** (`30-experiments/open100-stage1/open100_connectors.csv`, 96 connectors, recounted
2026-10-01):
- **Utility services on connector flags:** ACW 8, SWS 5, CAS 1.
- **Dangling connectors:** 42, pointing at sheets not in the 12-sheet set. Among their named targets: Service Water
  System 5, Water Sample System 5, Rad Waste / Chemical Addition 5, Waste Process System 4, Make-Up Water 1.

The real set therefore references utility and auxiliary systems drawn elsewhere. That matches HNF 3.2.5.2 ("Main
utility headers are not shown on the unit P&ID") and C4/S13 in `pid-structural-rules.md`.

**What a rule-grounded version touches, when unparked:**
- **Generator:** utility headers as their own `PlantSection` (P5: "Utilities").
- **Consumers:** they keep a short service-labelled stub (C4).
- **Splitter:** utility sheets (S13).
- **Data model:** a one-to-many service reference that `ConnectorPair` cannot express (index, "Four findings"
  item 1).
- **Resolver:** service-code linking.
- **Store:** service-reference edges.
- **Question families:** for example, the consumers of a utility.

**Size, estimate:** comparable to this whole note, roughly 6–8 coder tasks. It needs its own design note and ADR,
including whether `utility_aware` is repaired or retired.

## 7. Runs and gates (main session; criteria fixed here, before the runs)

| Run id | What | Pass criteria |
|---|---|---|
| **SMOKE-04b** | `ingest synthetic --headline --check --no-neo4j` at H100 and H1000 (seed 0), plus the old-config 1,000 / 2,900-unit DRAWING_ONLY rerun as a regression | G1 true and 0 unresolved everywhere; identity P = R = 1.0; pair precision 1.0. This is ADR-0023's gate |
| **SMOKE-07** | density on the headline preset at H100 and H1000 | nodes/sheet in [36, 43]; stubs/sheet in [2, 12]; equipment/sheet reported |
| **UNITS-02** | UNITS-01 re-measured on the preset, with UNITS-01's rule (all nodes with `unit_id`) | every sheet shows exactly 1 unit; sheets per unit reported |
| **SMOKE-05b** | Neo4j load of H1000 with unit nodes | verify counts match `expected_*` (faithfulness). K-NEO's 600 s stays the only time limit |
| **AVAIL-01** | question availability on H100, H1000 (seed 0) and D100 (seed 1), at duplication 0.25 and once at 0.0 | the build finishes in ≤ 600 s at H1000; bins 0, 1, 2 powered at both sizes; every powered and underpowered bin reported. The `k` histogram at 0.25 equals the one at 0.0 (ADR-0028's invariance) |

If a criterion fails, the run is still recorded in `_results.md`, and the relevant ADR's revisit clause applies.

## 8. Ordered coder tasks (one Sonnet coder at a time; each ends green on ruff, mypy --strict, pytest, offline)

| # | Task | Depends on | Size (estimate) |
|---|---|---|---|
| **RU-T1** | Signal loop number: `OffPageConnector.loop_tag`, the stub attribute, `ConnectorLabel.loop_tag`, `_group_key` (§3.1–3.2) | — | S |
| **RU-T2** | `by_unit`: unit-aware owners and balanced chunks (§3.1); golden-hash test that other strategies are unchanged | — | S |
| **RU-T3** | `ingest/headline.py` preset + `smallest_n_units` + CLI `--headline`, `--target-sheets`, `--eq-min/--eq-max` (§3.3) | T1, T2 | M |
| — | *Main session: SMOKE-04b, SMOKE-07, UNITS-02* | T3 | minutes |
| **RU-T4** | Store: `PlantSection`/`ProcessPlant` rows, `is_located_in`, `unit_id` index, verify counts, QA-T3 exclusion list (§3.4) | — | M |
| — | *Main session: SMOKE-05b* (needs the user's Neo4j) | T3, T4 | minutes |
| **RU-T5** | Enumeration at scale: `SheetIndex`; FLOW_PATH with no cap and per-(source, bin) draw; visited-set isolation walk; no cap on unanswerable tags (§3.5) | — | M |
| **RU-T6** | Doubling `KBin`, `BinTargets.per_bin`, `powered`, `u`, `build_seconds`, CLI flags (§3.5) | T5 | M |
| **RU-T7** | Home-sheet `k`, `k_connector`, `k_identity` (§3.5) | T5 | S |
| **RU-T8** | `SHEETS_OF_TAG` + `AnswerType.SHEET_SET` + scoring + final-answer string (§3.5) | T7 | M |
| — | *Main session: AVAIL-01* | T3, T6, T8 | minutes |

S is under about 150 changed lines including tests; M is about 150–400. Both are estimates.

**Order rationale.**
- **RU-T1 first:** it fixes a gate that fails today, independent of everything else.
- **RU-T1 → T3 next:** they give a measurable partial result (SMOKE-04b, SMOKE-07, UNITS-02) before any
  question-side change.
- **Then the queue:** QA-T9 onward continues after RU-T8.

## 9. Documents the main session updates on acceptance (accepted ADRs get outcome-log lines only)

- **ADR-0017:** outcome log, "headline split superseded in part by ADR-0025".
- **ADR-0023:** outcome log, "revisit clause fired; ADR-0027".
- **ADR-0013:** outcome log, "binning per ADR-0029; `k` counts identity crossings per ADR-0028".
- **ADR-0015:** outcome log, H1000 ≈ 39k nodes (probe), pending SMOKE-07.
- **ADR-0011:** outcome log, "utilities parked (user, 2026-10-01)".
- **`qa-system.md`:**
  - §9 families table: add `SHEETS_OF_TAG` as must; mark `k` as home-sheet based;
  - §12 step 6 and §13.3: per-bin floor applies per powered bin; fallback order;
  - §13.1: the preset;
  - §18.1 item 13: superseded;
  - §7: the CypherRAG schema sentence.
- **Other notes:**
  - `kg-construction.md` §7.2: deferral closed;
  - `splitter.md`: `by_unit` refinements and the headline;
  - `00-index.md`.

## 10. Open questions

1. **Unit size, user.** 24–72 equipment per unit, about 3 sheets per unit, is a declared choice. Is "2–4 sheets per
   unit" the "several" the user meant? A larger range (32–96 measured 2–6 sheets per unit, mean 4.6, before the
   final refinements) is a one-parameter change.
2. **Duplication rate, user.** Is 0.25, the lowest probed rate not below OPEN100's lower bound, acceptable as the
   one headline value, with the {0, 0.5} sensitivity at H100 as a should-item?
3. **Bin floor cost, user, after the pilot.** Doubling bins mean 7 × 97 = 679 questions per corpus × strategy ×
   repeat at the floor, against 485 today. The fallback order in ADR-0029 step 7 applies if the pilot prices it out.
4. **Sheet → unit edge.** It is derivable today. Add `(:Sheet)-[:is_located_in]->(:PlantSection)` only if
   Hierarchical's Cypher form needs it (ADR-0026, revisit).

## 11. Figures in this note and their sources

| Figure | Source |
|---|---|
| UNITS-01 and SMOKE-04/05/06 values | `30-experiments/_results.md` |
| Every other number in §0–§5 and §7 | architect scratch probes, 2026-10-01 (§2 method); re-measured by §7's runs |
| OPEN100 connector services and dangling targets | `30-experiments/open100-stage1/open100_connectors.csv`, recounted 2026-10-01 |
| OPEN100 multi-sheet items (≥ 5) | `40-design/open100-annotation.md` lines 85 and 132 |
| HNF 3.2.5.2, KLM item 8, C4, C7, C11, P5, S13, S16 | `10-literature/pid-structural-rules.md` |
| 97 per bin | `qa-system.md` §12 step 6 (arithmetic `(1.96 × 0.5 / 0.10)²`) |
| 679 and 485 questions | arithmetic: 7 × 97 and 5 × 97 |
