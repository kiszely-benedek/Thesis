---
component: ingest — Proteus importer, thin resolver, Neo4j loader
status: draft — awaiting review
related: [ADR-0009, ADR-0010, ADR-0002, ADR-0003, ADR-0013, ADR-0016, ADR-0017, plant-generator.md §4.3–§4.6 and §11, splitter.md §4]
date: 2026-09-26
---

# Design — KG construction (Phase 2): importer → resolver → Neo4j

Phase 2 of ADR-0010. The pipeline is: per-sheet graphs → resolved plant → Neo4j. After this phase the
system ingests one DEXPI file and a multi-sheet synthetic corpus and holds both in Neo4j. That is the first
half of the title, end to end.

```
Proteus XML ─► importer (A) ─┐
                             ├─► SheetGraph[] ─► localize ─► resolver (B) ─► Resolution ─► Neo4j loader (C)
generator ─► splitter ───────┘                      │                          │
                                  OccurrenceMap (gold, never passed to B) ─► scoring / gate (eval)
```

## 0. Recommendation

1. **Importer** = `pydexpi_io.load_proteus` → existing adapter → relabel node ids to the file's `proteusId`
   → one `SheetGraph`. `sheet_id` = DEXPI `MetaData.drawingNumber`. Two small adapter fixes first (§3).
2. **Leak closure = rename at the resolver boundary** (`localize`). A salted second renaming is a gate test,
   not the mechanism (§4). `plant-generator.md` §4.4 already designed this: opaque occurrence ids, with the
   mapping kept in gold.
3. **Thin resolver** = exact-label connector pairing and exact-tag equipment identity. When a case is
   ambiguous the connector stays unresolved: the resolver never guesses and never breaks a tie by id (§5).
4. **Neo4j stores the occurrence graph** (sheets, their items, connector stubs), plus `continues_as` and
   `same_tagged_item_as` links from the resolver. This follows `plant-generator.md` §4.3. The merged
   `DiGraph` stays in memory for the gate and for non-Cypher strategies (§7.1).
5. **Batched `UNWIND` writes**, wipe-and-load per `corpus_id`. **Kill threshold K-NEO: 600 s at SMOKE-02
   size**, fixed now, before any measurement. If it fires, the fallback is networkx in memory (§7.6).
   *(revised 2026-09-26, ADR-0017: "SMOKE-02 size" now means 2,900 units split at budget 16 after the
   depth-first fix, i.e. the H1000 headline corpus; still before any measurement, §7.6.)*
6. *(added 2026-09-26, ADR-0016)* **Unknown DEXPI classes are kept, never dropped:** they map to
   `GenericItem` (§3.1). Gate before EXP-0001: EX01 maps 36/36 nodes and T4750 → P4712 is a `send_to` path.

## 1. What the claim needs from this phase

- EXP-0001 and EXP-0002 must run the **same downstream code** (ADR-0009 rationale). Otherwise a difference
  between them is a pipeline difference, not a scale effect. Both therefore enter through `SheetGraph` →
  `localize` → `resolve` → load.
- The crossover (EXP-0002) runs on the resolver's output **with the equality asserted** (ADR-0010
  decision 3). Every component below must therefore be able to report whether it reproduced ground truth.
- The resolver gate is a **correctness gate, not a result** (ADR-0010 decision 2). Never report "ER 100 %".

## 2. Facts this design rests on (verified 2026-09-26 unless marked)

Source: architect probe, run with `uv run python` on `data/external/C01V04-VER.EX01.xml`. The script was in
the scratchpad and was not committed.

| Fact | Value |
|---|---|
| `ProteusSerializer().load` | 0.33–0.36 s. Complete graph 214 nodes / 376 edges; conceptual graph 36 / 39 (the ADR-0009 outcome log agrees) |
| `MetaData.drawingNumber` / `drawingName` | `"123/A93"` / `"DEXPI example PID"` |
| `MetaData.id` | **differs between two loads.** A random uuid, not usable |
| Conceptual node ids | **differ between two loads.** 0 of 23 mapped ids occur in the XML |
| `proteusId` attribute on conceptual nodes | present on 36/36, unique, all 36 found as `ID="…"` in the XML. **Stable** |
| `map_conceptual_graph` on EX01 | **crashes**: `KeyError: 'unit_id'` in `_assign_valve_units` (`pydexpi_adapter.py:354`). No `PlantSection`, so equipment has no `unit_id` |
| With that line made tolerant | 23 nodes / 16 edges mapped. Dropped classes: `PipeTee` 5, `BlindFlange` 2, `ButterflyValve`, `PipeReducer`, `SpringLoadedGlobeSafetyValve`, `ReciprocatingPump`, `FlowInPipeOffPageConnector`, `FlowOutPipeOffPageConnector` (1 each). `valve_units_unresolved` 9 |
| Edges lost with a dropped endpoint | **23 of 39**. **`ConversionReport` does not count them**: `edges_dropped_per_label` is `{}` (`_map_edges` skips them at line 312 without counting) |
| `validate_sheet_graph` on the result | 3 `duplicate_tag` violations. Valves `C1` (×3) and `C2` (×2): `pipingComponentNumber` is not unique on a real sheet |
| Splitter leak 1 | a reference occurrence reuses the home's node id (`splitter.py:182–183`) |
| Splitter leak 2 (**new**) | `OffPageConnector.partner_tag` is filled **even at `DRAWING_ONLY`** (`connectors.py:85–106`). Only the node attribute `referenced_connector_number` honours the dial (`connectors.py:150–151`) |
| Plant node ids | `{plant_id}-u{unit}-{kind}{seq}` (`generator.py:283–287`). They encode unit and kind |
| Sheet ids from strategies | `"0"`, `"1"`, … in flow order (`strategies.py:269–274`) |
| SMOKE-02 | 43,043 nodes, 47,405 edges, 4,015 sheets, 18,048 pairs; config at `duplication_rate=0.0` (`30-experiments/2026-09-20-scale-smoke.md`) |

## 3. Component A — Proteus importer (ADR-0009 I4)

**Files.** `src/plantgraph/adapters/pydexpi_proteus_import.py` (new). Its name keeps the ADR-0003 rule
that only `adapters/pydexpi_*.py` touches pyDEXPI. Plus small edits to `pydexpi_io.py` and
`pydexpi_adapter.py`.

**Prerequisite edits (in T1):**
- `pydexpi_io.load_proteus(directory: Path, filename: str) -> DexpiModel` loads a full file. It is the same
  call as `load_proteus_equipment_only`, whose name is wrong for a full file.
- `map_conceptual_graph(conceptual, plant_id: str, stream_kind: Mapping[str, StreamKind])` replaces the
  `record: GenerationRecord` parameter. An imported file has no generation record, and faking one would
  put a gold-type object on the import path. There are two call sites: `pydexpi_adapter.py:115` and
  `scale_smoke.py:109`.
- `_assign_valve_units`: an owner without `unit_id` counts as unresolved and does not raise
  (`if owner is None or "unit_id" not in plant.nodes[owner]`). This adds no lines, and the adapter is at
  394/400. *(revised 2026-09-26, ADR-0016: after T1 the adapter is at **400/400**, counted on the working
  tree 2026-09-26. Any further import logic goes in its own `adapters/pydexpi_*.py` module, §3.1.)*

**Types.**
```python
class ImportReport(BaseModel):
    source_file: str; sha256: str
    sheet_id: str; sheet_id_source: Literal["drawing_number", "file_stem", "argument"]
    drawing_name: str | None; plant_id: str
    conceptual_nodes: int; conceptual_edges: int
    conversion: ConversionReport
    edges_lost_to_unmapped_endpoints: dict[str, int]   # key "SourceClass->TargetClass"
    violations: list[SchemaViolation]

@dataclass
class ImportedSheet:
    sheet: SheetGraph          # connectors == [] (see §4)
    report: ImportReport

def import_proteus_sheet(path: Path, *, sheet_id: str | None = None,
                         plant_id: str | None = None) -> ImportedSheet: ...
```

**Rules.**
- **Sheet id for a lone file:** use `sheet_id` if it was passed. Otherwise use `MetaData.drawingNumber` if
  it is present and non-empty. Otherwise use the file stem. §11 asks for "the drawing number as printed",
  and EX01 prints `123/A93`. Raise if the id contains `:`, which is the key separator (`rejoin.py:87`,
  `OffPageConnector.key`).
- **`plant_id`:** the argument if given, else the file stem. The file has no `ProcessPlant` or
  `PlantSection` (`parent_structure_folded` = 0). `unit_id` stays absent. It is optional on sheets (§11).
- **Node ids:** relabel the mapped graph from conceptual ids to `proteusId`. Raise if one is missing or
  duplicated. This makes the import deterministic.
- **Nothing vanishes silently:** `nodes_mapped + Σ nodes_dropped_per_class == conceptual_nodes`. Every
  conceptual edge that is not in the output is either counted in the existing report fields or in
  `edges_lost_to_unmapped_endpoints`.
- **Violations are reported, not raised.** Duplicate valve tags are a fact of real sheets. The CLI prints
  them.
- ~~**Off-page connectors in a file are dropped and counted** (as today).~~ *(revised 2026-09-26,
  ADR-0016 rule 3)* **Off-page connectors in a file map to their schema connector classes**
  (`FlowInPipeOffPageConnector`, …). They stay unpaired, and `sheet.connectors == []` still holds. Mapping
  DEXPI connector references onto `connector_number` and `referenced_drawing_number` stays open (ADR-0009
  "Unverified"; §11). EX01 is a single sheet, so it does not need this.
- *(added 2026-09-26, ADR-0016)* **Unknown classes are kept as `GenericItem`**, never dropped. §3.1 gives
  the rules; T1b implements them.

**Tests** (`tests/test_proteus_import.py`):
- EX01, skipped if the file is absent (`data/` is untracked). `sheet_id == "123/A93"`; 23 nodes, 16 edges;
  the dropped-class counts in §2; `sum(edges_lost_to_unmapped_endpoints.values()) == 23`; 3
  `duplicate_tag` violations; identical node ids across two imports; the accounting invariant.
- Always-on: a 4-unit generated plant → `save_proteus_equipment_only` → `import_proteus_sheet`. The import
  must succeed, ids must be deterministic across two imports, every node class must be in
  `EQUIPMENT_CLASSES`, and the accounting invariant must hold. Whether the count equals the plant's
  equipment count is **unverified**. Assert it only if it holds, and say so in the report.
- A hand-built conceptual `MultiDiGraph`: a pump with no `parentStructure` feeding a valve. Expect
  `valve_units_unresolved == 1` and no `KeyError`.
- *(revised 2026-09-26, ADR-0016)* The EX01 figures above (23 nodes, 16 edges, the dropped-class counts,
  23 lost edges) describe T1 **before the fallback**. T1b replaces them with the §3.1 gate figures.

**Reports its accuracy against ground truth:** only as coverage. EX01 has no node-level gold. The
212 → 53 (ChatP&ID) versus 214 → 36 → 23 (ours) gap stays an EXP-0001 check. *(revised 2026-09-26,
ADR-0016: after T1b ours is 214 → 36 → 36; the 212 → 53 gap is upstream of the adapter and unchanged.)*

### 3.1 Unknown DEXPI classes: the generic fallback (added 2026-09-26, ADR-0016)

ADR-0016 chose U3 with no promotions: an unknown class is mapped and kept, never dropped. Its rule 6
leaves three details to this section: the tag rule per category, the label cut-off, and where the code
lives.

**Where the code lives.** `pydexpi_adapter.py` is at its 400-line limit (verified on the working tree
2026-09-26). The fallback therefore goes in a new module, `src/plantgraph/adapters/pydexpi_generic.py`.
Its name keeps the ADR-0003 rule. The adapter changes by **renames only, zero net lines**:
- `_topology_node_class` becomes the public `topology_node_class`, so the new module can ask "would the
  adapter drop this label?" without importing a private name.
- Its two membership tests read `schema.IMPORTABLE_CLASSES` instead of `schema.GENERATOR_CLASSES`.

**Schema additions** (`graph/schema.py`, 285 lines today):
- `NodeClass.GENERIC_ITEM = "GenericItem"`, with `ClassSpec(labels=("GenericItem",),
  category=NodeCategory.OTHER)`, and a new `NodeCategory.OTHER = "other"`.
- `IMPORTABLE_CLASSES = GENERATOR_CLASSES | CONNECTOR_CLASSES | {"GenericItem"}`. `GENERATOR_CLASSES`
  itself does not change, so generated plants cannot change (ADR-0016 "Why").
- `Relation.RELATED_TO = "related_to"`.
- `RELATION_ENDPOINTS`: `GenericItem` is allowed at both ends of every topology relation, because
  validation cannot know its semantics (that is what promotion is for). `related_to` allows every class
  in `IMPORTABLE_CLASSES` at both ends.
- `VISIBLE_NODE_PROPERTIES` gains `dexpi_class`, `category` and `dexpi_labels`. `VISIBLE_EDGE_PROPERTIES`
  gains `dexpi_label`. They describe the symbol that the drawing shows. Generated plants never set them.

**Rules** (all in `pydexpi_generic.py`):
1. **Pre-pass**, `prepare_generic(conceptual) -> tuple[nx.MultiDiGraph[str], dict[str, GenericInfo]]`, on a
   copy. A node whose label `topology_node_class` maps to `None` gets the label `GenericItem`, and its
   original label is kept in `GenericInfo`. The structure labels that the adapter folds on purpose
   (`PlantSection`, `ProcessPlant`; `_map_nodes` docstring) are left alone. Connector classes need no
   pre-pass: they are in `IMPORTABLE_CLASSES` and map to themselves.
2. *(revised 2026-09-27: instrumentation roots added at the user's request — `ActuatingSystem`, `InstrumentationLoopFunction`, `ProcessSignalGeneratingSystem`, `SignalConveyingFunction`, and the known `ProcessInstrumentationFunction`, `ProcessSignalGeneratingFunction`, `ActuatingFunction`; no shared mixin is a root. Measured over all 465 pyDEXPI 1.2.0 model classes: 106 equipment, 56 piping, 7 instrumentation, 263 other, 0 errors; no class changed from equipment/piping. Of the remaining `other`, ~111 are not plant items (graphics, attribute/quantity types, structure); components such as `Transmitter`, `ControlledActuator`, `Positioner`, `PrimaryElement` have no shared pyDEXPI parent and would need naming one by one — deferred per ADR-0016 rule 4.)* **Label cut-off.** `classify(label) -> GenericInfo(dexpi_class, category, labels)` walks pyDEXPI's
   `get_inheritance_from_dexpi_class`. The label chain is the prefix up to **and including** the first
   *category root*. The roots are a closed table: `Equipment` → `equipment`, `PipingComponent` → `piping`.
   With no root, or with a label that is not a pyDEXPI class, the category is `other` and the chain is
   `(dexpi_class,)`.
   - **Why a root table and not the whole chain.** Past the root, pyDEXPI's chain runs into mixins
     (`CustomAttributeOwner`, `PipingSourceItem`, `SensingLocation`, …) that are not categories.
   - **Verified** (pyDEXPI 1.2.0, architect probe 2026-09-26): `ReciprocatingPump:Pump:Equipment`;
     `PipeTee`, `BlindFlange`, `PipeReducer` → `…:PipeFitting:PipingComponent`;
     `ButterflyValve:OperatedValve:PipingComponent`;
     `SpringLoadedGlobeSafetyValve:SafetyValveOrFitting:PipingComponent`.
   - Instrumentation has no shared root in pyDEXPI (`FlowDetector` → `ProcessSignalGeneratingSystem`,
     `ControlledActuator` → `CustomAttributeOwner`), so an unknown instrument falls to `other`. None
     occurs on EX01.
3. **Tag rule per category.** `equipment` → `tagName`; `piping` → `pipingComponentNumber`; `other` → no
   tag. These are the attributes `_tag_of` already reads for the known classes of that category.
4. **Post-pass**, `annotate_generic(plant, infos, conceptual) -> None`, runs between `map_conceptual_graph`
   and the relabel to `proteusId`. It sets `dexpi_class`, `category`, `dexpi_labels` (a list) and the tag.
5. **Edges** (ADR-0016 rule 2). Once both ends are mapped, `_map_edges` maps the 23 previously lost EX01
   edges with its existing relations. Any conceptual edge counted in
   `ConversionReport.edges_dropped_per_label` becomes a `related_to` edge whose `dexpi_label` is that key.
   If the pair already has an edge, it is counted in `ImportReport.related_to_collapsed` instead. On EX01,
   `edges_dropped_per_label` was `{}` at 23 mapped nodes (§2). Whether it stays `{}` at 36 is
   **unverified**.
6. **Counting** (ADR-0016 rule 5). `ImportReport.nodes_per_dexpi_class: dict[str, int]` counts every output
   node by its pyDEXPI label, known and generic alike. It must equal the conceptual graph's label counts
   minus the folded structure nodes. ADR-0016 names `ConversionReport` for this count; it sits on
   `ImportReport` instead, because `ConversionReport` lives in the capped adapter and the generator path
   does not need it. Rule 6 of the ADR delegates this placement here.
7. **Neo4j labels (T6).** A `GenericItem` occurrence is written with the labels `dexpi_labels` plus
   `GenericItem`. The marker label lets an audit query count generic nodes (ADR-0016's revisit trigger).
   The importer checks every chain entry against `pydexpi_classes`. The loader cannot import pyDEXPI
   (ADR-0003), so it checks each entry against `^[A-Z][A-Za-z0-9]*$` and raises otherwise. The §7.4
   no-injection rule therefore still holds.

**Gate before EXP-0001** (ADR-0016 rule 5, tested in T1b):
- EX01 maps **36/36** conceptual nodes: `nodes_dropped_per_class == {}`. By the §2 dropped counts that is
  11 `GenericItem` nodes (5 + 2 + 1 + 1 + 1 + 1) and 2 connector nodes.
- **T4750 → P4712 is a `send_to` path** on the imported sheet, found by tag.
- `nodes_per_dexpi_class` sums to 36, and the accounting invariant holds.

**Generic share on EX01 (arithmetic from §2): 11 of 36 ≈ 31 %.** This is above ADR-0016's revisit trigger
of "about 25 %". See open question 1.

## 4. The contract at the resolver boundary — closing the leak

### 4.1 Leak audit (the check ADR-0009 asked for)

| # | Channel | Leaks | Closed by |
|---|---|---|---|
| L1 | a reference occurrence's node id equals its home's (`splitter.py:183`) | identity gold | `localize` renames |
| L2 | `SheetGraph.connectors[*].partner_tag` / `partner_sheet_id`, filled at every dial (`connectors.py:85–106`) | pairing gold at `DRAWING_ONLY` | `localize` empties `connectors`; the resolver reads node attributes only |
| L3 | plant node ids encode unit and kind (`generator.py:287`) | unit (already visible), kind | renamed |
| L4 | stub ids `opc:{sheet}:{index}`, where the index follows the sorted cut order on both sheets (`connectors.py:31–35, 164`) | weak ordering correlation between partners | renamed |
| L5 | node insertion order follows plant order | ordering | `localize` inserts in sorted new-id order |
| L6 | `stream_kind` on edges | G property (§4.4), not pairing gold | stripped by the whitelist |
| L7 | the `SplitManifest`, `rejoin` | everything | import ban, tested (§5.7) |
| — | sequential sheet ids in flow order; `referenced_drawing_number`; line and fluid codes on both halves of a cut | **not leaks**: printed on real drawings (V in §4.4) | — |

### 4.2 Decision D1 — rename at the boundary (chosen) versus a renaming property test only

- **D1-a, rename at the boundary (chosen).** `localize` produces contract-clean sheets. The resolver,
  Neo4j, retrieval and any LLM prompt only ever see opaque ids.
- **D1-b, property test only.** The resolver runs on raw splitter output, and a test shows that its output
  is invariant under renaming. That proves independence only on the inputs tested. The leaked ids still
  flow to Neo4j and into prompts. An LLM that sees `P1-u3-eq2` on two sheets can merge the two occurrences
  itself, which is a leak into **retrieval**, not only into resolution.
- **Why D1-a.** It closes the leak for every consumer at no extra cost, and it is the design `plant-generator.md`
  §4.4 already fixed. D1-b is kept as gate G2: the salted renaming (§5.6).

### 4.3 `localize`

File: `src/plantgraph/resolution/localize.py`.

```python
class OccurrenceMap(BaseModel):
    local_to_original: dict[str, str]     # "sheet:occ_id" -> "sheet:original_node_id"
    def original_key(self, local_key: str) -> str: ...
    def original_node_id(self, local_key: str) -> str: ...

def localize(sheets: Sequence[SheetGraph], salt: str = "") -> tuple[list[SheetGraph], OccurrenceMap]: ...
```
- `occ_id = sha1(f"{salt}{sheet_id}:{node_id}").hexdigest()[:12]`, as in §4.4. Raise on a collision
  within a sheet. The hash is 48 bits, and SMOKE-02 has about 79 k occurrences (§7.5). Probably never hit,
  but checked.
- Nodes and edges keep only the `VISIBLE_NODE_PROPERTIES` and `VISIBLE_EDGE_PROPERTIES` keys. Output
  `connectors = []`. Nodes and edges are inserted in sorted order.
- It applies to **every** producer: splitter sheets and imported sheets alike.

`src/plantgraph/resolution/contract.py`:
`check_contract(sheets) -> None` raises `ValueError` with the offending sheet and id when any of these hold:
- a node id occurs on more than one sheet;
- a property is outside the V whitelists;
- `connectors` is non-empty;
- a `sheet_id` is duplicated or contains `:`.

`resolve` calls it first. Raw splitter output is therefore rejected at `duplication_rate > 0`, with the
message pointing at `localize`.

## 5. Component B — thin resolver

Package `src/plantgraph/resolution/`. Input: `Sequence[SheetGraph]` only. There is no manifest, no
`OccurrenceMap` and no `SplitConfig`.

### 5.1 Common connector view (the seam for EXP-0004)

```python
class ConnectorLabel(BaseModel):          # what is printed on one connector symbol
    key: str                              # "sheet:occ_id"
    sheet_id: str
    direction: Direction                  # FlowIn… -> INCOMING, FlowOut… -> OUTGOING
    kind: ConnectorKind | None            # Pipe…/Signal… class; None allowed for OPEN100
    relation: str | None                  # relation of the stub's single edge
    connector_number: str
    referenced_drawing_number: str
    referenced_connector_number: str | None
    line_number: str | None
    fluid_code: str | None

def read_connector_labels(sheet: SheetGraph) -> list[ConnectorLabel]: ...
```
Built from connector **nodes** (`node_class in CONNECTOR_CLASSES`), never from `SheetGraph.connectors`. Raise
if a stub does not have exactly one incident edge. The OPEN100 adapter `ConnectorObservation → ConnectorLabel`
is Phase 5. The optional fields exist so that it fits without a model change.

### 5.2 Pairing (`pairing.py`)

`pair_connectors(labels, sheet_ids) -> tuple[list[ConnectorPair], list[UnresolvedConnector]]`. The output
pairs run from outgoing to incoming and have `original_edge=None`.

1. **Absent target:** if `referenced_drawing_number ∉ sheet_ids`, record `UnresolvedConnector(reason="referenced
   drawing not in corpus")`.
2. **Rule CONNECTOR_NUMBER** applies when both labels carry `referenced_connector_number`. Index the incoming
   labels by `(sheet_id, connector_number)`. A pair needs a **mutual** match: each label's
   `referenced_drawing_number` equals the other's `sheet_id`, and each label's `referenced_connector_number`
   equals the other's `connector_number`. If an index key is duplicated, the case is ambiguous and goes to
   unresolved.
3. **Rule LINE_NUMBER / SERVICE_DIRECTION** applies to the rest. Group by
   `(out.sheet, in.sheet, kind, relation, line_number, fluid_code)`. Pair **only** when the group holds exactly
   one outgoing and one incoming label. Use `LINE_NUMBER` if `line_number` is set, else `SERVICE_DIRECTION`.
   Larger groups become unresolved with reason `"ambiguous: k outgoing, m incoming share this label"`.
4. **Model change:** add `MatchRule.CONNECTOR_NUMBER = "connector_number"` to `benchmark/models.py`, ranked
   strongest, and update the ranking sentence in the docstring. `SYNTHETIC` is wrong for a prediction:
   it means "the generator knows".

**Property worth a test.** On synthetic sheets, true partners always share the full step-3 key: both stub
edges carry the same `edge_attrs` (`connectors.py:60–83, 146–149`). A singleton-singleton group is therefore
necessarily correct, so **pair precision is 1.0 at every dial**. Harder dials can only lower recall.

Complexity is O(connectors), using dicts only. Do not scan the sheet list per pair (the SMOKE-03 finding in
`rejoin.py:88`).

### 5.3 Identity (`identity.py`)

`group_identities(sheets, classes=EQUIPMENT_CLASSES) -> tuple[list[IdentityGroup], int]`. The int is the
number of ambiguous tag keys.
- Key = `(tag, node_class)`, over non-connector nodes of `classes` that have a non-empty tag. A key that
  occurs on **two or more sheets** forms a group.
- A key that is **non-unique within any one sheet** is excluded and counted. EX01's `C1` shows this happens.
- **Equipment only, by default.** The splitter duplicates only equipment (`splitter.py:124–126`). Merging
  valves by tag would merge per-line numbers like `C1` across sheets.
- **Representative** (the predicted `home`) = the occurrence with the most properties, tie-broken by
  `sheet_id`. Never by occurrence id: the salted renaming would change the choice. A home has full
  attributes; a reference has `tag` and `node_class` only (`splitter.py:182–184`).
- **Exact equality only.** Tag normalisation is Phase 5. Tuning it to `_tag_variant`'s three mutations
  (`splitter.py:223–227`) would score the resolver against its own noise model, which is circular.

### 5.4 Merge (`merge.py`)

`build_plant_graph(sheets, pairs, groups) -> tuple[nx.DiGraph[str], int]`. The int counts edge-attribute
conflicts.
- Node ids are local keys `"sheet:occ_id"`, mapped through the identity representative. A node takes its
  **representative's** attributes, not the union (a union would pull in variant tags).
- Intra-sheet edges between non-stub nodes are added through the representatives. If the same edge arrives
  twice with different attributes, count it and keep the first in `sheet_id` order.
- For each pair, add `(pred(out stub), succ(in stub))` through the representatives, with the out-stub edge's
  attributes. Drop both stubs.
- **Unpaired stubs stay** as nodes with their edge, so a miss shows up in the gate as a difference. They
  never disappear.

### 5.5 Output (`models.py`, `resolver.py`)

```python
class ResolutionReport(BaseModel):
    n_sheets: int; n_occurrences: int; n_connectors: int
    pairs_by_rule: dict[str, int]; unresolved_by_reason: dict[str, int]
    n_identity_groups: int; ambiguous_tag_keys: int; edge_attribute_conflicts: int

@dataclass
class Resolution:                     # dataclass, like SheetGraph: it holds a DiGraph
    plant: nx.DiGraph[str]
    connector_pairs: list[ConnectorPair]
    identity_groups: list[IdentityGroup]
    unresolved: list[UnresolvedConnector]
    report: ResolutionReport

def resolve(sheets: Sequence[SheetGraph]) -> Resolution:
    """check_contract → read_connector_labels → pair_connectors → group_identities → build_plant_graph"""
```
A connector is either paired or unresolved. `dangling` stays empty. `DanglingReference.target` is a
`SheetRef`, and synthetic sheet ids do not parse into one. Absent targets are therefore unresolved with an
explicit reason.

### 5.6 Gates

Tools live in `src/plantgraph/eval/graph_equality.py`:
- `visible_view(g)` keeps V properties only;
- `to_original_ids(g, occurrence_map)` relabels local keys to original node ids and raises if two nodes map
  to one id;
- `graph_differences(actual, expected, limit=20) -> list[str]` is the `assert_graphs_equal` logic of
  `test_splitter.py:26–37` as a function that returns differences.

| Gate | Where | Pass condition |
|---|---|---|
| **G1** equality | pytest: every strategy × `duplication_rate` ∈ {0.0, 0.5}, on the `make_plant_graph` fixture and a 4-unit generated plant; **SMOKE sizes: CLI `--check` run** (SMOKE-01 1,000 units and SMOKE-02 2,900 units, each at dup 0.0 and 0.5), recorded as **SMOKE-04** *(revised 2026-09-26, ADR-0017: at budget 16 with the depth-first `_flow_order`, i.e. after T4b)* | `graph_differences(to_original_ids(resolve(localize(split(p))).plant), visible_view(p)) == []` |
| **G2** renaming | pytest, same grid | the outputs under `salt=""` and `salt="renamed"`, mapped to original keys, are identical: graph, pairs, groups, unresolved |
| **G3** pairs = manifest | pytest, and the SMOKE-04 run | the original-key pairs as a set of unordered pairs equal `manifest.connector_pairs`; the groups as a set of frozensets equal `manifest.identity_groups` |
| **G4** harder dials run | pytest, one case each: `DRAWING_ONLY`; `exact_match_tags=False` (dup 0.5); `PID_STYLE`; `use_grid_reference=True` | no exception; every connector is paired or unresolved; pair precision == 1.0 (§5.2). Recall and identity scores are reported, not asserted |

G1 does not run in pytest at SMOKE sizes. SMOKE-02 generation alone measured 49.42 s (`2026-09-20-scale-smoke.md`).

### 5.7 Guard against reading the answer key

`tests/test_resolution_imports.py` parses every module in `plantgraph.resolution` with `ast`. It asserts
that none imports `benchmark.splitter`, `benchmark.rejoin`, `benchmark.strategies` or `eval`, and that
none references `SplitManifest` or `OccurrenceMap`.

## 6. Scoring (reused by EXP-0004)

File: `src/plantgraph/eval/resolution_scoring.py`. It has no pyDEXPI and no Neo4j.

```python
class PairScore(BaseModel):
    true_positives: int; false_positives: int; false_negatives: int
    precision: float | None; recall: float | None; f1: float | None   # None when the denominator is 0

class ResolutionScore(BaseModel):
    connector_pairs: PairScore
    identity: PairScore
    pair_precision_by_rule: dict[str, float | None]

def pairs_to_original(pairs, occurrence_map) -> list[ConnectorPair]: ...
def groups_to_original(groups, occurrence_map) -> list[IdentityGroup]: ...
def score_connector_pairs(predicted, gold) -> PairScore: ...      # unordered {from_key, to_key}
def score_identity_groups(predicted, gold) -> PairScore: ...      # pairwise over occurrences within groups
def score_resolution(resolution, manifest, occurrence_map: OccurrenceMap | None) -> ResolutionScore: ...
```
- **Pairs are compared unordered.** OPEN100 pairs are not directed (`open100/manifest.py`).
- **Identity is scored pairwise.** A group of k occurrences contributes k(k−1)/2 same-item links. This is
  the standard pairwise ER measure. B-cubed is the alternative and is not used here. A citation is still
  owed: the `researcher` should confirm one (Menestrina et al., VLDB 2010, is a candidate, **not read**).
- `occurrence_map=None` means the keys are already in manifest space. That is the OPEN100 case, where there
  is no renaming.
- **Tests:** hand-built cases covering TP, FP, FN and empty sets; a reversed pair counts as a TP; G3 expressed
  as `score == 1.0` at defaults; `DRAWING_ONLY` gives precision 1.0.

## 7. Component C — Neo4j loader

Package `src/plantgraph/store/`. It does **not** go in `graph/`, because `graph/` must not import
`benchmark` (the `schema.py` docstring) and the loader needs `Resolution`, `ConnectorPair` and
`IdentityGroup`.

### 7.1 Decision D2 — what is stored

- **D2-a, the occurrence graph plus link edges (chosen).** Every node of every localized sheet, stubs
  included, with `continues_as` (FlowOut stub → FlowIn stub) and `same_tagged_item_as` (reference → home).
  This is exactly `plant-generator.md` §4.3. It is lossless with respect to the sheets, and hierarchical
  retrieval gets a real `Sheet` layer.
- **D2-b, the merged plant only**, with `is_drawn_on` to several sheets. Compact, and simple Cypher. But the
  connector labels, `continues_as` and "which sheet shows which edge" are lost. The cross-sheet structure
  is then bypassed at retrieval, which is what ADR-0010's rationale argues against.
- **D2-c, both.** It doubles the store. Postpone it until the retrieval design says CypherRAG needs a
  collapsed view. The same loader can then write the merged graph under a second `corpus_id`.

### 7.2 Store shape

| Element | Neo4j | Properties |
|---|---|---|
| corpus | `(:CorpusNode:DrawingSet)` | `uid`, `corpus_id`, `drawing_set_id` (= `corpus_id`) |
| sheet | `(:CorpusNode:Sheet)` | `uid`, `corpus_id`, `sheet_id` |
| occurrence | `(:CorpusNode:<labels_for(node_class)>)` | `uid`, `corpus_id`, V properties only |
| hierarchy | `has_sheet` DrawingSet→Sheet; `is_drawn_on` occurrence→Sheet | — |
| topology | relationship type = `relation` verbatim, lowercase (§4.6) | `line_number`, `fluid_code` when set |
| links | `continues_as`, `same_tagged_item_as` | `asserted_by` ∈ {`resolver`, `oracle`}; `match_rule` on `continues_as` |

- `uid = f"{corpus_id}|{local_key}"`. `corpus_id` must match `[A-Za-z0-9_.-]+`. Sheet ids may contain `/`
  (EX01).
- **`CorpusNode` is a bookkeeping label.** The retrieval design must leave it out of any schema shown to an
  LLM.
- Deferred: `is_located_in`, `PlantSection` and `ProcessPlant`. Reference occurrences carry no `unit_id`. The
  retrieval note decides whether units are needed.
- The mixed-case relationship names (`send_to` next to `is_drawn_on`) follow `schema.Relation`. The
  caller's upper-case `IS_DRAWN_ON` and similar names were shorthand.

### 7.3 Decision D3 — write method

- **UNWIND batches through the driver (chosen).** Online, per-corpus, idempotent, and testable as generated
  Cypher.
- **`neo4j-admin database import`.** A bulk CSV import, probably the fastest. But it is offline, needs the
  DBMS stopped, and replaces a whole database, so there is no per-corpus wipe. Keep it as the second
  fallback under K-NEO.
- **Per-row `MERGE`.** Simplest, and slowest by construction: one round trip per element.

### 7.4 Pure plan, then execution

`store/neo4j_plan.py` has no driver import.
```python
class CypherStatement(BaseModel):
    query: str
    parameters: dict[str, object]

class LoadPlan(BaseModel):
    corpus_id: str
    schema_statements: list[CypherStatement]
    node_statements: list[CypherStatement]           # one per (label set, batch)
    relationship_statements: list[CypherStatement]   # one per (type, batch)
    expected_node_labels: dict[str, int]             # every label a node carries counts once
    expected_relationship_types: dict[str, int]

def build_load_plan(corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution,
                    asserted_by: Literal["resolver", "oracle"] = "resolver",
                    batch_size: int = 5000) -> LoadPlan: ...
```
- Labels and relationship types cannot be Cypher parameters. They are therefore written into the query
  string, but **only** from `labels_for()` and `schema.Relation`, which is a closed whitelist, so this is
  no injection risk. Raise on anything else. *(revised 2026-09-26, ADR-0016: the one exception is a
  `GenericItem`'s `dexpi_labels`, each checked against `^[A-Z][A-Za-z0-9]*$`; §3.1 rule 7.)*
- Rows are `{"props": {...}}` for nodes and `{"source_uid", "target_uid", "props"}` for relationships.
  `None` values are dropped before sending.
- `batch_size = 5000` is a **starting value, not measured**. It is exposed as a CLI flag.

Statement shapes (Neo4j 5 syntax, **to be verified on the DBMS the user creates**):
```cypher
CREATE CONSTRAINT corpus_node_uid IF NOT EXISTS FOR (n:CorpusNode) REQUIRE n.uid IS UNIQUE
CREATE INDEX corpus_node_corpus_id IF NOT EXISTS FOR (n:CorpusNode) ON (n.corpus_id)
CREATE INDEX corpus_node_tag IF NOT EXISTS FOR (n:CorpusNode) ON (n.tag)

UNWIND $rows AS row CREATE (n:CorpusNode:CentrifugalPump:Pump:Equipment:TaggedPlantItem) SET n = row.props

UNWIND $rows AS row
MATCH (a:CorpusNode {uid: row.source_uid}) MATCH (b:CorpusNode {uid: row.target_uid})
CREATE (a)-[r:send_to]->(b) SET r = row.props

// wipe, repeated until deleted = 0 — version-independent, no CALL … IN TRANSACTIONS
MATCH (n:CorpusNode {corpus_id: $corpus_id}) WITH n LIMIT $batch_size DETACH DELETE n RETURN count(*) AS deleted
```

`store/neo4j_settings.py`:
- `Neo4jSettings(uri, username, password: SecretStr, database="neo4j")`;
- `from_env() -> Neo4jSettings | None` reads `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` and
  `NEO4J_DATABASE`, and returns `None` if any of the first three is missing.

~~No `.env` file and no `python-dotenv`: the user sets the variables in the shell.~~ *(revised 2026-09-26, as built in T7: real environment variables take precedence, otherwise a git-ignored `.env` at the repo root is read with `python-dotenv`; `Neo4jSettings` holds the password as `SecretStr`.)* The password never
appears in output or `repr`.

`store/neo4j_loader.py`: `load_corpus(settings, plan) -> LoadReport`. Its steps are wipe → schema → nodes →
relationships → verify. There is one managed write transaction per statement, using the official `neo4j`
driver, added with `uv add neo4j`, version as resolved by uv. **Verify** counts labels and relationship
types for `corpus_id` and raises on any mismatch with `expected_*`. This check is the loader's accuracy
against ground truth.
```python
class LoadReport(BaseModel):
    corpus_id: str; nodes_written: int; relationships_written: int; batch_size: int
    wipe_s: float; schema_s: float; nodes_s: float; relationships_s: float; verify_s: float; total_s: float
    neo4j_version: str | None            # from CALL dbms.components(), for the run note
```

### 7.5 Size at SMOKE-02 — arithmetic, not measurement

This is derived from the SMOKE-02 counts at `duplication_rate=0.0`, where every cross-sheet edge is cut
(`test_splitter.py:56–66`):
- **Occurrences:** 43,043 + 2 × 18,048 = **79,139**. With 4,015 sheets and 1 set, that is **83,155 nodes**.
- **Relationships:**
  - topology (47,405 − 18,048) + 2 × 18,048 = 65,453;
  - `is_drawn_on` 79,139;
  - `has_sheet` 4,015;
  - `continues_as` 18,048;
  - total **166,655**.

The load time is **unmeasured**.

*(revised 2026-09-26, ADR-0017)* These counts are for **budget 4**. K-NEO now uses budget 16 (§7.6). There
the same 2,900 units give fewer sheets and far fewer connector pairs, so the store is smaller than
above. The plant's own 43,043 nodes and 47,405 edges do not depend on the budget. The budget-16 sheet and
pair counts come from SMOKE-06 (T4b), and this arithmetic is redone from them. No budget-16 figure is
written here before that run.

### 7.6 Kill threshold K-NEO (set 2026-09-26, before the first measurement; amended 2026-09-26, ADR-0017)

> ~~**K-NEO fires if** loading the SMOKE-02-size corpus (2,900 units, budget 4, seed 0, `SplitConfig`
> defaults) …~~
>
> *(revised 2026-09-26, ADR-0017)* **K-NEO fires if** loading the SMOKE-02-size corpus (**2,900 units,
> `flow_greedy` with the depth-first `_flow_order` (T4b), budget 16, seed 0**, `SplitConfig` defaults
> otherwise) into a database with no other corpus takes **more than 600 s** by `LoadReport.total_s`, or
> fails (out of memory, transaction error, or the verify mismatch persists). **At most one** batch-size
> change is allowed before the verdict.

- **The amendment precedes any measurement.** No Neo4j load has run: no DBMS exists yet (open question 3),
  and SMOKE-05 has not run. Only the split changes, to ADR-0017's headline configuration. The 2,900 units
  and the 600 s stay. At budget 16 this corpus is the H1000 headline corpus (ADR-0017: ≈ 2,900 units
  ≈ 1,000 sheets, a linear estimate), which is what ADR-0017's revisit clause "H1000 fails K-NEO" refers to.

- **Why 600 s.** It is the same budget as the generation kill criterion (`plant-generator.md` §2, the one
  SMOKE-01/02 were judged on). A corpus is loaded once per EXP-0002 scale point, not once per question, so
  600 s per point is affordable. Anything above that means the load dominates the pipeline it serves.
- **Fallback 1** (ADR-0010 and the phase plan): non-Cypher strategies run on `Resolution.plant` and the
  localized sheets in networkx. Neo4j is loaded only at the sizes that pass, and CypherRAG is reported only
  there. The missing points are stated as an engineering limit, **not** as evidence for the claim.
- **Fallback 2:** `neo4j-admin database import` (D3), trying one size at a time.
- **Recording:** the verdict goes into a run note, **SMOKE-05**, in `30-experiments/`, in the SMOKE format.

### 7.7 Tests

- **Without Neo4j** (`tests/test_neo4j_plan.py`), on a 4-unit plant at dup 0.5:
  - every label in the queries comes from `labels_for`;
  - no row carries `stream_kind` or a key outside V plus `uid` and `corpus_id`;
  - the `uid` values are unique;
  - `expected_*` equal counts taken independently from the sheets and the resolution;
  - batches split at `batch_size`;
  - every wipe query contains `corpus_id: $corpus_id` and no statement is `MATCH (n) DETACH DELETE n`;
  - `Neo4jSettings.from_env` returns `None` when the variables are absent, and `repr` hides the password.
- **Opt-in integration test** (`tests/test_neo4j_integration.py`): the whole module is skipped unless
  `NEO4J_URI`, `NEO4J_USERNAME` and `NEO4J_PASSWORD` are set. It loads a 4-unit corpus as
  `corpus_id="pytest-kg-construction"`, verifies, loads again (idempotent, same counts), and wipes it in a
  `finally`. It touches no other corpus.
- **Recommend to the user:** a dedicated DBMS for this project.

## 8. CLI — `python -m plantgraph.ingest`

This uses `python -m`, the convention of `scale_smoke` and `open100`, with no new `[project.scripts]`.
Package `src/plantgraph/ingest/`:
- `pipeline.py` holds pure orchestration: `run_synthetic(...)` and `run_proteus(...)` return `IngestResult`.
- `__main__.py` holds argparse only.

```
python -m plantgraph.ingest synthetic --n-units N --budget B --seed S
       [--duplication-rate R] [--label-detail full|drawing_only] [--variant-tags]
       [--numbering sequential|pid_style] [--grid] [--corpus-id ID] [--batch-size K]
       [--no-neo4j] [--check]
python -m plantgraph.ingest proteus PATH [--sheet-id X] [--plant-id P] [--corpus-id ID] [--no-neo4j]
```
- **Output:** one JSON `IngestResult` on stdout, in the `scale_smoke` style. It contains the sizes, the
  `perf_counter` stage timings, the `ResolutionReport`, the `ImportReport` (proteus), the `LoadReport` and,
  with `--check`, `gate_equal`, the first differences and a `ResolutionScore`.
  - synthetic stages: `generate`, `split`, `localize`, `resolve`, `check`;
  - proteus stages: `import`, `localize`, `resolve`.
- **`--check`** exits 1 if G1 fails.
- **Neo4j:** without `--no-neo4j`, a missing environment variable is an error that names the three variables.
- **Default `corpus_id`:** `syn-u{N}-b{B}-s{S}` or the file stem, sanitized.

## 9. Files and dependency rules

```
src/plantgraph/adapters/pydexpi_io.py            + load_proteus
src/plantgraph/adapters/pydexpi_adapter.py       map_conceptual_graph signature; tolerant valve units
src/plantgraph/adapters/pydexpi_proteus_import.py  new
src/plantgraph/adapters/pydexpi_generic.py       new (revised 2026-09-26, ADR-0016; §3.1)
src/plantgraph/graph/schema.py                   + GenericItem, OTHER, IMPORTABLE_CLASSES, related_to (ADR-0016)
src/plantgraph/benchmark/strategies.py           _flow_order depth-first (revised 2026-09-26, ADR-0017)
src/plantgraph/benchmark/models.py               + MatchRule.CONNECTOR_NUMBER
src/plantgraph/resolution/{__init__,contract,localize,connector_labels,pairing,identity,merge,models,resolver}.py
src/plantgraph/eval/{__init__,graph_equality,resolution_scoring}.py
src/plantgraph/store/{__init__,neo4j_plan,neo4j_settings,neo4j_loader}.py
src/plantgraph/ingest/{__init__,__main__,pipeline}.py
```
Dependency rules:
- `resolution` → `benchmark.models`, `benchmark.sheet_graph`, `graph.schema` only.
- `eval` → `resolution`, `benchmark`.
- `store` → `resolution`, `graph.schema`; the `neo4j` driver only in `neo4j_loader.py`.
- pyDEXPI only in `adapters/pydexpi_*`.

## 10. Coder task list (one Sonnet coder at a time, in order; every task ends with the full suite, ruff and mypy --strict green)

| # | Task | Acceptance |
|---|---|---|
| **T1** | Importer (§3): `load_proteus`, the `map_conceptual_graph` signature change (both call sites), the tolerant valve-unit line, `pydexpi_proteus_import.py`, tests | the §3 tests pass, including the EX01 figures when the file is present; `pydexpi_adapter.py` ≤ 400 lines; the existing adapter and scale-smoke tests unchanged and green |
| **T2** | `resolution/contract.py` and `resolution/localize.py` (§4.3) | a 4-unit plant at dup 0.5: raw split output fails `check_contract` naming the shared id; `localize` output passes; the `OccurrenceMap` is a bijection; a different salt gives disjoint ids; no G property survives; `connectors == []` |
| **T3** | `ConnectorLabel`, `read_connector_labels`, `pair_connectors`, `MatchRule.CONNECTOR_NUMBER` (§5.1–5.2) | on localized sheets at defaults, the pairs mapped through `OccurrenceMap` equal `manifest.connector_pairs` (unordered); at `DRAWING_ONLY` every connector is paired or unresolved and every pair is in the manifest |
| **T4** | `identity.py`, `merge.py`, `models.py`, `resolver.py`, `eval/graph_equality.py`, the import-ban test (§5.3–5.7) | G1, G2 and G4 pass in pytest on the grid in §5.6; `resolve` on the imported EX01 sheet returns 23 nodes and 0 pairs (skip if the file is absent) |
| **T4b** *(added 2026-09-26, ADR-0017)* | Splitter locality fix (`splitter.md` §3 "Density calibration"): `_flow_order` in `benchmark/strategies.py` becomes an **iterative depth-first preorder** from the feeds. It keeps the sorted tie-break (smallest successor first) and the restart rule for unreached owners, and the docstring says depth-first. It is shared with `by_unit` and `utility_aware`. Nothing else in the splitter changes | (1) the ADR-0017 regression test: on a generated plant, `flow_greedy` cuts fewer edges than `random` at the same budget; (2) a unit test on a hand-built owner graph where the breadth-first and depth-first orders differ asserts the depth-first order (open question 9 says why (1) alone is not enough); (3) every existing strategy, splitter and round-trip test is green, and any changed expected value is named in the hand-off. **Then SMOKE-06**, run by the user or the main session, not the coder: the SMOKE-01/02 configs at **budget 16**, seed 0, 1,000 and 2,900 units. It reports sheets, nodes, **nodes/sheet** (`n_nodes / n_sheets`) and **connector stubs/sheet** (`2 × n_connector_pairs / n_sheets`) against EX01 (36 nodes) and OPEN100 (8.0 stubs/sheet), plus time and memory. It gets a row in `_results.md` and a run note, and ADR-0017's revisit bound (stubs/sheet outside 2–12) is checked |
| **T1b** *(added 2026-09-26, ADR-0016)* | Generic fallback (§3.1): the `schema.py` additions; the two zero-line adapter renames; `adapters/pydexpi_generic.py`; `ImportReport.nodes_per_dexpi_class` and `related_to_collapsed`; update the T1 EX01 tests whose figures change | EX01 (skipped if the file is absent): **36/36 nodes**, `nodes_dropped_per_class == {}`, 11 `GenericItem` and 2 connector nodes; P4712 has `dexpi_labels == ["ReciprocatingPump", "Pump", "Equipment"]` and `category == "equipment"`; **a `send_to` path T4750 → P4712**; `sheet.connectors == []`; `edges_lost_to_unmapped_endpoints == {}`; the accounting invariant holds with `nodes_per_dexpi_class`; `resolve(localize([sheet]))` returns 36 nodes, 0 pairs and both connectors unresolved. If T3's `ConnectorLabel` cannot be built from a connector with no reference label, T1b adds the unresolved reason `"no reference label"` rather than raising (open question 1). Always-on: a hand-built conceptual graph with an unknown equipment subclass, an unknown piping subclass and a label that is not a pyDEXPI class gives the three categories and chains of §3.1; an unknown edge label becomes `related_to`; a chain entry that fails the label regex is rejected. The existing adapter, generator, splitter, round-trip and scale-smoke tests are unchanged and green; `pydexpi_adapter.py` ≤ 400 lines |
| ~~**T1c**~~ **cancelled — ADR-0021** *(added 2026-09-26 by the main session, ADR-0020)* | Imported files keep their DEXPI data attributes as visible node properties: decide the attribute-name whitelist and units from what EX01 actually carries (probe first, list them in §3.1), extend the visible-property set for imported nodes only, keep generated plants unchanged | EX01: the values ChatP&ID's App. Table 1 asks about are present on the right nodes after `localize` (e.g. the cylinder length of T4750, the shaft power of P4711, the nominal diameter of 66KL21, the set pressure of SV 104.01 — exact values read from the file, not from the paper); a generated plant's nodes carry no new property; the contract check passes on both |
| ~~**T1d**~~ **cancelled — ADR-0021** *(added 2026-09-26 by the main session, ADR-0020 scope)* | **Done in T1c:** whitelist and value/unit split live in `adapters/pydexpi_attributes.py` (its module docstring is the authoritative list: 11 quantity attributes split into `{name}_value`/`{name}_unit`, 18 plain ones, exclusions with reasons); 5 of 6 probed ChatP&ID values match the paper exactly. **Remaining gap for T1d:** design temperatures/pressures live on `Chamber` sub-objects, which pyDEXPI's `GraphAbstractor` removes before the adapter runs, so T4750's upper design temperature (100.0 °C in the file, = paper) never reaches the node. Fold each chamber's limits onto its owning equipment node from the complete graph (naming per chamber, never merged or averaged) | EX01: T4750 carries its chambers' upper/lower design temperature and pressure (values read from the file; the paper's knowledge-inference reference cites T4750 chamber pressures 0.1 / 0.05 bar and H1007 chamber design temperature 100 °C — report matches, do not force); generated plants gain no property |
| **T5** | `eval/resolution_scoring.py` (§6) | the hand-built cases pass; G3 is expressed as `score_resolution(...)` = 1.0 at defaults *with `duplication_rate=0.5`* (at the true default 0.0 no identity groups exist, so identity scores are `None` — corrected 2026-09-26 after T5); precision 1.0 at `DRAWING_ONLY` |
| **T6** | `store/neo4j_plan.py` (§7.4), no driver | the §7.7 no-Neo4j tests pass |
| **T7** | `uv add neo4j`; `neo4j_settings.py`, `neo4j_loader.py`, the opt-in integration test | the suite is green with the variables unset (integration skipped); when the user sets them, the integration test passes twice in a row |
| **T8** | `ingest/` CLI (§8) | `--no-neo4j --check` on 4 and 25 units exits 0 and prints valid `IngestResult` JSON; `proteus data/external/C01V04-VER.EX01.xml --no-neo4j` prints the import report with 3 violations; a pipeline test calls `run_synthetic` without Neo4j |

**Runs after T8, done by the user or the main session, not by the coder:**
- **SMOKE-04:** G1 and G3 at 1,000 and 2,900 units, dup 0.0 and 0.5.
- **SMOKE-05:** the first Neo4j load at SMOKE-02 size, judged against K-NEO.
- Both get run notes in `30-experiments/`.
- *(revised 2026-09-26, ADR-0017 rule 4)* SMOKE-04 and SMOKE-05 use the new split configuration (budget 16,
  depth-first `_flow_order`). SMOKE-06 (T4b) has the next free id but runs first. SMOKE-01…03 stay the
  record for time, memory and round trip only.

**Cut line if Phase 2 slips.** After T4 the resolved graph exists in memory, so P4's non-Cypher strategies
can start. T5 is needed by EXP-0004 (P5) and can move there. The G3 check already lives in T3's test.
*(revised 2026-09-26, ADR-0016/0017)* **T4b goes before T1b.** Every corpus the pilot splits (qa-system
CP1, 2026-10-04) and every headline corpus depends on T4b. T1b blocks only EXP-0001 (P3). Neither can be
cut: T4b is ADR-0017's gate, and T1b is ADR-0016's gate before EXP-0001.

**Deferred, not tasks:**
- the oracle `Resolution` from the manifest (ADR-0010 decision 3; only if G1 fails on a corpus);
- the OPEN100 `ConnectorObservation → ConnectorLabel` adapter (P5);
- `is_located_in`;
- the merged-view load (D2-c).

## 11. Which part of the claim it serves

The crossover (EXP-0002) varies corpus scale over a graph that the pipeline **built from sheets**. This
phase makes that graph exist, proves it equals the ground truth (G1, SMOKE-04), and prices storing it at
scale (K-NEO, SMOKE-05). The importer makes EXP-0001 enter by the same door, so the single-sheet and
plant-scale arms differ in scale only.

## Open questions and unverified points

1. ~~**EX01 fidelity is a P3 blocker, not a P2 one.** … Before EXP-0001, an ADR is needed on extending the
   importer's class mapping (a generic pass-through class, or new schema classes). That ADR is not decided
   here.~~ *(revised 2026-09-26, ADR-0016)* **Decided: U3 with no promotions** (§3.1, T1b). Its gate (36/36
   nodes, T4750 → P4712 as a `send_to` path) must pass before EXP-0001. What stays open:
   - a. **The revisit trigger fires on EX01 itself.** Generic nodes are 11 of 36 ≈ 31 % (§3.1), above
     ADR-0016's "about 25 %". The ADR does not say whether EX01 counts as "some real file". The user should
     decide whether this needs a follow-up ADR or an outcome-log note on ADR-0016.
   - b. **EX01's two connectors carry no reference label** until the ADR-0009 "Unverified" mapping is done.
     `ConnectorLabel` (§5.1) requires `connector_number` and `referenced_drawing_number`, and
     `read_connector_labels` raises unless a stub has exactly one incident edge. Whether EX01's connectors
     have exactly one edge is **unverified**. T1b must make `resolve` report them as unresolved, not crash.
   - c. That P4712's and T4750's `tagName` values are exactly `"P4712"` and `"T4750"` is **unverified**.
     ChatP&ID's question text uses these tags.
   - d. *(decided 2026-09-26: ADR-0020, then superseded the same day by ADR-0021 — no equipment data anywhere; T1c/T1d cancelled; only identifiers such as `piping_component_name` are kept)* **R5 of `qa-system.md` is not delivered by any task here.** The importer keeps `node_class`, `tag`
     and `plant_id` only, and `localize` strips anything outside V. EX01's data attributes (the ones
     ChatP&ID's graph-query questions ask about) therefore never reach the store. Under ADR-0018 (A1),
     EXP-0001 on EX01 is the only place attribute questions exist, so this gap decides whether those rows
     are answerable (qa-system OQ2).
2. The ChatP&ID 212 → 53 gap against our 214 → 36 is unexplained (ADR-0009 outcome log). Whether this file
   is ChatP&ID's `DEXPIEX01.xml` is supported, not proven.
3. **Neo4j:** no DBMS exists yet, so its version and edition are unknown. The constraint and index syntax in
   §7.4 is the Neo4j 5 form and must be checked on it. The driver version is left to uv. Load time is
   unmeasured.
4. The equipment-only Proteus round trip (T1 test): whether pyDEXPI's exporter preserves ids that give the
   same node count is **unverified**.
5. `data/external/C01V04-VER.EX01.xml` is untracked, and the file's licence is not checked. It comes from
   pyDEXPI's GitHub `data/`. Until the user decides whether to commit it, the EX01 tests skip on any other
   machine, including the professor's.
6. The pairwise-F1 citation for identity scoring is owed (§6).
7. `batch_size = 5000` and the choice of the `tag` index are unmeasured starting points.
8. **ADR candidates.** D1 and D2 implement the already-reviewed `plant-generator.md` §4.3–4.4, so no new
   ADR is proposed. D3 is conventional. An ADR becomes necessary if the retrieval design wants D2-c, or
   for open question 1. *(revised 2026-09-26: open question 1 is now ADR-0016.)*
9. *(added 2026-09-26, ADR-0017)* **ADR-0017's regression test does not catch the bug it guards.** By
   ADR-0017's own diagnostic, pre-fix `flow_greedy` already cuts fewer edges than `random` (6,162 vs 6,230 at
   budget 4, and 6,099 vs 6,220 at budget 16, 1,000 units). "`flow_greedy` < `random`" therefore passes on
   the breadth-first code too. T4b adds a direct order test on a hand-built graph. A threshold such as
   "`flow_greedy` cuts at most x % of `random`" would catch it at scale, but any x would be invented until
   SMOKE-06 has measured the ratio.

**Built vs. designed (main session, 2026-09-26).** The T8 CLI implements a minimal flag set (`synthetic --n-units --budget --seed --strategy --corpus-id --check --no-neo4j`; `proteus PATH --corpus-id --no-neo4j`); the fuller list in §8 (`--duplication-rate`, `--label-detail`, `--numbering`, `--grid`, `--batch-size`, `--sheet-id`, `--plant-id`) is not built and can be added additively when a task needs it. Since T1b, EX01 imports 36 nodes (T4's "23 nodes" is the pre-T1b state) and reports 7 `duplicate_tag` violations, not 3. `neo4j_loader.wipe_corpus` exists for cleanup without a load (T7).
