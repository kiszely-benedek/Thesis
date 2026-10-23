# Reading order — work of 2026-09-10 to 2026-09-13

Everything written or changed since the splitter was started, in the order that makes it easiest to follow:
**why → decisions → design → code → tests → your answers.** Each item says what it is, what changed and what you
can skim. Line counts are measured.

**Commit first** (commands are in the chat), so what you read is what is in git.

**State in one paragraph.**
- **Committed earlier:** the splitter, which cuts a plant graph into sheets with off-page connectors and an answer
  key (built 2026-09-10, `85d23f2`).
- **Uncommitted, from 2026-09-13:**
  - the graph schema and validators;
  - pipe/signal connectors with visible labels;
  - the `by_unit` strategy;
  - **the whole plant generator:**
    - `plan_plant` decides the topology from one seed;
    - `DexpiPlantBuilder` builds a real pyDEXPI `DexpiModel` from those decisions;
    - the adapter turns the model into the graph the splitter cuts;
  - a comment pass with your `python-comments` skill.
  - **233 tests**; ruff, format and mypy --strict clean.
- **ADR-0007 is accepted.**
- **Not built yet:** equipment data (waits for your DISCHARGE answer), the scale smoke run, utilities.

---

## Part 1 — Orientation (Hungarian teaching notes)

1. **`docs/Notes/why-a-synthetic-benchmark.md`** (09-10). Why the splitter exists: the inversion idea, the four
   strategies, the round-trip invariant.
2. **`docs/Notes/uzemgenerator-es-grafsema.md`** (303 lines). Read **§1–§5**; skip §0, which is superseded (see
   its banner).
   - §1: the random tree that `generator.py` implements.
   - §2: the two schema layers.
   - §3: visible vs hidden fields, with the `P-101` example.
   - §4: where the pump sits.
   - §5: what our method takes as input.
3. **`docs/Notes/dexpi-modell-generalas.md`** (228 lines). The pyDEXPI route: what a `DexpiModel` is, streams and
   control loops in DEXPI, the two file formats, model → graph, why the loader was slow, the id trap, the
   equipment data table, the input contract. It explains most of Part 5's second half.
4. **Short, if not read yet:** `docs/Notes/adapter-minta.md` (why an adapter — you asked) and
   `docs/Notes/adr-eletciklus.md` (proposed vs accepted).

## Part 2 — Decisions

5. **`docs/private/20-decisions/ADR-0007-external-validity-without-real-documents.md`** (184 lines). Read it
   whole; **accepted**. Its options are numbered G1…G5; **G5 is the design note's H1** (line 79 says so).
6. **`docs/private/20-decisions/ADR-0004-multipage-benchmark-by-inversion.md`**. Only the **last paragraph**:
   the outcome-log entry saying where plant graphs now come from.

## Part 3 — Design: `docs/private/40-design/plant-generator.md` (818 lines, revision 2)

Not all of it. In this order:

7. **The two boxed notes.**
   - "Offline split of step 3" (above §3.2): why the generator was built in two halves (topology, then pyDEXPI),
     and the oracle test that ties them together.
   - "Post-implementation notes" (above §4.1): what changed when the schema was built.
8. **§0 Recommendation** and **§2 Options** (the H1 / H2 / H3 table and the kill criterion).
9. **§3.2–§3.4**: input/output, the algorithm (the spec `generator.py` follows), the invariants (the spec the
   tests follow).
10. **§3.5 DEXPI construction** and **§3.6 Adapter**. Now built; read them before Part 5's adapter items.
11. **§4.1–§4.5 Graph schema** (built), **§4.8 Equipment data** (not built yet), **§11 Method input contract**.
12. **§5 Splitter changes** (built) and **§10 Open questions** (feeding Part 8).
13. **Skim:** §3.7 (files and persisted artefacts), §7 (prototype evidence), §9 (implementation order).
14. **`docs/private/40-design/splitter.md`**. The original splitter design (2026-08-25). Read §1, §2 and §4; the
    banner at the top points to the §5 changes.

## Part 4 — Code: the splitter of 2026-09-10 (committed `85d23f2`, adjusted today)

**Today's changes are marked.**

15. **`src/plantgraph/benchmark/models.py`** (361). The answer-key data model.
    - Skim the OPEN100 classes at the top.
    - Read `ConnectorPair`, **`ConnectorKind` (new)**, `OffPageConnector` (**new fields**), `IdentityGroup`,
      `SplitManifest`.
    - One mechanical change for Python 3.12: `timezone.utc` → `UTC`.
16. **`src/plantgraph/benchmark/split_models.py`** (64, **new**). `SplitConfig`, **`ConnectorLabelDetail`**;
    `equipment_classes` defaults to DEXPI class names.
17. **`src/plantgraph/benchmark/sheet_graph.py`** (27, **new**). `SheetGraph`.
18. **`src/plantgraph/benchmark/splitter.py`** (228). `split()` top to bottom, then `_duplicate_equipment` and
    `_draw_on_neighbour_sheets`. **Changed:** connector cutting moved to `connectors.py`.
19. **`src/plantgraph/benchmark/strategies.py`** (274).
    - `STRATEGIES`, then `flow_greedy` and its helpers.
    - `modularity`, `random_partition`.
    - **`by_unit` (new).**
    - `utility_aware`: **docstring added**.
20. **`src/plantgraph/benchmark/rejoin.py`** (95). The test-only inverse behind the round-trip proof.

## Part 5 — Code: new today

**Schema and connectors**

21. **`src/plantgraph/graph/schema.py`** (285). `NodeClass` (20 DEXPI class names), `Relation` (9),
    `CLASS_SPECS`, the class sets, `RELATION_ENDPOINTS`, `VISIBLE_NODE_PROPERTIES` / `VISIBLE_EDGE_PROPERTIES`.
22. **`src/plantgraph/graph/validation.py`** (193). `validate_plant_graph`, `validate_sheet_graph`.
23. **`src/plantgraph/benchmark/connectors.py`** (181). `cut_remaining_edges` → `_cut_one_edge`;
    `_connector_kind` / `_connector_class`; `_stub_node_attrs` (the visible label).

**Generator: topology (no pyDEXPI)**

24. **`src/plantgraph/benchmark/generator_models.py`** (213). `GeneratorConfig`, `StreamKind`,
    `GenerationRecord`, `ValveSpec`, `LoopSpec`, the **`PlantBuilder` protocol**, and `PlantSummary` (the
    per-plant numbers EXP-0002 will regress on).
25. **`src/plantgraph/benchmark/generator.py`** (316). `plan_plant` first, then `_GenerationState` in §3.3's step
    order:
    1. `add_sections`
    2. `add_equipment`
    3. `add_intra_unit_streams` → `_add_tree` → `_maybe_add_recycle`
    4. `add_inter_unit_streams` → `_add_cross_unit_stream` → `_maybe_add_cross_link`
    5. `_add_stream` → `_add_valves`
    6. `add_control_loops`
    7. the id and tag counters

**Generator: pyDEXPI (the only package allowed to import pyDEXPI)**

26. **`pyproject.toml`**. Read the diff (`git diff HEAD~2 -- pyproject.toml` after committing, or before
    committing `git diff pyproject.toml`):
    - Python ≥ 3.12, and ruff and mypy targets 3.12;
    - `pydexpi==1.2.0`;
    - `.claude` excluded from ruff;
    - `UP042` ignored, with a comment on why (`StrEnum` would change what enum members print);
    - a mypy override limited to `pydexpi.*`.
    - `uv.lock` changed with it; no need to read that.
27. **`src/plantgraph/adapters/__init__.py`** (9). What the package is, and the import rule.
28. **`src/plantgraph/adapters/pydexpi_builder.py`** (287). `DexpiPlantBuilder`: how each topology decision
    becomes DEXPI objects (§3.5 table). Watch the dedicated sensing nozzle and the explicit ids, which make seeds
    reproducible. Then `GeneratedPlant` and `generate_plant`.
29. **`src/plantgraph/adapters/pydexpi_adapter.py`** (378). `LinearGraphLoader` (the fast loader), then
    `plant_graph` (pyDEXPI labels → our 4 relations, units folded onto nodes, valves' units derived) and
    `ConversionReport` (every dropped or folded edge counted).
30. **`src/plantgraph/adapters/pydexpi_io.py`** (62). JSON save/load (lossless) and the Proteus export
    (equipment-only in pyDEXPI 1.2.0, documented).
31. **`src/plantgraph/adapters/plant_summary.py`** (74). `summarize_plant`: counts per class, relation and stream
    kind.

**Comment pass**

32. **`src/plantgraph/__init__.py`, `benchmark/__init__.py`, `benchmark/open100/__init__.py`** (6–8 lines each).
    The only files the comment pass changed: short Hungarian module docstrings.

## Part 6 — Tests: the evidence (read after the code)

33. **`tests/test_splitter.py`** (169). The **round-trip invariant**: the main correctness argument for the
    benchmark.
34. **`tests/test_identity_groups.py`** (120). The tag-identity half the round-trip cannot see.
35. **`tests/graph_plant_builder.py`** (134). The test-only builder that writes the schema graph directly — the
    **oracle**.
36. **`tests/test_generator.py`** (272) and **`tests/test_generator_integration.py`** (82). Determinism, the
    global random state untouched, schema validity, connectedness, branching, the recycle / cross-link /
    control-loop rules, split round-trips on generated plants, and **invariant 8** (`flow_greedy` and
    `modularity` cut generated plants differently: the plant is not a chain).
37. **`tests/test_pydexpi_adapter.py`** (274). Read the **oracle-equality test** first,
    `test_plant_graph_matches_the_oracle_builder_on_their_shared_properties`: the real pyDEXPI pipeline gives
    exactly the oracle's graph for seeds 0–4. Then:
    - JSON bytes identical per seed;
    - no random uuids;
    - fast loader = pyDEXPI's loader;
    - nothing unmapped;
    - JSON round-trip;
    - canonical order;
    - the splitter round-trip on real DEXPI-generated plants for every strategy.
38. **`tests/test_pydexpi_builder.py`** (164). The sensing-nozzle rule, and streams with 0, 1 and 2 valves.
39. **Also new:**
    - `tests/test_pydexpi_io.py` (63);
    - `tests/test_plant_summary.py` (41);
    - `tests/test_generator_models.py` (50);
    - `tests/test_connectors.py` (81);
    - `tests/test_schema.py` (145);
    - `tests/test_strategies.py` (100; the `by_unit` tests are new).

    **Skim:** `tests/plant_fixtures.py` (92), `tests/test_splitter_models.py` (69).

## Part 7 — The comment pass

40. **`docs/private/50-progress/2026-09-13-comment-audit.md`** (116 lines). Read "Summary", "Changes applied" and
    "Test results after the pass".
    - **Result:** your `python-comments` skill found the 23 files already compliant; only three empty
      `__init__.py` files needed docstrings (item 32).
    - **Verification:** the coder compared the code structure before and after with docstrings removed; the main
      session confirmed exactly 3 of 23 files changed.

## Part 8 — Your answers, before the next coder run

**Done under the recommendations (tell me if you disagree):**
- **Python target raised to ≥ 3.12.** pyDEXPI 1.2.0 requires it; the environment already ran 3.13.1.
- **mypy override limited to `pydexpi.*`.** pyDEXPI ships no type marker.
- **`.claude` excluded from ruff.**
- **`UP042` ignored.**
- **pyDEXPI JSON is the lossless file**, and the Proteus export is labelled equipment-only.
- **ADR-0007 accepted with the builder route (H1)**, not pyDEXPI's own pattern sampler (H2).

**Still open:**
1. **OPEN100's DISCHARGE column:** map to `differentialPressure` (recommended) or `designPressureHead`? This
   blocks step 3b (equipment data).
2. **Your `python-comments` skill folder** (`.claude/skills/python-comments/`) is uncommitted. Commit it (third
   commit, optional) or keep it local?
