# Reading order — 2026-09-20

You have read **only Part 1** of `2026-09-13-reading-order.md`. So this note is **self-contained**: its
Part 3 reproduces that note's Parts 2-8 in full, in their original order and with their original item
numbers, with today's corrections applied inline. **You should not need to open the 09-13 note again.**

Everything is marked:

- 🆕 **NEW** — written or changed today, 2026-09-20. Not in the 09-13 note.
- ↩︎ **CARRIED** — still unread from the 09-13 note. Unchanged unless the entry says so.
- ⚠️ **CHANGED** — was in the 09-13 note, but today invalidated part of it. **Read the marker before
  the item**, or you will read something that is no longer true.

**Budget:** Part 0 is 2 minutes and saves you from reading dead pages. Parts 1-2 (new today) are about
45 minutes. Part 3 (carried, items 5-40) is the long one - it is the bulk of the 09-13 note you have not
reached yet, and most of it still stands exactly as written.

---

## Part 0 — Read this first: three things today changed under you

These three invalidate parts of the 09-13 note. Two minutes, and they save you from reading dead pages.

1. ⚠️ **Equipment data (step 3b) is dropped.** You said datasheets are out of scope — *"just the
   scaling interconnecting"*. The 09-13 note's **Part 8 question 1** (the DISCHARGE mapping) is therefore
   moot. You did answer it (`differentialPressure`) an hour before dropping it, and it was the right
   answer, but **no code ever shipped**. An implementation was started, then reverted uncommitted, so the
   repository has never contained an equipment-data feature. Also gone with it: requirement **N8**, and
   the `equipment_data` scaffolding that the 09-13 note described as "the type is already fixed so the
   builder signature will not change".
2. ⚠️ **The 09-13 note's "Commit first" instruction is done, and its hashes are dead.** The history was
   rewritten to strip tooling traces. `85d23f2` and `5585026` no longer exist. The splitter is now
   `96aeea1` and the whole 09-13 session is `42cc83d`. `2026-W38.md` said "nothing has been committed" —
   that line is now struck and corrected.
3. ⚠️ **The ontology position did not change** — but you asked, so read why in Part 1 item 1. Short
   version: your professor is right, and the code already agrees with them.

---

## Part 1 — 🆕 NEW, and the reason today mattered

### 1. 🆕 `docs/Notes/sajat-ontologia-leltar.md` (155 lines, Hungarian)

**What it is.** The note you asked for: what our ontology actually consists of, term by term, and what
each term is anchored to outside the project.

**Why it exists.** Your professor said connecting sheets and building a hierarchy with an ontology is
"maybe overkill". The honest answer needed an inventory first.

**The finding, and it is a good one:** we do **not** use an ontology to connect sheets, and never did.
The hierarchy and the cross-sheet links are six ordinary graph terms that already exist in
`graph/schema.py` — `DRAWING_SET`, `SHEET`, `HAS_SHEET`, `IS_DRAWN_ON`, `CONTINUES_AS`,
`SAME_TAGGED_ITEM_AS` — plus `ConnectorPair` and `IdentityGroup`. The ontology strand is only the RDF
comparison arm's vocabulary (ADR-0002), which keeps its own kill criterion.

**Read:** §4 (the table mapping "ontology talk" → what is already in the code) and §5 (the paragraph to
say back to your professor). **Skim:** §1–§3, which restate the vocabulary layers.

**Two of your calls are already in it.** **R3.4** (per-assertion provenance) is struck — you said it is
not needed, so the extension is **three items, not four**; `verified_by_human` stays as a CSV column in
the OPEN100 annotation, because it was never an ontology term. And **LPG/RDF stays exactly as it is** at
your instruction, so ADR-0002 is untouched and the end-of-phase-3 kill criterion still settles it.

**If the LPG-vs-RDF distinction itself is the unclear part:** `docs/Notes/lpg-vs-rdf.md` (236 lines,
Hungarian) explains it, and its "Egy kidolgozott példa" section writes **the same cross-sheet
connection in both models side by side**. That is the fastest way in. §4 of the inventory note now
points at it.

### 2. 🆕 `docs/private/30-experiments/2026-09-20-scale-smoke.md` (170 lines) — **the result of the day**

**What it is.** The first real end-to-end scale measurements the project has: **SMOKE-01, SMOKE-02 and
SMOKE-03** in one note. Not `EXP-000X` numbers — those stay reserved for the retrieval experiments.

**Two sizes were run** (sheet budget 4, seed 0, one laptop, one process):

| | 1,000 units | **2,900 units** |
|---|---|---|
| Sheets | 1,378 | **4,015** |
| `DiGraph` | 14,687 / 16,171 | **43,043 / 47,405** |
| Connector pairs | 6,162 | **18,048** |
| seed → `DiGraph` | 14.07 s | **49.42 s** (criterion 600 s → **12× margin**) |
| Full path incl. split | 15.21 s | **53.96 s** |
| Peak memory | 278.1 MiB | **785.7 MiB** |

**What it means: the kill criterion is not met at either size, so H1 stands and there is no fall back to
H3.** Growth is **slightly superlinear, not quadratic** — size ×2.93, time ×3.51, memory ×2.83 — so the
blow-up the stock `GraphLoader` showed does not appear on our path. **"Hundreds or thousands of sheets"
is now measured, not estimated:** over 4,000 sheets in under a minute, under 800 MiB.

Worth noting: §7 predicted "about a minute" for the 2,900-unit case before it was ever run. It was right.

**Read:** "Result", "Reading", and **"Threats" in full** — the threats are the honest part. **Skim:**
"Setup". **Threat 5 was `rejoin`, and it is already closed** — measured the same day, see item 2b below.
**Threat 1 is the live one:** the trend is fitted to two points, so anything above ~4,000 sheets is still
extrapolation.

### 2b. 🆕 SMOKE-03 — **"if we split it, can we put it back?"** (same run note, second half)

**You asked this directly, and the answer is yes — now with evidence at scale.**

The guarantee is the **round-trip invariant**: `rejoin(split(plant)) == plant`. Split the plant into
sheets, then rebuild it from the sheets plus the answer key; if anything is lost or invented, the
rebuilt graph differs. It is tested in three places — `test_splitter.py:42`,
`test_generator_integration.py:30` (every strategy) and `test_pydexpi_adapter.py:259` (real pyDEXPI
plants) — and `rejoin.py` exists **only** for this. It is not product code; it is proof.

**The gap, now closed:** all three tests run at `GeneratorConfig` defaults, i.e. **4 units**. The
invariant had never been shown on a big plant. Measured today across 7 sizes, 25 → 2,900 units:

| units | sheets | pairs | rejoin | round trip equal? |
|---|---|---|---|---|
| 1,000 | 1,378 | 6,162 | 0.504 s | **True** |
| 2,900 | 4,015 | 18,048 | 3.176 s | **True** |

**It holds at 4,015 sheets.** That is the benchmark's central correctness claim, and it now has
evidence above toy size.

**On the hotspot — I overstated it before measuring.** `rejoin.py:88` really is O(pairs × sheets), and
it grew ×6.30 for a ×2.9 size step, so the scan does dominate `rejoin`. But it is **3.18 s out of ~54 s,
about 6 %**, and `rejoin` is not part of the §2 kill criterion at all. I called it "the top engineering
risk" from arithmetic; the arithmetic was right, the conclusion was too strong. **Recommended, not
urgent:** a `dict[sheet_id, SheetGraph]` lookup, a few lines, before going much past 4,000 sheets.

**Read:** the SMOKE-03 section of the run note. **Background, if the invariant idea is new to you:**
`docs/Notes/why-a-synthetic-benchmark.md` §7 explains it in Hungarian, and now carries today's result.

### 3. 🆕 `src/plantgraph/benchmark/scale_smoke.py` (197 lines) and `tests/test_scale_smoke.py` (64)

**What it is.** The tool behind item 2. `python -m plantgraph.benchmark.scale_smoke --n-units N
--budget B --seed S [--no-memory]`. Times five stages separately (build, loader, conceptual, adapter,
split) and prints a JSON line so numbers reach a note without being retyped.

**Read the module docstring.** It carries a measured table that matters more than the code: **running
`tracemalloc` inflates the timings up to 9×**. The first version of this tool measured time and memory in
one pass, which made the pipeline look about 6× slower than it is — against a criterion that *is* a
wall-clock threshold. It was caught by cross-checking a fresh number against the 09-13 prototype table
rather than trusting it. Hence `--no-memory`, and hence two separate runs in the run note.

**Skim:** the rest. The test runs at tiny sizes only, by design — the real measurement is not a test.

### 4. 🆕/⚠️ `src/plantgraph/adapters/pydexpi_adapter.py` (394 lines) — **the one change worth a real look**

**What changed.** `plant_graph()` used to bundle three pyDEXPI steps into one call with no seam to time.
It is now split into three public functions — `load_complete_graph`, `abstract_conceptual_graph`,
`map_conceptual_graph` (the former private `_to_schema_graph`, renamed and made public) — which
`plant_graph()` composes, unchanged. Behaviour is identical; existing adapter tests cover it.

**Why:** `scale_smoke` lives in `benchmark/` and may not import pyDEXPI (ADR-0003 restricts that to
`adapters/pydexpi_*.py`), so the seams had to be exposed here.

**Read the three new function docstrings.** **Note for later:** this file is now **394 of 400 allowed
lines**. The next thing added to it will need a split first.

### 5. 🆕 The equipment-data removal — four files, small diffs

`generator_models.py` (203), `pydexpi_builder.py` (275), `generator.py` (315),
`graph_plant_builder.py` (133), `test_pydexpi_builder.py` (162). Net **−10 lines across the six changed
files**.

**What went:** `DataValue`, `GeneratorConfig.equipment_data`, the `data` parameter on
`add_equipment` (protocol, real builder and test builder) and its raise-on-non-empty guard, plus the
stale comments promising step 3b.

**Why removed rather than left dormant:** a parameter that must always be empty is exactly what your
professor asks "why is this here" about. **Skim the diff** (`git diff`); there is no logic in it.

### 6. 🆕 `CLAUDE.md` — your new hard rules

**Read this one properly**, it governs every future session.

- **Never commit, never push, never stage.** Including when you say "commit this" — the command and
  message get printed for you instead. Read-only git stays allowed.
- **No attribution trailers** in commit messages, and no mention of the tooling.
- **Use the repo's skills** when they apply; new ones get proposed to you, not built unasked.

I also corrected one stale line while in there: the Tooling row called ADR-0002 "not final", but it was
accepted on 2026-09-06.

### 7. 🆕 Design-note and index edits (skim only)

- `40-design/plant-generator.md` — struck banners on **§4.8**, the **N8** row, **§9 step 3b**, **§10 Q5**,
  and step 6's second assertion. **§10 Q2** now records your Proteus leaning (below). **§10 Q3** closed:
  Python ≥3.12 — verified in force today, `requires-python >=3.12`, ruff `py312`, mypy `3.12`, venv
  3.12.10.
- `00-index.md` — the scale result, the datasheet decision, the ontology entry, the Proteus leaning, the
  PDF backlog, and a rewritten Next action.
- `30-experiments/_results.md` — the `SMOKE-01` row, the first row that table has ever had.
- `50-progress/2026-W38.md` — the dead-hash correction.

---

## Part 2 — 🆕 Two things waiting on **you**

1. **Proteus exporter.** You said *"We will need this I think."* Recorded in §10 Q2 as a **leaning, not a
   decision**, and nothing was built. It belongs to the rendering phase, and it has a real alternative —
   write the piping/instrumentation exporter ourselves, or contribute it upstream to pyDEXPI under
   AGPL-3.0 — which makes it **ADR** material when the rendering design starts.
2. **Python 3.13?** You asked to raise Python to 3.12; it has been ≥3.12 since 09-13 and I closed the
   question. But note the drift the run note flags: the 09-13 prototype ran **3.13.1** and this venv runs
   **3.12.10**. If you want them to match, that is a separate, deliberate bump — say so and it is a
   two-line change.

---

## Part 3 — ↩︎ CARRIED from 2026-09-13: everything you have not read yet

You have read **Part 1 of the 09-13 note** (the four Hungarian teaching notes) and nothing after it. So
the whole of its Parts 2–8 is reproduced here **in full**, in its original order, with today's
corrections applied **inline** — you should not need to open the 09-13 note again.

Two corrections that apply to the Part 1 you already read:

- ⚠️ `docs/Notes/dexpi-modell-generalas.md` **lines 172–180** — the equipment data table with the
  DISCHARGE row. **Dead scope**, ignore it.
- ↩︎ Everything else in Part 1 stands.

Line counts are measured. Items keep their original 09-13 numbers so the two notes line up.

---

### Part 3a — Decisions (09-13 items 5–6)

**5. ↩︎ `docs/private/20-decisions/ADR-0007-external-validity-without-real-documents.md`** (184 lines).
Read it whole; it is **accepted**, and it is the decision the entire current phase rests on: plants are
generated with pyDEXPI rather than taken from real documents, realism is a later phase, and OPEN100's 23
pairs are held out for EXP-0004. Its options are numbered G1…G5, and **G5 is the design note's H1**
(line 79 says so) — the route that today's scale run just validated.

**6. ↩︎ `docs/private/20-decisions/ADR-0004-multipage-benchmark-by-inversion.md`** — only the **last
paragraph**, the outcome-log entry saying where plant graphs now come from. One minute.

---

### Part 3b — Design: `docs/private/40-design/plant-generator.md` (09-13 items 7–14)

The note is 818 lines; you are not reading all of it. In this order:

**7. ↩︎ The two boxed notes.**
- *"Offline split of step 3"* (above §3.2) — why the generator was built in two halves (topology first,
  then pyDEXPI), and the oracle test that ties them together.
- *"Post-implementation notes"* (above §4.1) — what changed once the schema was built.

**8. ↩︎ §0 Recommendation and §2 Options** — the H1 / H2 / H3 table and the kill criterion. ⚠️ **Read §2
with today's result in hand:** the kill criterion it defines is the one `SMOKE-01` just cleared by 43×.

**9. ↩︎ §3.2–§3.4** — input/output, the algorithm (the spec `generator.py` follows), and the invariants
(the spec the tests follow).

**10. ↩︎ §3.5 DEXPI construction and §3.6 Adapter.** Both built. Read before the adapter code below.
⚠️ §3.6 now has three public stage functions rather than one bundled call — see Part 1 item 4.

**11. ↩︎ §4.1–§4.5 Graph schema** and **§11 Method input contract**. ⚠️ **Skip §4.8** — struck today.

**12. ↩︎ §5 Splitter changes** (built) and **§10 Open questions**. ⚠️ In §10: **Q2** now records your
Proteus leaning, **Q3** is closed (Python ≥3.12), **Q5** is closed and moot (DISCHARGE).

**13. ↩︎ Skim:** §3.7 (files and persisted artefacts), §7 (prototype evidence), §9 (implementation
order). ⚠️ §7's estimate table is now **partly superseded by real measurement** — see Part 1 item 2.
⚠️ §9: step 3b struck, step 6 already complete, step 7 done.

**14. ↩︎ `docs/private/40-design/splitter.md`** — the original splitter design (2026-08-25). Read §1, §2
and §4; the banner at the top points to the §5 changes.

---

### Part 3c — Code: the splitter (09-13 items 15–20)

Committed as `96aeea1`. **Nothing here was touched today.**

**15. ↩︎ `src/plantgraph/benchmark/models.py`** (361). The answer-key data model — the heart of the
benchmark.
- **Skim** the OPEN100 classes at the top.
- **Read** `ConnectorPair`, `ConnectorKind`, `OffPageConnector`, `IdentityGroup`, `SplitManifest`.
- These are also the classes that answer your professor's ontology question — see Part 1 item 1.

**16. ↩︎ `src/plantgraph/benchmark/split_models.py`** (64). `SplitConfig`, `ConnectorLabelDetail`;
`equipment_classes` defaults to DEXPI class names.

**17. ↩︎ `src/plantgraph/benchmark/sheet_graph.py`** (27). `SheetGraph`. Two minutes.

**18. ↩︎ `src/plantgraph/benchmark/splitter.py`** (228). `split()` top to bottom, then
`_duplicate_equipment` and `_draw_on_neighbour_sheets`.

**19. ↩︎ `src/plantgraph/benchmark/strategies.py`** (274). `STRATEGIES`, then `flow_greedy` and its
helpers, `modularity`, `random_partition`, `by_unit`, `utility_aware`.

**20. ↩︎ `src/plantgraph/benchmark/rejoin.py`** (95). The test-only inverse behind the round-trip proof.
⚠️ **Worth attention now:** §7 flags `_stub_edge_attrs` as an unmeasured hotspot, and today's run makes
that concrete — 6,162 pairs × 1,378 sheets is ≈8.5 M sheet visits if the scan is per pair. It is on the
next-actions list.

---

### Part 3d — Code: schema, connectors, generator, adapter (09-13 items 21–32)

**Schema and connectors** — unchanged today.

**21. ↩︎ `src/plantgraph/graph/schema.py`** (285). `NodeClass` (20 DEXPI class names), `Relation` (9),
`CLASS_SPECS`, the class sets, `RELATION_ENDPOINTS`, `VISIBLE_NODE_PROPERTIES` /
`VISIBLE_EDGE_PROPERTIES`. ⚠️ **This is the file that answers the ontology question** — the six terms in
Part 1 item 1 all live here. An earlier version of today's work added equipment-data constants to it;
that was **reverted**, so the file is exactly as committed.

**22. ↩︎ `src/plantgraph/graph/validation.py`** (193). `validate_plant_graph`, `validate_sheet_graph`.

**23. ↩︎ `src/plantgraph/benchmark/connectors.py`** (181). `cut_remaining_edges` → `_cut_one_edge`;
`_connector_kind` / `_connector_class`; `_stub_node_attrs` (the visible label).

**Generator: topology, no pyDEXPI**

**24. ⚠️ `src/plantgraph/benchmark/generator_models.py`** — **was 213, now 203.** `GeneratorConfig`,
`StreamKind`, `GenerationRecord`, `ValveSpec`, `LoopSpec`, the `PlantBuilder` protocol, and
`PlantSummary`. **Changed today:** `DataValue` and `GeneratorConfig.equipment_data` removed, and the
`data` parameter dropped from the `PlantBuilder` protocol. The 09-13 note described `DataValue` as
"fixed now so the builder signature will not change" — that plan is void.

**25. ⚠️ `src/plantgraph/benchmark/generator.py`** — **was 316, now 315.** Read `plan_plant` first, then
`_GenerationState` in §3.3's step order: `add_sections` → `add_equipment` → `add_intra_unit_streams`
(`_add_tree`, `_maybe_add_recycle`) → `add_inter_unit_streams` (`_add_cross_unit_stream`,
`_maybe_add_cross_link`) → `_add_stream` (`_add_valves`) → `add_control_loops` → the id and tag
counters. **Changed today:** one `data={}` argument removed. That is the whole diff.

**Generator: pyDEXPI** (the only package allowed to import pyDEXPI)

**26. ↩︎ `pyproject.toml`.** Read the diff. Python ≥ 3.12 with ruff and mypy targets to match;
`pydexpi==1.2.0`; `.claude` excluded from ruff; `UP042` ignored with a comment on why (`StrEnum` would
change what enum members print); a mypy override limited to `pydexpi.*`. `uv.lock` changed with it — no
need to read that. ⚠️ Today this is **confirmed in force and the open question is closed**: you asked to
raise Python to 3.12 and it already was.

**27. ↩︎ `src/plantgraph/adapters/__init__.py`** (9). What the package is, and the import rule. ⚠️ That
import rule is exactly why item 29 had to change today.

**28. ⚠️ `src/plantgraph/adapters/pydexpi_builder.py`** — **was 287, now 275.** `DexpiPlantBuilder`: how
each topology decision becomes DEXPI objects (§3.5 table). Watch the dedicated sensing nozzle and the
explicit ids, which are what make seeds reproducible. Then `GeneratedPlant` and `generate_plant`.
**Changed today:** the `data` parameter and its raise-on-non-empty guard removed from `add_equipment`,
plus the module docstring paragraph about it.

**29. ⚠️ `src/plantgraph/adapters/pydexpi_adapter.py`** — **was 378, now 394. The one change worth real
attention** (also described in Part 1 item 4). `LinearGraphLoader` (the fast loader), then `plant_graph`
(pyDEXPI labels → our 4 relations, units folded onto nodes, valves' units derived) and
`ConversionReport`. **Changed today:** `plant_graph()` split into three composed public functions —
`load_complete_graph`, `abstract_conceptual_graph`, `map_conceptual_graph` — so `scale_smoke` can time
each pyDEXPI stage without importing pyDEXPI outside `adapters/`. Behaviour identical. **Now 394 of 400
allowed lines: the next addition needs a split first.**

**30. ↩︎ `src/plantgraph/adapters/pydexpi_io.py`** (62). JSON save/load (lossless) and the Proteus
export (equipment-only in pyDEXPI 1.2.0, documented). ⚠️ **This is the file behind your Proteus
remark** — "equipment-only" is the limitation you were reacting to.

**31. ↩︎ `src/plantgraph/adapters/plant_summary.py`** (74). `summarize_plant`: counts per class,
relation and stream kind.

**32. ↩︎ `src/plantgraph/__init__.py`, `benchmark/__init__.py`, `benchmark/open100/__init__.py`** (6–8
lines each). The only files the comment pass changed: short Hungarian module docstrings.

---

### Part 3e — Tests: the evidence (09-13 items 33–39)

Read after the code. Suite is now **238 tests**, up from 233 (+5 today, all `scale_smoke`).

**33. ↩︎ `tests/test_splitter.py`** (169). The **round-trip invariant** — the main correctness argument
for the whole benchmark. If you read one test file, this one.

**34. ↩︎ `tests/test_identity_groups.py`** (120). The tag-identity half the round-trip cannot see.

**35. ⚠️ `tests/graph_plant_builder.py`** — **was 134, now 133.** The test-only builder that writes the
schema graph directly: the **oracle**. **Changed today:** the `data` parameter removed to match the real
builder.

**36. ↩︎ `tests/test_generator.py`** (272) and **`tests/test_generator_integration.py`** (82).
Determinism, the global random state left untouched, schema validity, connectedness, branching, the
recycle / cross-link / control-loop rules, split round-trips on generated plants, and **invariant 8**
(`flow_greedy` and `modularity` cut generated plants differently — the plant is not a chain).
⚠️ **`test_generator_integration.py` is the file that turned out to make step 6 unnecessary:** invariant
7 at line 30, sheet-schema validity at line 45, invariant 8 at line 57.

**37. ↩︎ `tests/test_pydexpi_adapter.py`** (274). Read the **oracle-equality test** first,
`test_plant_graph_matches_the_oracle_builder_on_their_shared_properties`: the real pyDEXPI pipeline
gives exactly the oracle's graph for seeds 0–4. Then: JSON bytes identical per seed; no random uuids;
fast loader = pyDEXPI's loader; nothing unmapped; JSON round-trip; canonical order; and the splitter
round-trip on real DEXPI-generated plants for every strategy. ⚠️ Two of these — the loader-equality and
the no-unmapped-edges tests — are **limb (b) of the kill criterion**, and they pass, which is half of
why H1 stands.

**38. ⚠️ `tests/test_pydexpi_builder.py`** — **was 164, now 162.** The sensing-nozzle rule, and streams
with 0, 1 and 2 valves. **Changed today:** two `data={}` arguments dropped.

**39. ↩︎ Also new on 09-13:** `tests/test_pydexpi_io.py` (63), `tests/test_plant_summary.py` (41),
`tests/test_generator_models.py` (50), `tests/test_connectors.py` (81), `tests/test_schema.py` (145),
`tests/test_strategies.py` (100). **Skim:** `tests/plant_fixtures.py` (92),
`tests/test_splitter_models.py` (69).

---

### Part 3f — The comment pass (09-13 item 40)

**40. ↩︎ `docs/private/50-progress/2026-09-13-comment-audit.md`** (116 lines). Read "Summary", "Changes
applied" and "Test results after the pass".
- **Result:** your `python-comments` skill found the 23 files already compliant; only three empty
  `__init__.py` files needed docstrings (item 32).
- **Verification:** the coder compared code structure before and after with docstrings removed; the main
  session confirmed exactly 3 of 23 files changed.

---

### Part 3g — The 09-13 note's Part 8, "your answers"

**Done under the recommendations, and all still accurate** (tell me if you disagree):

- **Python target raised to ≥ 3.12.** ⚠️ You re-confirmed this today; the open question is now closed.
- **mypy override limited to `pydexpi.*`** — pyDEXPI ships no type marker.
- **`.claude` excluded from ruff.**
- **`UP042` ignored.**
- **pyDEXPI JSON is the lossless file**, and the Proteus export is labelled equipment-only.
- **ADR-0007 accepted with the builder route (H1)**, not pyDEXPI's own pattern sampler (H2).

**Its two open questions, resolved:**

1. ⚠️ **DISCHARGE → `differentialPressure` or `designPressureHead`?** **Moot.** You answered
   `differentialPressure`, then dropped datasheets an hour later. No code shipped.
2. ↩︎ **The `python-comments` skill folder** (`.claude/skills/python-comments/`) — **still uncommitted,
   and per the 2026-09-19 decision it is not to be committed.** Nothing to do; the question is closed
   unless you want to reopen it.

---

## Part 4 — Gates, and what to commit

**All four gates, run by me on the final tree, real output:**

```
uv run pytest            →  238 passed in 8.84s
uv run ruff check .      →  All checks passed!
uv run ruff format --check .  →  46 files already formatted
uv run mypy              →  Success: no issues found in 29 source files
```

**Nothing is committed — that is yours.** The working tree holds 6 modified files and 2 new ones
(`docs/` is excluded from git, so the notes above are local only). Suggested message:

```
Add scale_smoke and drop equipment data

Measure the full generate -> plant_graph -> split path at two sizes:
2,900 units gives 4,015 sheets in 49.42 s and 786 MiB peak, against a
600 s kill criterion, so the direct-builder route stands. Growth is
slightly superlinear, not quadratic.

Split plant_graph() into three public stage functions so the tool can
time each pyDEXPI stage without importing pydexpi outside adapters/.
Measure timings and memory in separate runs: tracemalloc inflates the
stage times up to 9x, which would have overstated the criterion by 6x.

Remove the equipment-data plumbing: datasheets are out of scope.
```

**Done — you committed as `b30414b`**, and the run note's Setup line and threat 7 now name that hash
instead of "uncommitted working tree".

---

## If you read only three things

1. **Part 0** — the three things that changed under you (2 min).
2. **`2026-09-20-scale-smoke.md`**, Result + Reading + Threats — the number the thesis rests on.
3. **`sajat-ontologia-leltar.md` §4** — the table that answers your professor.
