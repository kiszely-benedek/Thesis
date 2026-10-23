---
component: benchmark/generator + adapters/pydexpi + graph/schema
status: draft — revision 2 awaiting review
related: [ADR-0007 (proposed, approved by the user with amendments 2026-09-13), ADR-0004, ADR-0003, ADR-0002, splitter.md]
date: 2026-09-12
revised: 2026-09-13
---

# Design — plant generator and graph schema

Produces the large, directed, typed plant graphs that the `splitter` cuts into sheets, and fixes the graph
schema the generator emits and the graph store will hold. **Simple is a requirement** (user, 2026-09-12).

**Revision 2 (2026-09-13)** follows the user's amendments to ADR-0007: the generator outputs a real pyDEXPI
`DexpiModel`; the topology logic of revision 1 stays. **Frozen while a coder implements them, and not edited
in this revision:** §4.1–§4.5, §5, and §9 steps 1, 2, 4, 5. Where the pyDEXPI evidence touches them, §10 Q4
lists it; the frozen text is unchanged.

## 0. Recommendation

Build **H1**. Our seeded topology logic (§3.3) drives a thin pyDEXPI builder that constructs a `DexpiModel`
directly from pyDEXPI classes and toolkits. The model is the single source of truth; the splitter's
`DiGraph` is derived from it by pyDEXPI's own path (loader → `GraphAbstractor.build_conceptual_graph`) plus
our adapter (§3.6). Prototype, pyDEXPI 1.2.0, 2026-09-13: seed → `DiGraph` in **15.1 s at 1,000 units
(5,470 equipment)** once pyDEXPI's quadratic instance collection is replaced by a linear subclass whose
output is identical (§7).

Two pyDEXPI facts shape the design and are measured, not assumed:
- **Proteus XML export writes equipment and `MetaData` only.** The lossless persisted form is pyDEXPI JSON (§3.7).
- **pyDEXPI emits no prior-work relation names** (`send_to`, `control`, …). The adapter maps its edge labels onto them (§3.6).

---

## 1. What the methodology needs — simplicity tested against it

| # | Need | Why the methodology needs it | Mechanism in H1 |
|---|---|---|---|
| N1 | **Branching and cross-links** | On a chain, three of four split strategies cut almost alike (`pid-structural-rules.md` §6.1, §8 item 7 — *reasoned, not run*); a cross-sheet question reduces to walking consecutive sheets (*reasoning*). | Random recursive tree per `PlantSection`; recycle and cross-link probabilities |
| N2 | **Typed nodes and relations, tied to topology** | Prior work's questions are typed (ChatP&ID categories — `2603.22528.md`); its graphs carry class-name labels and typed relations (`2502.18928.md`). Types drawn independently of topology turn a typed question into a label lookup. | Equipment at stream ends, valves inline in piping segments, control loops sensing on equipment |
| N3 | **Directed edges** | `flow_greedy` walks downstream; "upstream of X" questions. All 762 PID2Graph graphs are undirected (ADR-0007 History). | Segment `sourceItem → targetItem`, signal `source → target` |
| N4 | **Reproducible seed** | `SplitManifest` promises "same seed ⇒ byte-identical manifest" (`splitter.md` §4). | One `random.Random(config.seed)`; **every DEXPI object gets an explicit id** (pyDEXPI defaults to `uuid4`) |
| N5 | **Scale as swept parameters** | The claim is a function of scale (professor: "hundreds or thousands" of sheets). No target number is sourced. | `n_units` × `equipment_per_unit_*`; sheets follow from the splitter's budget |
| N6 | **Declared hierarchy plant → unit** | Phase 3 is hierarchical retrieval; splitter finding 3 (`by_unit`, §5). | `ProcessPlant` → `PlantSection` → item via DEXPI `parentStructure` (unit = `PlantSection`, user 2026-09-13) |
| N7 | **Two kinds of cut, pipe and signal**, plus tag identity | EXP-0004 scores cross-sheet linking; `splitter.md` open question 3. | Control loops give signal relations; identity comes from the splitter |
| ~~N8~~ | ~~**Equipment data, visible and queryable**~~ **dropped 2026-09-20 (user); see 4.8 banner** | Questions such as "pumps with shaft power above X downstream of tank Y" combine topology with values, as real sheets print a data table under the drawing (OPEN100: SERVICE / CAPACITY / DISCHARGE / RPM / HP). | DEXPI data attributes on equipment, numeric in the graph (§4.8) |
| N9 | **A real DEXPI model** (user, 2026-09-13) | Prior work runs DEXPI → pyDEXPI → graph (`2502.18928.md`, `2603.22528.md`); a later rendering phase needs a model, not a bare graph. | `DexpiModel` built with pyDEXPI classes and toolkits |

**Excluded in this phase** (each is a later step or phase, not a permanent exclusion):
- **P&ID engineering rules** (L1–L20, C1–C11 in `pid-structural-rules.md`) — a later phase, built up gradually (ADR-0007 P2 as amended).
- **Utilities and headers** — a later generator step (§9 step 8).
- **Several plants per corpus** — next phase (§10 Q7).
- **Rendering to PDF** and reading PDFs back — later phase; the method's input stays per-sheet graphs (§11).
- **Line properties** (pressure class, diameter, insulation) — not needed by any planned question.
- **Calibration to any corpus** (ADR-0007).

Nozzles, pipes, segments and piping systems are now **built** (DEXPI needs them to connect equipment), but
pyDEXPI's conceptual abstraction removes them, as it does for ChatP&ID's 0.91 conceptual graph
(`2603.22528.md`). They never reach the `DiGraph`.

## 2. Options

| | **H1 — our topology builds the `DexpiModel` directly** | H2 — our patterns + custom `GeneratorFunction` in `SyntheticPIDGenerator` | H3 — revision 1's networkx generator + networkx → `DexpiModel` exporter |
|---|---|---|---|
| Source of truth | One: the `DexpiModel`; the `DiGraph` is derived | One: the `DexpiModel` | **Two** that can drift: the `DiGraph` feeds the benchmark, the model is a side export |
| Prior-work pipeline | DEXPI → pyDEXPI loader → conceptual graph → schema, as prior work | Same, and closest to pyDEXPI's own `syndata` | The benchmark never passes through DEXPI |
| Seeding | Own `random.Random`; explicit ids; global `random` untouched. **Measured:** identical pyDEXPI JSON bytes and identical sorted `DiGraph` under `PYTHONHASHSEED` 1, 2, 3 | **Blocked twice.** `PatternDistribution.sample_pattern` calls global `choices` (`syndata/pattern_distribution.py` lines 158–170), so save/restore of global state is unavoidable. Every sampled pattern is `copy.deepcopy`-ed (`syndata/pattern.py` lines 504–537), and `DexpiBaseModel.__deepcopy__` assigns a fresh `uuid4` id to every object (**measured**: a deep-copied `Tank(id="fixed-id")` came back with a uuid). Ids would need relabelling after generation. | Fine (revision 1 design) |
| Fit to our topology | Direct: the five steps of §3.3 become builder calls | Indirect: `DexpiPattern` accepts only `BasicPipingIn/OutConnector` (`syndata/dexpi_pattern.py` lines 253–262), so control loops would be added after generation anyway; tree parents and cross-unit links need multi-outlet patterns (*reasoned from code, not prototyped*) | Direct |
| Effort, one Sonnet coder | Builder with four public methods + adapter | Pattern library as DEXPI object models, custom generator and capping functions, global-random wrapper, id relabelling, loop post-pass | Revision 1 generator **plus** an exporter that is H1's builder fed from a graph, plus an equivalence test |
| Speed at scale | **Measured**: 15.1 s at 1,000 units with the linear loader; 140.4 s at 250 units with the stock `GraphLoader` (§7) | Not measured | Benchmark path not measured; export as H1's builder |
| Proteus XML | Equipment-only in pyDEXPI 1.2.0 (all options alike) | Same | Same |

**Recommendation: H1.** H2 fails N4 at the root (uuid ids on every copy) and bends N1/N7 around a
piping-only connector model. H3 keeps two representations that must be proved equal forever. H1 costs a
builder and an adapter, and the adapter is needed anyway for EXP-0001 on `DEXPIEX01.xml` (§6).

**Kill criterion (fall back to H3 for the benchmark path; the `DexpiModel` is still built and checked for
equivalence on small plants):**
- (a) seed → `DiGraph` exceeds **10 minutes** wall-clock, or runs out of memory, for the largest plant the
  EXP-0002 sweep needs, as measured by `scale_smoke` (§9 step 7); or
- (b) invariant 11 (linear loader ≡ `GraphLoader`) or 12 (no unmapped topology edge) cannot be made to pass
  on the pinned pyDEXPI within one coder step.

Current evidence against (a): 15.1 s at 1,000 units.

---

## 3. Generator design

### 3.1 Files

```
src/plantgraph/graph/schema.py                  # §4 definitions (step 1 done; + equipment data constants, step 3b)
src/plantgraph/graph/validation.py              # validate_plant_graph, validate_sheet_graph (step 1 done)
src/plantgraph/benchmark/generator_models.py    # GeneratorConfig, StreamKind, GenerationRecord, PlantSummary
src/plantgraph/benchmark/generator.py           # topology decisions (§3.3); imports no pydexpi
src/plantgraph/benchmark/equipment_data.py      # step 3b: declared ranges → plain (value, unit) pairs
src/plantgraph/adapters/__init__.py
src/plantgraph/adapters/pydexpi_builder.py      # DexpiPlantBuilder, GeneratedPlant (§3.5)
src/plantgraph/adapters/pydexpi_adapter.py      # LinearGraphLoader, plant_graph(), ConversionReport, save/load (§3.6, §3.7)
tests/test_generator.py
tests/test_pydexpi_builder.py
tests/test_pydexpi_adapter.py
```

**Import rule (ADR-0003, "isolate pyDEXPI usage behind a thin internal adapter module").** Only
`src/plantgraph/adapters/pydexpi_*.py` import `pydexpi`. `generator.py` passes strings, ints and floats to
`DexpiPlantBuilder`; `schema.py` imports nothing from `plantgraph.benchmark` or `plantgraph.adapters`.

**Existing layout (coder, steps 1, 2, 4, 5):** `graph/schema.py` + `graph/validation.py`;
`benchmark/models.py` (361 lines: `OffPageConnector`, `ConnectorKind`, `SplitManifest`),
`benchmark/split_models.py` (`SplitConfig`, `NumberingScheme`, `ConnectorLabelDetail`),
`benchmark/connectors.py` (cut and stub logic), `benchmark/sheet_graph.py` (`SheetGraph`). The generator's
models go into a new `generator_models.py` so `models.py` stays under the 400-line cap.

> **Offline split of step 3 (main session, 2026-09-13).** PyPI was unreachable on 2026-09-13, and
> `uv add --offline pydexpi==1.2.0` fails because the universal lock needs registry metadata that is not cached.
> Step 3 is therefore split in two, without changing the algorithm or the single source of truth:
> - **3-topology (now, no new dependency).** `ValveSpec`, `LoopSpec`, `DataValue` and a `PlantBuilder`
>   `typing.Protocol` live in `benchmark/generator_models.py`, next to `GeneratorConfig`, `StreamKind` and
>   `GenerationRecord`. The protocol has §3.5's `add_section`, `add_equipment`, `add_stream`, `add_control_loop`
>   and a read-only `backend_version: str`; `build()` is backend-specific and not part of it.
>   `benchmark/generator.py` exposes `plan_plant(config, builder: PlantBuilder) -> GenerationRecord`, which
>   performs §3.3 steps 0–5 (with `equipment_data` ignored until step 3b) and imports nothing from `adapters`.
>   Tests drive it with a test-only `GraphPlantBuilder` (`tests/graph_plant_builder.py`) that writes the schema
>   `DiGraph` the adapter is meant to produce.
> - **3-pyDEXPI (when online).** `adapters/pydexpi_builder.py` implements `PlantBuilder` and provides
>   `generate_plant(config) -> GeneratedPlant`, i.e. `DexpiPlantBuilder` + `plan_plant` + `build()`. The Python
>   target raise and the `pydexpi==1.2.0` dependency land here. pyDEXPI ships no `py.typed` marker (checked
>   2026-09-13), so this step needs a mypy override limited to `pydexpi.*`.
> - **New invariant for step 3a.** For seeds 0–4, `plant_graph(generate_plant(cfg))[0]` equals the
>   `GraphPlantBuilder` graph for the same config, on the node and edge properties both carry. The test-only
>   builder is an oracle, not a second production path.

### 3.2 Input and output

```python
# benchmark/generator.py
def generate_plant(config: GeneratorConfig) -> GeneratedPlant: ...

# adapters/pydexpi_adapter.py
def plant_graph(generated: GeneratedPlant) -> tuple[nx.DiGraph[str], ConversionReport]: ...
def summarize_plant(plant: nx.DiGraph[str]) -> PlantSummary: ...
```

`GeneratedPlant` (frozen dataclass in `pydexpi_builder.py`): `model: DexpiModel`, `record: GenerationRecord`.

`GeneratorConfig` (Pydantic, `generator_models.py`). **All defaults are arbitrary and test-sized. None is a claim about
real plants.** Fields as in revision 1, plus one:

| Field | Type, default | Meaning |
|---|---|---|
| `plant_id` | `str = "plant0"`, pattern `^[a-z0-9]+$` | goes into ids, so no `-` or `:` |
| `seed` | `int = 0` | |
| `n_units` | `int = 4`, `ge=1` | number of `PlantSection`s |
| `equipment_per_unit_min` / `_max` | `int = 3` / `8`, `ge=1`, validator `min <= max` | equipment per unit, uniform |
| `p_recycle` | `float = 0.2`, `[0, 1]` | per unit: chance of one recycle stream |
| `p_cross_link` | `float = 0.2`, `[0, 1]` | per unit `u >= 1`: chance of one extra stream from an earlier unit |
| `valves_per_stream_max` | `int = 2`, `ge=0` | inline valves per stream, uniform `0..max` |
| `p_control_loop` | `float = 0.5`, `[0, 1]` | per equipment |
| `equipment_weights` | `dict[str, float]`, weight `1.0` for each of `schema.EQUIPMENT_CLASSES` | validator: keys ⊆ `EQUIPMENT_CLASSES`, weights `> 0` |
| `fluid_codes` | `list[str] = ["PL", "PG"]`, `min_length=1` | per stream |
| `equipment_data` | `bool = True` (**new, step 3b**) | draw §4.8 values |

`GenerationRecord` (Pydantic, `generator_models.py`) — **gold, never loaded into the store under test:**
`plant_id`, `seed`, `generator_config: str` (JSON), `pydexpi_version: str`,
`stream_kind: dict[str, StreamKind]` keyed by line number. `StreamKind(str, Enum)`: `tree`, `recycle`,
`cross_unit`, `cross_link`.

`PlantSummary` is unchanged from revision 1: `n_nodes`, `n_edges`, `nodes_per_class`, `edges_per_relation`,
`n_units`, `n_equipment`, `n_streams`, `streams_per_kind`, `n_control_loops`,
`max_streams_out_of_one_equipment`. It is computed on the derived `DiGraph` and written beside every instance
as EXP-0002's regression variables (ADR-0007 Decision 3).

### 3.3 Algorithm

All topology randomness goes through `rng = random.Random(config.seed)`. Equipment data (step 3b) uses a
second, independent `data_rng = random.Random(f"{config.seed}:equipment-data")`, so switching data on or off
never changes the topology. Iterate in index or sorted order only, never over a `set`. The draw order below
is the specification; the builder calls are §3.5.

0. **Plant and units.** `builder = DexpiPlantBuilder(plant_id)`; for `u` in `0..n_units-1`,
   `builder.add_section(unit_no=u + 1)`.
1. **Equipment.** For each unit, draw `k = rng.randint(min, max)`, then `k` classes with
   `rng.choices(sorted(equipment_weights), weights)[0]`. For each, `builder.add_equipment(...)` with the id
   and tag rules below and, from step 3b, `equipment_data.draw(data_rng, node_class)`.
2. **Streams inside a unit** (random recursive tree). For `e` in `1..k-1`, `parent = rng.randrange(e)`,
   `add_stream(eq[parent], eq[e], "tree")`. **Recycle:** with probability `p_recycle`, collect pairs
   `(src, dst)` with `1 <= dst < src`, `dst` not the tree parent of `src`, no stream between them in either
   direction; if any, `add_stream(*rng.choice(pairs), "recycle")`.
3. **Streams between units.** For `u` in `1..n_units-1`: `up = rng.randrange(u)`,
   `add_stream(rng.choice(eq[up]), eq[u][0], "cross_unit")`. **Cross-link:** with probability `p_cross_link`,
   if unit `u` has more than one equipment: `i = rng.randrange(u)`, `src = rng.choice(eq[i])`,
   `dst = rng.choice(eq[u][1:])`; if no stream `src → dst` exists, `add_stream(src, dst, "cross_link")`.
4. **`add_stream(src, dst, kind)`.** `fluid = rng.choice(fluid_codes)`; line number `f"{fluid}-{stream_seq}"`
   (plant-wide counter from 1); `n = rng.randint(0, valves_per_stream_max)` valves, each class
   `rng.choice(sorted(VALVE_CLASSES))`, owned by the **source's unit**. Call
   `builder.add_stream(line_number, fluid, src_id, dst_id, valves)` and record `kind` in
   `GenerationRecord.stream_kind`. A second stream on an existing ordered pair **raises**.
5. **Control loops.** For each equipment in node-id order, with probability `p_control_loop`: candidates are
   `GlobeValve` or `BallValve` on this equipment's outgoing streams, not yet controlled; if none, skip; else
   `valve = rng.choice(candidates)`, `var = rng.choice("FLPT")`, loop counter `s` per unit, and
   `builder.add_control_loop(...)`.

**Ids and tags** (unchanged from revision 1; the DEXPI `id` of a topology object **is** its node id):
- Node id: `f"{plant_id}-u{unit_no}-{kind}{seq}"`, `kind` ∈ `eq`, `va`, `in`.
- Equipment and valve tag: `f"{prefix}-{unit_no}-{seq}"`, `prefix` from `schema.CLASS_SPECS`, `seq` per (unit, prefix).
- Instrument tags: `f"{var}T-{unit_no}-{s}"`, `f"{var}IC-{unit_no}-{s}"`, `f"{var}V-{unit_no}-{s}"`.
  *(If ADR-0044 is accepted: `{var}V-…` moves from the actuator to the operated valve, and the actuator has no tag.
  See `control-valve-tagging.md`.)*

### 3.4 Invariants (each is a test)

Invariants 1–8 keep their revision-1 meaning; "the output" is `plant_graph(generate_plant(cfg))[0]`.

1. The output is `nx.DiGraph`, has no self-loops, and generation never raises on seeds 0–19 with default config.
2. `validation.validate_plant_graph(plant) == []`.
3. The same seed gives equal `sorted(nodes(data=True))` and `sorted(edges(data=True))`; seeds 0 and 1 differ.
4. `random.getstate()` is identical before and after `generate_plant` and `plant_graph`.
5. The plant is weakly connected. Unit 1's first equipment has in-degree 0.
6. Across seeds 0–19 with default config, at least one equipment has two or more outgoing streams (N1).
7. Integration: for every registered strategy, `rejoin(*split(plant, split_cfg))` reproduces the plant.
8. **The strategies differ.** With `sheet_equipment_budget=2`, `flow_greedy` and `modularity` produce different
   partitions on at least one of seeds 0–4. **If this fails, stop and report it; do not tune the generator.**
9. Same seed ⇒ identical `JsonSerializer().export_to_bytes(model)`; seeds 0 and 1 differ.
10. No DEXPI object in the model has a uuid-shaped id (every id is explicit).
11. `LinearGraphLoader().dexpi_to_graph(m)` equals `GraphLoader().dexpi_to_graph(m)` — nodes with attributes,
    edges with keys and attributes, and node order — on seeds 0–4 with `n_units=5`.
12. `ConversionReport`: zero unmapped edges between topology nodes; every valve's unit resolved.
13. JSON save → load → `plant_graph` gives the same sorted nodes and edges as the in-memory model.
14. `list(plant.nodes) == sorted(plant.nodes)` and `list(plant.edges) == sorted(plant.edges)` (insertion order
    is canonical; the prototype showed pyDEXPI's abstraction varies it across processes).

### 3.5 DEXPI construction (`adapters/pydexpi_builder.py`)

```python
class DexpiPlantBuilder:
    def __init__(self, plant_id: str) -> None: ...
    def add_section(self, unit_no: int) -> None: ...
    def add_equipment(self, node_id: str, node_class: str, unit_no: int, tag: str,
                      tag_prefix: str, tag_seq: int, data: Mapping[str, DataValue]) -> None: ...
    def add_stream(self, line_number: str, fluid_code: str, src_id: str, dst_id: str,
                   valves: Sequence[ValveSpec]) -> None: ...
    def add_control_loop(self, loop: LoopSpec) -> None: ...
    def build(self) -> DexpiModel: ...
```

`ValveSpec` (`node_id`, `node_class`, `tag`) and `LoopSpec` (`equipment_id`, `valve_id`, `variable`,
`unit_no`, `loop_no`, `psgf_id`, `pif_id`, `af_id`) are frozen Pydantic models. `DataValue` is
`str | tuple[float, str]` (text, or value with unit symbol).

| Topology concept | DEXPI objects (pyDEXPI 1.2.0 classes; all verified in the prototype) | Id |
|---|---|---|
| plant | `ProcessPlant(processPlantIdentificationCode=plant_id)` in `conceptualModel.plantStructureItems`; `MetaData(drawingNumber=plant_id)` | `{plant_id}-plant` |
| unit | `PlantSection(plantSectionIdentificationCode=str(unit_no), plantSectionName, parentStructure=plant)` in `plantStructureItems` | `{plant_id}-u{unit_no}` |
| equipment | its class with `tagName`, `tagNamePrefix`, `tagNameSequenceNumber`, `parentStructure=section`, data (§4.8), in `taggedPlantItems` | node id |
| stream end | a new `Nozzle(subTagName=f"N{k}")` on the equipment, one per stream end | `{node_id}-nz{k}` |
| stream | `PipingNetworkSystem(lineNumber, fluidCode, parentStructure=source section)` with one `PipingNetworkSegment(fluidCode)` from `piping_toolkit.construct_new_segment(valves, pipes, source nozzle, target nozzle, connectivity_convention=USE_ITEMS)`; `len(pipes) = len(valves) + 1` `Pipe`s | `{plant_id}-L{seq}-ps`, `-sg`, `-pp{i}` |
| inline valve | `GlobeValve` / `BallValve` / `CheckValve(pipingComponentNumber=tag, fluidCode)` | node id |
| control loop | `ProcessSignalGeneratingFunction(processSignalGeneratingFunctionNumber, sensingLocation=<dedicated Nozzle>, parentStructure)`; `ProcessInstrumentationFunction(processInstrumentationFunctionCategory=var, processInstrumentationFunctionModifier="IC", processInstrumentationFunctionNumber=f"{unit_no}-{s}", parentStructure)`; `ActuatingFunction(actuatingFunctionNumber, parentStructure)`; `instrumentation_toolkit.add_signal_generating_function_to_instrumentation_function(pif, psgf, MeasuringLineFunction)`; `add_actuating_function_to_instrumentation_function(pif, af, SignalLineFunction)`; `af.systems = ActuatingSystem(operatedValveReference=OperatedValveReference(valve=…))`; `InstrumentationLoopFunction(processInstrumentationFunctions=[pif])` | node ids; `{pif_id}-ml`, `-sl`, `-as`, `-ov`, `-lp`, `{equipment_id}-nz{k}` |
| model | `DexpiModel(conceptualModel, exportDateTime=datetime(2026, 1, 1), originatingSystemName="plantgraph", originatingSystemVendorName="plantgraph", originatingSystemVersion=<package version>)` | `{plant_id}-model` |

**Two construction rules the evidence forced:**
- **The sensing location is a dedicated nozzle.** DEXPI does not allow equipment as a `SensingLocation`
  (its subclasses are `Nozzle`, `PipingComponent`, `PipingNetworkSegment` — checked in the prototype).
  pyDEXPI's abstraction stitches a nozzle away only when it has exactly two edges
  (`loaders/graph_loader.py` lines 741–748). **Measured:** with the sensing reference on the piped nozzle,
  the conceptual graph lost both the pipe `tank → valve` and the sensing edge; with a dedicated nozzle both
  survive.
- **Fixed export metadata.** `exportDateTime` is a constant so exports are byte-identical, and the Proteus
  serializer runs with `override_export_info=False`, because `True` opens `pyproject.toml` from the current
  working directory (`proteus_exporter/exporter_modules.py`, `PlantModelExporter._make_plant_information`).

### 3.6 Adapter: model → schema `DiGraph` (`adapters/pydexpi_adapter.py`)

Three stages; the first two are pyDEXPI's own path, which is what makes the result comparable with prior work.

1. **`LinearGraphLoader(GraphLoader)`** overrides `parse_dexpi_to_graph` only: it collects instances by DFS
   pre-order with an identity set, then calls pyDEXPI's own `_add_nodes` and `_add_edges`. Reason: the stock
   `mt.get_all_instances_in_model` deduplicates with `obj not in list` (`toolkits/model_toolkit.py`
   lines 127–160), which is quadratic in pydantic `__eq__` calls. **Measured** equal to `GraphLoader` (nodes,
   attributes, edges, keys, node order) at 5 and 50 units. Private methods of a pinned version; invariant 11
   guards it.
2. **`GraphAbstractor.build_conceptual_graph(complete)`**, unchanged.
3. **Mapping to §4**, inserting nodes and edges in sorted order (invariant 14):

| pyDEXPI conceptual edge (`label` / `attr_name`), as observed | Schema | Properties |
|---|---|---|
| `Pipe`, `DirectPipingConnection` | `send_to`, same direction | `line_number` ← `lineNumber`, `fluid_code` ← `fluidCode` (inherited from system and segment); `stream_kind` ← `GenerationRecord` (G) |
| `MeasuringLineFunction`, `SignalLineFunction`, `SignalConveyingFunction` | `send_signal_to`, same direction | — |
| `OperatedValveReference` (AF → valve) | `control` | — |
| `reference` / `sensingLocation` (PSGF → equipment, after nozzle stitching) | `measured_by`, **reversed** | — |
| `reference` / `parentStructure` (item → `PlantSection`) | not an edge: folded into `unit_id` | — |
| anything else | dropped and counted | — |

Observed edge labels on the prototype and on the public DEXPI example `C01V04-VER.EX01.xml` (conceptual
graph: 36 nodes, 39 edges): exactly the first four rows plus `parentStructure` on the prototype.

Node rules:
- `node_class` = pyDEXPI `label` if in `schema.NodeClass`, else nearest ancestor (§6); otherwise dropped and counted.
- `tag`: equipment `tagName`; valves `pipingComponentNumber`; PSGF `processSignalGeneratingFunctionNumber`;
  AF `actuatingFunctionNumber`; PIF `f"{category}{modifier}-{number}"` (DEXPI has no single PIF tag).
- `unit_id` = `plantSectionIdentificationCode` of the `parentStructure` target; `plant_id` from the section's
  `ProcessPlant`. **Valves have no `parentStructure`** (`PipingComponent` is not a `TechnicalItem`), and the
  system's link is dropped by the abstraction; a valve takes the `unit_id` of the equipment reached by walking
  `send_to` upstream through valves — exactly the generator's "owned by the source's unit" rule.
- `loop_tag` = the PIF's tag, on the PIF and its PSGF and AF neighbours; `measured_variable` =
  `processInstrumentationFunctionCategory`.
- Equipment data (§4.8) is read **from the DEXPI objects by id**, not parsed from `GraphLoader`'s strings.
- Parallel-edge and class-mapping policies: §6.

`ConversionReport` (Pydantic): `nodes_mapped`, `nodes_dropped_per_class`, `edges_mapped_per_relation`,
`edges_dropped_per_label`, `parent_structure_folded`, `valve_units_unresolved`, `parallel_edges_collapsed`.

### 3.7 Persisted artefacts

| File | Content | Gold? | Written when |
|---|---|---|---|
| `generation_record.json` | seed, config, pyDEXPI version, `stream_kind` | G | always — with the pinned version it regenerates the model |
| `plant_summary.json` | `PlantSummary` | analysis | always |
| `plant.dexpi.json` | pyDEXPI `JsonSerializer`, **lossless** (prototype: conceptual edges equal after reload) | source | published instances and on request; 83.6 MB at 1,000 units (§7) |
| `plant.equipment.proteus.xml` | `ProteusSerializer` — **equipment and `MetaData` only** in pyDEXPI 1.2.0 | source | on request; the name says what it is not |

**Proteus export, measured:** the tiny model exported 3 `Equipment` elements plus `PlantInformation` and
`MetaData`. Reloaded, it gave a conceptual graph of 3 nodes and 0 edges, with the pump's data attributes intact.
`PlantModelExporter.__init__` iterates `conceptualModel.taggedPlantItems` only
(`proteus_exporter/exporter_modules.py`). The GitHub `master` file shows the same (fetched 2026-09-13).
The Proteus **parser**, however, reads piping and instrumentation (`proteus_parser/parser_factory.py` lines
71–118; the public example loaded to 214 nodes). See §10 Q2.

---

## 4. Graph schema

The user asked whether an ontology is still needed (2026-09-12). **For the query side, yes.** Retrieval
at scale needs node types, properties and connections. It is **not "a P&ID ontology"**. It is pyDEXPI
class names plus the ~10-term multi-sheet extension recommended in `ontology-landscape.md` §5 R3.

> **Post-implementation notes (main session, 2026-09-13).** §4.1–§4.5 were implemented as written (§9 steps 1, 2,
> 4, 5; 84 tests green). Four notes, none of which changes the text below:
> 1. **Files.** §4.5's single `schema.py` is `graph/schema.py` (definitions) plus `graph/validation.py`
>    (`SchemaViolation`, `validate_plant_graph`, `validate_sheet_graph`), split for the 400-line cap.
> 2. **Relation names.** pyDEXPI 1.2.0 emits none of `send_to`, `send_signal_to`, `control`, `measured_by`; the
>    adapter (§3.6) maps its labels onto them. DEXPI allows a `Nozzle` as sensing location, so `measured_by` from
>    equipment follows from §3.5's dedicated-nozzle rule rather than being a simplification.
> 3. **`unit_id` on valves** is derived by the adapter from the upstream equipment; DEXPI declares no parent for valves.
> 4. **`VISIBLE_NODE_PROPERTIES`** does not yet list the §4.8 equipment data properties. Step 3b adds them; until
>    then a loader enforcing it would strip equipment data.

### 4.1 Two layers

- **Topology layer.** What the generator emits and the splitter cuts: lexical relations only, as
  networkx edges with a required `relation` attribute.
- **Structure layer.** Containment, sheets and cross-sheet resolution. The loader materializes it into
  Neo4j from node attributes and the `SplitManifest`. **It is never an edge in the splitter's input.**
  Reason, from the code: `_cluster_owners` runs a BFS over `plant.to_undirected()`. A unit node linked to
  all its items would make every item two hops from every other. `_cut_remaining_edges` would then turn
  containment edges into off-page connectors.

This is the domain/lexical split of `2502.18928.md`, placed where the splitter can live with it.

### 4.2 Node classes

Class names verified in installed pyDEXPI 1.2.0 `dexpi_classes/pydantic_classes.py`. The labels are a
**curated** ancestor chain. pyDEXPI's `get_inheritance_from_dexpi_class` also returns mixins such as
`CustomAttributeOwner`, `NozzleOwner` and `TechnicalItem` (`toolkits/base_model_utils.py` lines 286–316),
and those are dropped. The kept names are identical strings, so `MATCH (n:Equipment)` means the same on a
generated graph and on a pyDEXPI-loaded `DEXPIEX01.xml`.

| `node_class` | Neo4j labels | Category | Tag prefix | Emitted by |
|---|---|---|---|---|
| `CentrifugalPump` | `CentrifugalPump:Pump:Equipment:TaggedPlantItem` | equipment | `P` | generator |
| `Compressor` | `Compressor:Equipment:TaggedPlantItem` | equipment | `C` | generator |
| `Tank` | `Tank:Vessel:Equipment:TaggedPlantItem` | equipment | `TK` | generator |
| `PressureVessel` | `PressureVessel:Vessel:Equipment:TaggedPlantItem` | equipment | `V` | generator |
| `ProcessColumn` | `ProcessColumn:Equipment:TaggedPlantItem` | equipment | `T` | generator |
| `HeatExchanger` | `HeatExchanger:Equipment:TaggedPlantItem` | equipment | `E` | generator |
| `GlobeValve` | `GlobeValve:OperatedValve:PipingComponent` | piping | `GV` | generator |
| `BallValve` | `BallValve:OperatedValve:PipingComponent` | piping | `BV` | generator |
| `CheckValve` | `CheckValve:PipingComponent` | piping | `CHV` | generator |
| `ProcessSignalGeneratingFunction` | same | instrumentation | `{var}T` | generator |
| `ProcessInstrumentationFunction` | same | instrumentation | `{var}IC` | generator |
| `ActuatingFunction` | same | instrumentation | `{var}V` | generator |
| `FlowOutPipeOffPageConnector` / `FlowInPipeOffPageConnector` | `…:PipeOffPageConnector` | connector | — | splitter |
| `FlowOutSignalOffPageConnector` / `FlowInSignalOffPageConnector` | `…:SignalOffPageConnector` | connector | — | splitter |
| `ProcessPlant` | `ProcessPlant` | structure | — | loader |
| `PlantSection` | `PlantSection` (**the "unit"**) | structure | — | loader |
| `DrawingSet` | `DrawingSet` (extension) | structure | — | loader |
| `Sheet` | `Sheet` (extension) | structure | — | loader |

The topology layer therefore has 16 classes: 12 emitted by the generator and 4 connector classes emitted by
the splitter. The four structure classes exist only in the store. Equipment classes count against the sheet
budget.

**Why `PlantSection` for "unit".** DEXPI 1.3 has no `Unit` class; `unitName` exists only on `MetaData`
(lines 1609–1612). `PlantSection` is declared a `TechnicalItemParentStructure` and `ProcessPlant` a
`PlantSectionParentStructure` (class bases, lines 1645, 3494), so DEXPI supports plant → section → item
natively. `PlantSystem`, OPEN100's convention, is only a `PlantStructureItem`. See open question 2.

**Connector direction** follows DEXPI's own typing. `FlowInPipeOffPageConnector` is a `PipingSourceItem`
and `FlowOutPipeOffPageConnector` a `PipingTargetItem` (lines 4273, 4279). Likewise
`FlowInSignalOffPageConnector` is a `SignalConveyingFunctionSource` and `FlowOutSignalOffPageConnector` a
`…Target` (lines 4513, 4519). So the splitter's outgoing stub is `FlowOut…` and its incoming stub is
`FlowIn…`.

### 4.3 Relations

**Topology layer** — networkx edges with a `relation` attribute:

| `relation` | From → to | DEXPI origin (collapsed, as pyDEXPI's conceptual graph collapses it) | Edge properties |
|---|---|---|---|
| `send_to` | equipment, piping, `FlowInPipe…` → equipment, piping, `FlowOutPipe…` | `PipingNetworkSegment.sourceItem → targetItem` (lines 2330–2338) | `line_number`, `fluid_code`, `stream_kind` |
| `send_signal_to` | PSGF, PIF, `FlowInSignal…` → PIF, AF, `FlowOutSignal…` | `SignalConveyingFunction.source → target` (lines 2794–2799) | — |
| `control` | AF, `FlowInSignal…` → `GlobeValve`, `BallValve`, `FlowOutSignal…` | `ActuatingFunction.systems → ActuatingSystem.operatedValveReference → OperatedValveReference.valve` (lines 2540, 2557, 2643) | — |
| `measured_by` | equipment, `FlowInSignal…` → PSGF, `FlowOutSignal…` | `ProcessSignalGeneratingFunction.sensingLocation` (line 2745), reversed. DEXPI's sensing location is a segment or component; equipment here is a conceptual-level simplification. | — |

The relation names are the prior work's own strings (`2502.18928.md`: lexical `send_to`, `control`,
`send_signal_to`, `measured_by`). Their **directions** are this design's reading of the names; the paper
notes record names, not directions.

**Not emitted: DEXPI's `has_*` compositions** (nozzles, segments, actuating systems, loop membership). There
are two reasons:
- They sit below the conceptual level.
- `ProcessInstrumentationFunction.actuatingFunctions` (composition, line 2679) would be a second edge on the
  same ordered pair PIF → AF as `send_signal_to`, and a `DiGraph` silently keeps one.

Loop membership is the property `loop_tag` instead.

**Structure layer** — loader-materialized. These form the multi-sheet extension, `ontology-landscape.md` §5 R3:

| Term | Kind | From → to / on | Source |
|---|---|---|---|
| `is_located_in` | relation | item occurrence → `PlantSection`; `PlantSection` → `ProcessPlant` | prior-work domain relation (`2502.18928.md`); from `unit_id`, `plant_id` |
| `DrawingSet` | class | container of a corpus | R3.1 |
| `Sheet` | class | one drawing sheet | R3.1 |
| `has_sheet` | relation | `DrawingSet` → `Sheet` | R3.1 |
| `is_drawn_on` | relation | occurrence → `Sheet` | R3.1 |
| `continues_as` | relation | `FlowOut…Connector` → `FlowIn…Connector` | R3.2 `continuesAs` |
| `same_tagged_item_as` | relation | reference occurrence → home occurrence | R3.3 `sameTaggedItemAs` / `IdentityGroup` |
| `asserted_by` | property on the two above | `oracle` \| `resolver` | R3.4 provenance |
| `match_rule` | property on `continues_as` | existing `MatchRule` enum | R3.4 |
| `verified_by_human` | property on the two above | bool (OPEN100) | R3.4 |

**Oracle and resolver are an experimental factor, not a detail.** In an evaluation run the store holds
`continues_as` and `same_tagged_item_as` edges from exactly one source:
- `asserted_by=oracle`, copied from the manifest, isolates retrieval from resolution (EXP-0002);
- `asserted_by=resolver` measures the full pipeline (EXP-0004).

They are never mixed in one run.

### 4.4 Properties and visibility

**V** means visible to retrieval and to the resolver. **G** means gold only: it is kept in the manifest or a
separate database, never in the store under test. The loader enforces this from
`schema.VISIBLE_NODE_PROPERTIES` and `VISIBLE_EDGE_PROPERTIES`.

| Property | On | Required | V/G | Note |
|---|---|---|---|---|
| `node_id` | topology nodes | yes | **G** | The splitter draws identity references under the **same** `node_id` on other sheets (`splitter.py` `_draw_on_neighbour_sheets`). Exposing it leaks the tag-identity gold set. |
| `node_class` | all | yes | V (as labels) | |
| `tag` | topology nodes | yes | V | |
| `plant_id`, `unit_id` | generator nodes | yes in plant graphs | V | Title blocks name the system, and tags already encode the unit |
| `loop_tag`, `measured_variable` | instrumentation | yes | V | |
| `connector_number`, `referenced_drawing_number` | connectors | yes | V | DEXPI `referencedDrawingNumber` (line 2228), flattened onto the connector |
| `referenced_connector_number` | connectors | only with `FULL` label detail (§5) | V | DEXPI `referencedConnectorNumber` |
| `line_number`, `fluid_code` | `send_to` edges, pipe connectors | yes on `send_to` | V | |
| `stream_kind` | `send_to` edges | yes | **G** | `tree` \| `recycle` \| `cross_unit` \| `cross_link`; for analysis only |
| `relation` | all edges | yes | V (relationship type) | |
| occurrence id | store nodes | yes | V | **opaque**: `sha1(f"{sheet_id}:{node_id}")`, first 12 hex digits; the mapping stays in gold |

### 4.5 `src/plantgraph/graph/schema.py` contents

- `NodeClass(str, Enum)`, `NodeCategory(str, Enum)` and `Relation(str, Enum)` hold the values in the tables above.
- `ClassSpec` is a frozen Pydantic model with `labels: tuple[str, ...]`, `category: NodeCategory` and
  `tag_prefix: str | None`. It backs `CLASS_SPECS: dict[NodeClass, ClassSpec]`.
- The class-set constants are:
  - `EQUIPMENT_CLASSES`, `VALVE_CLASSES`, `OPERATED_VALVE_CLASSES` and `CONNECTOR_CLASSES`, each a
    `frozenset[str]`;
  - `TOPOLOGY_RELATIONS: frozenset[Relation]`.
- `RELATION_ENDPOINTS: dict[Relation, tuple[frozenset[str], frozenset[str]]]` holds the from/to sets in §4.3,
  connector classes included.
- `VISIBLE_NODE_PROPERTIES` and `VISIBLE_EDGE_PROPERTIES` are `frozenset[str]` constants.
- `labels_for(node_class: str) -> tuple[str, ...]`.
- `SchemaViolation` is a Pydantic model with `kind`, `subject` and `detail`. `kind` is one of
  `unknown_class`, `missing_property`, `unknown_relation`, `bad_endpoint`, `duplicate_tag`.
- `validate_plant_graph(g) -> list[SchemaViolation]` checks generator output. Every node needs a known
  topology class, `tag`, `plant_id` and `unit_id`; there are no connector nodes; tags are unique
  plant-wide; edges must pass the relation and endpoint checks.
- `validate_sheet_graph(g) -> list[SchemaViolation]` checks splitter output. Connector nodes are allowed and
  need their own required properties. Other nodes need only `node_class` and `tag`, because identity
  references carry "tag and little else". Tags must be unique per sheet.

### 4.6 Store mapping (ADR-0002: LPG primary)

- A node becomes a Neo4j node with `labels_for(node_class)` and its V properties.
- An edge becomes a relationship whose type is the `relation` string **verbatim, lowercase**. That breaks
  Neo4j's UPPER_SNAKE convention on purpose, to keep prior-work strings identical.
- The structure layer (§4.3) is created by the loader, which gets its own design note (`graph/loader`).

### 4.7 What the RDF mapping will need (not designed here)

- An IRI scheme for occurrences, sheets, sections and plants (ADR-0002: global IRIs are the point).
- Class IRIs generated from the pyDEXPI names in §4.2, aligned to PCA RDL IRIs where the pyDEXPI docstring
  cites one. Example: `HeatExchanger` → `data.15926.org/rdl/RDS304199`, from `ontology-landscape.md` §1.3.
  They must be vendored locally, because the live RDL returns HTTP 401 (§5 R5).
- Object properties for the 4 topology and 5 structure relations; datatype properties for the V columns.
- `same_tagged_item_as` versus `owl:sameAs`. R3.3 recommends our own property.
- A pattern for per-assertion provenance (`asserted_by`, `match_rule`): RDF-star, named graphs or
  reification. This decides the triple-count measurement in R4(i).
- Where oracle edges live, so the gold/visible split of §4.4 holds in RDF too.

### 4.8 Equipment data (new, step 3b)

> **STRUCK 2026-09-20 (user).** Equipment data sheets are out of scope: *"we dont need to do anything
> with datasheets, thats important, just the scaling interconnecting"*. Step 3b was started and then
> reverted uncommitted on the same day; requirement **N8 falls with it**, and the DISCHARGE question in
> §10 Q5 is moot (it had been answered `differentialPressure` an hour earlier). The subsection is kept
> as written, not deleted, so the decision is reconstructable. Nothing else in the design depends on it:
> §4.4/§4.5 keep their frozen visible sets unchanged, and §10 Q4's "step 3b needs them added" no longer
> applies.

**What it is for.** N8: questions that combine topology with values, for example
`MATCH (t:Tank {tag: $y})-[:send_to*]->(p:CentrifugalPump) WHERE p.designShaftPower > $x RETURN p.tag`.

**Attributes per class.** Names are pyDEXPI 1.2.0 data attributes, listed by introspection on 2026-09-13.
"Generated" marks the ones step 3b fills; the rest exist on the class but stay empty. The OPEN100 column is
**the main session's interpretation of the printed table, not a DEXPI statement**.

| `node_class` | Generated (DEXPI name → pyDEXPI type, generated unit) | Present, not generated | OPEN100 column (interpretation) |
|---|---|---|---|
| `CentrifugalPump` | `equipmentDescription` → `MultiLanguageString`; `designVolumeFlowRate` → `VolumeFlowRate`, m3/h; `differentialPressure` → `PressureAbsolute`, bar; `designRotationalSpeed` → `RotationalFrequency`, min-1; `designShaftPower` → `Power`, kW | `designPressureHead` | SERVICE, CAPACITY, DISCHARGE, RPM, HP |
| `Compressor` | `equipmentDescription`; `designVolumeFlowRate` (m3/h); `differentialPressure` (bar) | — | — |
| `Tank`, `PressureVessel` | `equipmentDescription`; `nominalCapacityVolume` → `Volume`, m3 | `cylinderLength` | SERVICE, CAPACITY |
| `ProcessColumn` | `equipmentDescription`; `nominalCapacityVolume` (m3) | — | — |
| `HeatExchanger` | `equipmentDescription`; `designHeatFlowRate` → `Power`, kW | `designHeatTransferArea`, `designHeatTransferCoefficient` | — |

Valves and instruments carry no generated data.

**How values are generated.** `equipment_data.py` holds `EQUIPMENT_DATA_RANGES: dict[str, dict[str,
DataRange]]`, one declared uniform range and one unit per attribute, and a short word list for
`equipmentDescription` (e.g. `FEED PUMP`, `TRANSFER PUMP`). Values are drawn from `data_rng` (§3.3), rounded
to one decimal. **Ranges are arbitrary, declared in one table, and never claimed realistic.** The prototype
used, for example, 0.5–500 kW for `designShaftPower`; that choice has no source and is not a finding.

**Representation in the `DiGraph` and the store.** In the model the values are pyDEXPI quantity objects;
the builder maps unit symbols to pyDEXPI enums by value (e.g. `PowerUnit("kW")`). `GraphLoader` would render
them as strings — the prototype produced `'202.8 kW'` and, for descriptions, a JSON dump of the
`MultiLanguageString` (`loaders/graph_loader.py` lines 139–143) — which Cypher cannot compare numerically. So
the adapter reads the objects and writes:
- `<attribute>`: `float` (e.g. `designShaftPower: 202.8`), and `<attribute>_unit`: `str` (`"kW"`);
- `equipmentDescription`: plain `str`, the first `SingleLanguageString.value`.

The generator uses one unit per attribute, so nothing is converted. A real file with another unit (EXP-0001)
keeps its own `_unit`, and the `ConversionReport` counts it as non-canonical.

**Visibility: V.** A data table is printed on a real sheet, so it is not answer-key material.

**Home vs reference occurrences.** Only the home occurrence carries data. The splitter already guarantees
this: a reference occurrence is added with `tag` and `node_class` only (`splitter.py` `_draw_on_neighbour_sheets`, lines 182–184). Step 6
adds a test that no reference occurrence carries a §4.8 property.

**Schema constants (step 3b):** `EQUIPMENT_DATA_PROPERTIES: dict[str, frozenset[str]]` (per class, including
`_unit` names) and `EQUIPMENT_DATA_UNITS: dict[str, str]`. Adding them to the visible set touches frozen §4.4
and §4.5; see §10 Q4.

---

## 5. Splitter changes, prioritized

| # | Finding (`00-index.md`, 2026-09-12) | Decision | Why |
|---|---|---|---|
| 1 | `utility_aware` moves high-degree equipment, not headers; a utility crossing is one-to-many | **Defer.** Exclude `utility_aware` from every sweep. Drop the one-to-many connector. | Generator v1 emits no utilities, so the strategy's "hubs" would be process equipment (`pid-structural-rules.md` §8 item 1). Pairwise pairs suffice for linking accuracy. |
| 2a | A cut signal becomes the same connector as a cut pipe | **Fix now** | N7. The schema has distinct DEXPI classes. |
| 2b | *New, found in `splitter.py` `_cut_one_edge`:* the stub node carries only `node_class`; its label lives only in `SheetGraph.connectors` and the manifest | **Fix now** | A resolver reading sheet graphs has nothing to match on. Reading the manifest would be scoring against the answer key. |
| 2c | Missing label fields: service, source/destination, zone; same-unit vs cross-unit | Service = `fluid_code`, **fix now** (part of 2b). Source/destination tag: **defer**. Zone: **no change** (`use_grid_reference` exists). Same-unit vs cross-unit: **defer**, derivable later from endpoint `unit_id`s. | Only what EXP-0004 needs to be non-trivial |
| 3 | `modularity` is a proxy for declared units | **Fix now: add `by_unit`.** Keep `modularity` unchanged, documented as a graph-community proxy. | N6. The rule-grounded form partitions on declared unit codes (`pid-structural-rules.md` §8 item 5, S16). |
| 4 | `IdentityGroup` duplication is observation-grounded only | **Keep; no code change.** Reword `splitter.md` open question 3: "which is how real drawings do it" → "as observed on OPEN100; no drafting rule prescribes it (`pid-structural-rules.md` §8 item 6)". | It is contribution 2's gold set. A methodology needs the mechanism, not a rule for it. |
| 5 | *New:* `SplitConfig.equipment_classes` defaults to `{"vessel", "pump", "exchanger", "column", "tank"}` | **Fix now** | No generator class matches, so `_validate_has_equipment` would reject every generated plant |
| — | ADR-0007 v1's degenerate-direction precondition | **Drop** | Direction is guaranteed by construction and tested in §3.4 (invariants 5, 6). No planned path feeds an undirected graph. |

**Change specifications.**

**2a — connector kind.**
- Add `ConnectorKind(str, Enum)` with `PIPE` and `SIGNAL` to `models.py`.
- `OffPageConnector` gains `kind: ConnectorKind = PIPE`, `line_number: str | None = None` and
  `fluid_code: str | None = None`. The defaults keep the OPEN100 code valid.
- In `_cut_one_edge`: `relation = edge_attrs.get("relation", "send_to")`. `send_to` gives `PIPE`; anything
  else gives `SIGNAL`.
- The stub `node_class` is `FlowOut{Pipe|Signal}OffPageConnector` on the source sheet and
  `FlowIn{Pipe|Signal}OffPageConnector` on the target sheet.
- The literal `"off_page_connector"` disappears.

**2b — visible label on the stub node.**
- Add `ConnectorLabelDetail(str, Enum)` with `FULL` and `DRAWING_ONLY`, and
  `SplitConfig.connector_label_detail = FULL`.
- Each stub node gets `connector_number` (its own tag), `referenced_drawing_number` (the partner sheet id),
  and `line_number` and `fluid_code` copied from the cut edge when present.
- Under `FULL` only, it also gets `referenced_connector_number` (the partner tag).
- `DRAWING_ONLY` is the harder EXP-0004 condition: pairs between the same two sheets must be told apart by
  line number and fluid.
- `rejoin` is unaffected, because stubs are removed.

**3 — `by_unit` strategy** in `strategies.py`, registered in `STRATEGIES`:
1. Build the owner graph and `order = _flow_order(...)` exactly as `flow_greedy` does.
2. The unit of an owner is `plant.nodes[owner].get("unit_id", "")`.
3. Order units by the first position of any of their owners in `order`, so sheet numbers follow flow.
4. For each unit, keep its owners in `order` and apply `_chunk_by_budget`. Concatenate the chunk lists, so
   no sheet ever holds two units.
5. If no equipment node has a `unit_id`, raise
   `ValueError("by_unit needs unit_id on equipment nodes")`.

**1 — docstring only.** `utility_aware` gets a docstring note: "not used in experiments until the generator
emits utilities (plant-generator.md §5)".

**5 — default classes and fixtures.**
- `SplitConfig.equipment_classes` defaults to `set(schema.EQUIPMENT_CLASSES)`.
- `tests/plant_fixtures.py` switches to DEXPI names: `vessel`→`PressureVessel`, `pump`→`CentrifugalPump`,
  `exchanger`→`HeatExchanger`, `column`→`ProcessColumn`, `tank`→`Tank`,
  `instrument`→`ProcessSignalGeneratingFunction`. `utility_header` stays as a test-only non-schema class.
- Fixture edges get a `relation`: process and utility edges `send_to`, instrument edges `measured_by`.
- Update the assertion at `tests/test_splitter_models.py` line 38 and the explicit set at
  `tests/test_strategies.py` line 64.

**New splitter tests.**
- Connector class follows relation kind.
- Stub label attributes are present.
- `DRAWING_ONLY` omits `referenced_connector_number`.
- `by_unit` never mixes units on a sheet, respects the budget, and raises without `unit_id`.
- Every sheet graph of a generated plant passes `validate_sheet_graph`.

---

## 6. pyDEXPI on the benchmark path

1. **Dependency.** `pydexpi==1.2.0` becomes a hard dependency in step 3 (ADR-0003 accepted). pyDEXPI 1.2.0
   declares Python ≥3.12: on 2026-09-13 `uv` refused `pydexpi==1.2.0` on the default Python 3.10.11, and
   resolved it on Python 3.13.1. `pyproject.toml` says `requires-python = ">=3.10"` and targets py310 for ruff
   and mypy, so step 3 must raise all three (§10 Q3). *Reasoned, not verified:* the main session's unpinned
   ephemeral run on 2026-09-13, where `svg_loader` did not import, most likely resolved an older pyDEXPI on
   Python 3.10. Pin both the version and the interpreter.
2. **The same adapter serves EXP-0001** on `DEXPIEX01.xml` (not yet in the repository): `ProteusSerializer().load`
   → `LinearGraphLoader` → `build_conceptual_graph` → §3.6 mapping. Its policies, unchanged from revision 1:
   - **MultiDiGraph → DiGraph.** Map each edge to a schema relation first. Unmappable edges are dropped and
     counted. Where two mapped edges share an ordered pair, keep one by priority
     `send_to > send_signal_to > control > measured_by`. Every dropped edge is recorded in the
     `ConversionReport`, published with EXP-0001. Nothing collapses silently.
   - **DEXPI class → `node_class`.** The class itself if it is in `NodeClass`; otherwise the nearest ancestor
     in `NodeClass` via `get_inheritance_from_dexpi_class`; otherwise unmapped and counted. (The public example
     `C01V04-VER.EX01.xml` has `PlateHeatExchanger`, `TubularHeatExchanger`, `ReciprocatingPump`,
     `SwingCheckValve`, `PipeTee`, … in its conceptual graph; most need the ancestor rule, some have none.)
   - **Seed.** Loading draws no randomness; global `random` is untouched.
3. **RDF vocabulary generation** — the script over `pydexpi.dexpi_classes.pydantic_classes`
   (`ontology-landscape.md` §5 R2).
4. **Not used:** `SyntheticPIDGenerator`, the sample patterns, a global-`random` wrapper, the stock
   `get_all_instances_in_model` on large models.

## 7. How it is tested, and the prototype evidence

The generator manufactures inputs; its correctness is observable as:
- the invariants in §3.4;
- **zero schema violations** on the plant graph and every sheet graph;
- the `ConversionReport` of every conversion (zero unmapped topology edges for generated plants);
- a `PlantSummary` per instance.

The schema reports its own coverage through the `ConversionReport` on `DEXPIEX01.xml` (EXP-0001).

**Prototype, 2026-09-13.** Scratchpad scripts, not in the repository:
`…/scratchpad/proto/{h1_model,adapter,linear_loader,run_tiny,run_scale,run_linear,determinism,shared_nozzle}.py`.
Setup: `uv run --python 3.13 --with pydexpi==1.2.0 --no-project`, Python 3.13.1, networkx 3.6.1,
pydantic 2.13.5, this developer machine, one process, wall-clock `time.perf_counter`. Plants were built by the
§3.3 algorithm with revision-1 default probabilities, seed 0.

| `n_units` | equipment | DEXPI instances | build (s) | stock `GraphLoader` (s) | `LinearGraphLoader` (s) | conceptual (s) | adapter (s) | seed → `DiGraph` (s) | `DiGraph` nodes / edges | JSON export (s) | Proteus export (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 27 | 241 | 0.108 | 0.043 | 0.013 | 0.033 | 0.002 | 0.156 | 57 / 60 | 0.008 | 0.023 |
| 50 | 282 | 2,799 | 0.150 | 4.429 | 0.136 | 0.349 | 0.011 | 0.646 | 710 / 768 | 0.164 | 0.336 |
| 250 | 1,380 | 14,598 | 0.467 | 140.387 | 0.759 | 2.249 | 0.064 | 3.539 | 3,720 / 4,109 | 0.657 | 1.089 |
| 1,000 | 5,470 | 58,028 | 1.507 | not run | 3.396 | 9.630 | 0.581 | **15.114** | 14,861 / 16,408 | 2.426 | 4.799 |

Notes:
- Separate runs, so build times differ slightly between them: 0.101 / 0.213 / 0.595 / 1.539 s in the export
  and stock-loader runs. The seed → `DiGraph` column uses the linear loader.
- File sizes at 1,000 units: pyDEXPI JSON 83.6 MB; equipment-only Proteus XML 11.3 MB.
- The linear loader's complete graph was **equal** to the stock one, node order included, at 5 and 50 units.
- The stock loader grew about quadratically: from 50 to 250 units, instances ×5.2 and time ×28.6.
- Determinism: same seed ⇒ identical JSON bytes and identical sorted `DiGraph` under `PYTHONHASHSEED` 1, 2, 3;
  edge insertion order differed (hence invariant 14); global `random` state unchanged.
- Tiny model, as specified by the main session: 2 sections, a pump with data, a tank, a vessel, a globe valve
  on the inter-unit stream, a check valve on the recycle, one level loop. Complete graph 36 nodes / 70 edges;
  conceptual 11 / 17; `DiGraph` 8 / 9. Every topology edge mapped. `PlantSection` membership arrived as
  `parentStructure` edges for equipment and instruments, not for valves. Pump data survived as strings.
- **Not measured:** peak memory; the splitter at these sizes; the stock loader at 1,000 units.

**Estimates, not measurements.**
- Stock `GraphLoader` at 1,000 units ≈ 140 s × (58,028 / 14,598)² ≈ **37 min**, from the two-point quadratic trend.
- Sheets at 1,000 units depend on the swept budget, which has no sourced value. At an arbitrary 4 equipment per
  sheet, 5,470 equipment is **about 1,370 sheets**. The splitter was not run.
- "Thousands" of sheets, e.g. 4,000 at that budget, needs about 16,000 equipment, roughly 2,900 units. If the
  linear path stays near-linear (conceptual time grew ×6.4 for ×5.2 instances, then ×4.3 for ×4.0), seed →
  `DiGraph` is **about a minute**.

**Scale smoke** (step 7) replaces these estimates with measurements:
`python -m plantgraph.benchmark.scale_smoke --n-units N --budget B --seed S` prints nodes, edges, sheets,
connector pairs, the wall-clock time of each stage (build, loader, conceptual, adapter, split) and peak memory
(`tracemalloc`). It is run once at the largest `N` that gives at least 1,000 sheets. The printout is filed as a
run note under `30-experiments/` and checked against the kill criterion (§2). A possible hotspot, unmeasured:
`rejoin._stub_edge_attrs` scans the sheet list once per pair.

## 8. Which part of the claim it serves

It is the source of every plant-scale graph in contribution 1. It unblocks EXP-0002 (scale sweep, with
`PlantSummary` as regression variables), EXP-0004 (pipe, signal and identity cuts, under oracle vs resolver)
and EXP-0005. It also supplies the plant → unit → sheet hierarchy that Phase 3's hierarchical retrieval
routes over. Because the same adapter reads `DEXPIEX01.xml`, the single-sheet baseline (EXP-0001) and the
plant-scale sweep see graphs produced by one code path — the comparison the claim rests on.

## 9. Implementation order (one sequential Sonnet `coder`, ADR-0006; each step ends with the full suite green)

1. `graph/schema.py` + `tests/test_schema.py`.
2. Finding 5: the `SplitConfig` default and the fixtures move to DEXPI names. This touches existing tests only.
3. **Generator on pyDEXPI, topology only.** Needs §10 Q3 first. Add `pydexpi==1.2.0` to `pyproject.toml`
   and raise `requires-python`, the ruff target and the mypy target to 3.12. Then build `GeneratorConfig`,
   `StreamKind` and `GenerationRecord` in `benchmark/generator_models.py` (§3.2); `adapters/pydexpi_builder.py` (§3.5); and
   `benchmark/generator.py` (§3.3), with `equipment_data=False`. Tests: `tests/test_pydexpi_builder.py`
   (sensing nozzle; a stream with 0, 1 and 2 valves) and `tests/test_generator.py` (invariants 4, 9, 10).
3a. **Adapter.** `adapters/pydexpi_adapter.py`: `LinearGraphLoader`, `plant_graph()`, `ConversionReport`,
   `summarize_plant`, and JSON / Proteus save and load (§3.6, §3.7). Tests in
   `tests/test_pydexpi_adapter.py`: invariants 1–3, 5, 6, 11–14. **First partial result:** generated plants
   feed the unchanged splitter.
3b. ~~**Equipment data** (§4.8).~~ **Struck 2026-09-20 (user): datasheets are out of scope.** Needs §10 Q4 first. Add `benchmark/equipment_data.py`, the builder's quantity
   mapping, the adapter's numeric properties, and `schema.EQUIPMENT_DATA_PROPERTIES` and `EQUIPMENT_DATA_UNITS`.
   Tests: values stay inside the declared ranges; toggling `equipment_data` leaves the topology unchanged;
   the JSON round trip keeps the values.
4. Findings 2a, 2b and 2c-service: connector kind and visible labels.
5. Finding 3: `by_unit`. Finding 1: docstring.
6. **Integration tests.** Invariants 7–8. Every sheet graph of a generated plant passes
   `graph/validation.py` `validate_sheet_graph`. ~~No reference occurrence carries a §4.8 property.~~
   (That second assertion falls with §4.8, struck 2026-09-20; the sheet-validation half stands.)
7. **`scale_smoke` over the full path:** generate → `plant_graph` → split, timing each stage and recording
   peak memory (§7). Run it once, file the run note, and check the kill criterion (§2).
8. **Utilities (later, after step 7).** Needs a short design addendum before code: how a utility header is
   represented in DEXPI, how consumers attach, and the `utility_aware` repair (§5 finding 1). Nothing in this
   revision decides it.

## 10. Open questions for the user

**Closed since revision 1 (user, 2026-09-13):**
- Q1 (accept G2) → pyDEXPI route, ADR-0007 amended.
- Q2 → unit is `PlantSection`.
- Q3 → utilities are in scope, as §9 step 8.
- Q4 → several plants per corpus is the next phase.
- Q5 → rendering is a later phase; the method input is per-sheet graphs (§11).

**Open:**
1. **Accept revision 2 and H1?** ADR-0007 stays `proposed` until the main session verifies this note.
2. **Proteus XML.** pyDEXPI 1.2.0 exports equipment only. *Recommendation:* for this phase, pyDEXPI JSON is the
   lossless artefact and the Proteus file is labelled equipment-only. Decide on a full Proteus exporter
   (piping and instrumentation modules, ours or upstream) when the rendering design starts, because only an
   external DEXPI tool or renderer would need it.
   > **User signal, 2026-09-20:** *"We will need this I think."* Recorded as a leaning, **not yet a decision**,
   > and no work started — it belongs to the rendering phase (ADR-0007, a later phase), and today's priority is
   > the scale measurement. Before it is built, two things need answering: whether the renderer we choose
   > actually consumes Proteus rather than our own graph, and whether the piping/instrumentation exporter is
   > written by us or contributed upstream to pyDEXPI (AGPL-3.0, ADR-0003, and §10 Q9 already asks the related
   > upstream question). Those make it an `architect` question with a real alternative, so it should become an
   > ADR when the rendering design starts — not a quiet addition to this note.
3. ~~**Raise Python to ≥3.12**~~ **Closed 2026-09-20: yes (user).** Already in force since 2026-09-13 and
   verified today — `requires-python = ">=3.12"` (line 7), ruff `target-version = "py312"` (line 35), mypy
   `python_version = "3.12"` (line 64); the venv runs 3.12.10. mypy `--strict` does accept pyDEXPI with the
   `pydexpi.*` override, so the "not yet checked" clause below is also resolved. *Original recommendation:* yes. The project's compiled files are already `cpython-313`, and
   pyDEXPI 1.2.0 cannot be installed otherwise. Not yet checked: whether mypy `--strict` accepts pyDEXPI's
   typing, or needs `ignore_missing_imports` for `pydexpi`.
4. **Frozen-section follow-ups, after the coder finishes steps 1, 2, 4 and 5.** Nothing blocks those steps.
   - §4.4 and §4.5: `VISIBLE_NODE_PROPERTIES` has no §4.8 data properties, so a loader enforcing it would strip
     equipment data. Step 3b needs them added.
   - §4.3 wording: pyDEXPI 1.2.0 emits no relation named `send_to`, `control`, `send_signal_to` or
     `measured_by`; its labels are in §3.6, and the names come from our adapter. DEXPI also allows a `Nozzle`
     as sensing location, so `measured_by` from equipment is not a simplification under §3.5's
     dedicated-nozzle rule.
   - §4.4 `unit_id` on valves is derived, not declared in DEXPI (§3.6).

   *Recommendation:* a one-paragraph amendment by the main session once the coder is done.
5. ~~**DISCHARGE column.**~~ **Closed 2026-09-20.** Answered `differentialPressure` by the user, then made
   moot the same day when equipment data was dropped altogether (see the §4.8 banner). No code shipped.
6. **Rendering phase, noted now.** DEXPI object ids equal the gold `node_id` (§3.3, §4.4). Any per-sheet DEXPI
   or PDF export must re-id objects with the opaque occurrence id, or it leaks the identity gold set.
7. **Several plants (next phase).** The splitter's sheet ids are `"0"`, `"1"`, … per call and need a plant
   namespace. DEXPI ids already carry `plant_id`.
8. **Rule-grounded realism (later phase).** The natural insertion point is the builder: "typicals" such as a
   pump with a discharge check valve and block valves, or a control valve with block valves and a by-pass
   (Hanford HNF-64103 §3.2.4.2, §3.2.5.1, quoted in `00-index.md`). Not designed.
9. **Upstream.** Offer the linear instance collection to pyDEXPI (AGPL-3.0, ADR-0003)? Optional; it would
   remove our only override of a private method.

## 11. Method input contract

The retrieval and resolution method never reads the plant graph, the `DexpiModel`, the `GenerationRecord` or
the `SplitManifest`. Its input is a **set of per-sheet graphs**. Today the splitter produces them. Later, a
PDF-digitization project may produce them from rendered or real drawings. This section is what that project
must deliver.

**Per sheet:** one directed graph (`nx.DiGraph`, or its `node_link_data` JSON) and a sheet record:
`sheet_id` (the drawing number as printed, unique in the corpus), plus `plant_id` and `unit_id` from the
title block where printed.

**Nodes**

| Property | On | Required | Note |
|---|---|---|---|
| node id | all | yes | unique **within the sheet**, opaque; it must carry no cross-sheet meaning (§4.4: a shared id is the identity gold set) |
| `node_class` | all | yes | one of the 12 generator classes or 4 connector classes (§4.2); a finer DEXPI class maps to its nearest ancestor (§6) |
| `tag` | all except connectors | yes | the string as printed; variants across sheets are expected and are what resolution handles |
| `connector_number`, `referenced_drawing_number` | connectors | yes | from the connector label |
| `line_number`, `fluid_code` | pipe connectors | recommended | from the connector label or the line |
| `referenced_connector_number` | connectors | optional | only if printed |
| `unit_id`, `plant_id` | home occurrences | recommended | from the title block or the tag |
| `loop_tag`, `measured_variable` | instrumentation | optional | derivable from the tag |
| §4.8 properties with `_unit` | equipment home occurrences | optional | from the data table under the drawing; numeric plus unit |

**Edges:** `relation` ∈ {`send_to`, `send_signal_to`, `control`, `measured_by`}, directed as in §4.3
(required); `line_number` and `fluid_code` on `send_to` (recommended).

**Must not contain:**
- any G property of §4.4 (a node id shared across sheets, `stream_kind`);
- any structure-layer or cross-sheet edge (`continues_as`, `same_tagged_item_as`, `is_drawn_on`, …) — the
  method builds or resolves those;
- anything from a manifest.

**Acceptance test:** `plantgraph.graph.validation.validate_sheet_graph(g) == []` for every sheet, plus the step 3b check that every §4.8
property is numeric and has its `_unit`.

**Strongly recommended with it:** a per-sheet digitization quality report against the ground truth. It should
give node precision and recall per class, edge precision and recall per relation, and character accuracy of
connector labels, so that EXP-0003 can relate digitization error to retrieval accuracy.

**Equivalent DEXPI route.** A digitizer that writes full per-sheet Proteus XML can hand that over instead. The
pyDEXPI Proteus parser reads piping and instrumentation (§3.7), and the §3.6 adapter would produce the same
graphs. *Open:* the adapter's mapping of DEXPI off-page connector references to `referenced_drawing_number`
is not yet designed. The generated benchmark never needed it.
