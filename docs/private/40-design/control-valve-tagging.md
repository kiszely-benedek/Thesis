---
component: control-valve tagging in the generator (who carries the loop's `{var}V-u-n` tag), and what follows downstream
status: draft — awaiting user decision (ADR-0044 proposed)
related: [ADR-0044 (proposed), ADR-0040 (rejected/superseded), ADR-0041 (primer), ADR-0027 (signal-connector loop_tag), ADR-0035 (sealed held-out), ADR-0039; plant-generator.md §3.3; plant-graph-first-and-effort-routing.md §B.3, §C.3; pid-primer-v1.md]
date: 2026-10-04
author: architect (Opus 5.5)
---

# Design — the control valve carries the loop's valve tag

## 0. Recommendation

**Option A-i.** The operated valve that a loop moves carries the loop's `{var}V-{unit}-{loop}` tag (e.g. `FV-30-6`).
The `ActuatingFunction` (the actuator) carries **no tag**, as the actuator symbol on a P&ID carries none of its own.
The DEXPI `ActuatingSystem` gets `actuatingSystemNumber = FV-30-6`, as in the DEXPI reference example. The question
text, reference function, scoring and topology stay as they are. Only tag strings change.

| | Before | After (A-i) |
|---|---|---|
| valve body (`GlobeValve`/`BallValve`) under a loop | `GV-30-4` (its own minted tag) | `FV-30-6` |
| `ActuatingFunction` | `FV-30-6` | no tag (`loop_tag`, `measured_variable` unchanged) |
| `ActuatingSystem.actuatingSystemNumber` (DEXPI only, not a graph node) | unset | `FV-30-6` |
| controller, transmitter, loop function, valves without a loop | unchanged | unchanged |
| node ids, edges, sheets, `k`, connector `loop_tag` | — | identical (tags consume no RNG) |

Two coder tasks (§6), both small. After them, the main session runs the free checks again (§8).

## 1. Link to the claim

A benchmark question with two defensible answers measures the scorer, not the retrieval strategy
(plant-graph-first-and-effort-routing.md §1, P6). Fixing the naming in the data keeps the question natural, which is
the user's binding rule. The fix is the same for every strategy and representation, so it cannot move one arm
against another. That is why it belongs in the data, not in a renderer (option B).

## 2. Evidence

### 2.1 Code (read 2026-10-04, HEAD `8d00a17`)

| # | Fact | Where |
|---|---|---|
| C1 | Valves get their tag when streams are built (step 4). Loops are added after that (step 5). | `benchmark/generator.py:41-46`, `:228-238`, `:250-278` |
| C2 | The builder writes `FV-u-n` into `ActuatingFunction.actuatingFunctionNumber`. The valve keeps `pipingComponentNumber = GV-…`. `ActuatingSystem` gets no number. | `adapters/pydexpi_builder.py:179-183`, `:190-192`, `:219-226` |
| C3 | The importer reads a valve's tag from `pipingComponentNumber` and an actuator's from `actuatingFunctionNumber`. It always writes a `"tag"` key, even when the value is `None`. | `adapters/pydexpi_adapter.py:186`, `:210-225` |
| C4 | `loop_tag` = the controller's tag. It is written onto the controller and the instrument nodes next to it (sensor, actuator), never onto the valve. | `adapters/pydexpi_adapter.py:388-400` |
| C5 | A signal cut's connector `loop_tag` = the source's `loop_tag`, else the target's. For actuator → valve the source is the actuator. | `benchmark/connectors.py:126-132` |
| C6 | Identity grouping (`SAME_TAGGED_ITEM_AS`) and inexact tag variants cover equipment only. | `resolution/identity.py:34-55`; `benchmark/splitter.py:172-193` |
| C7 | Validation requires `tag` on every plant node and on every non-connector sheet node, and reports duplicate tags. | `graph/validation.py:39`, `:67`, `:106`, `:146-155` |
| C8 | `LOOKUP_TYPE` and `LOOKUP_UNIT` take every tagged node, actuators included. Today "What type of item is FV-30-6?" has the reference `ActuatingFunction`, which is the same ambiguity in another family. | `qa/questions/families_lookup.py:47`, `:76`; `common.py:23-34` |
| C9 | The absent tags for `UNANSWERABLE_TAG` are formed per (prefix, unit) over equipment and valve tags. | `qa/questions/families_abstain.py:43-73` |
| C10 | `evidence_tags` reads `plant.nodes[n]["tag"]` for every evidence node. Evidence-node recall compares tags. `evidence_sheets` and `k` use node ids. | `qa/questions/evidence.py:164-174`; `qa/harness/routing_gold.py:112`, `:120-127` |
| C11 | API-01 reads the gold side with `plant.nodes[x]["tag"]`. The item side already maps a missing tag to `<untagged>`. | `qa/harness/api_fidelity.py:24`, `:67-79`, `:147-157` |
| C12 | The canonical program for the family walks 2 signal hops from the controller and keeps valve-labelled tags. `_tags_where` skips `None` tags. | `qa/harness/canonical_programs.py:47-53`, `:86-89`, `:178-186` |
| C13 | The rules need-classifier matches wording only (`actuated`, `control loop`). Tags play no part. | `qa/need/rules.py:70-73` |
| C14 | The schema text and the occurrence legend say "Connector nodes have no tag". Both legends describe the chain `actuator -control-> valve`. | `qa/schema_text.py:43`; `qa/prompts/legend_occurrence.txt:1`, `legend_plant.txt:1` |
| C15 | The primer says V = valve. | `qa/prompts/primer_pid_v1.txt:9` |
| C16 | `question_id` is built from family and anchors. When an anchor tag changes, the id changes. | `qa/questions/common.py:121`, `:160` |

### 2.2 Realism sources

| # | Claim | Source | Status |
|---|---|---|---|
| R1 | With the letter V in third place, the tag names a **valve**. | DOE-HDBK-1016/1-93, Module 2, p. 6: "The third letter is a 'V' to indicate that the piece of equipment is a valve." | verified (pid-primer-v1.md §3, B9) |
| R2 | A control valve in a pressure loop is tagged PV. In the ISA-5.1 letter table, succeeding letter V = "Valve, Damper, Louver" and Z = "Driver, Actuator, Unclassified final control element". | *Control Loop Foundation: Batch and Continuous Processes*, ISA, Ch. 7, p. 105, Fig. 7-9 ("Excerpt" of ISA-5.1); text: "A control valve used in pressure control would be identified using the letters PV, pressure valve." | verified 2026-10-04: text extracted from the ISA-hosted chapter PDF. Authors (Blevins, Nixon) recalled, not on the pages read |
| R3 | Example P&IDs print **one** tag per control valve (e.g. `FV 101`, `AV 103`, `PV 115`) with the fail action next to it. No actuator tag is printed. The actuator is drawn as part of the valve symbol. | same book, Fig. 7-16 (p. 111), Figs. 7-17 to 7-19 (pp. 113-115); p. 107: "A complete representation of the valve is provided by combining the valve representation with the actuator representation." | verified 2026-10-04 (as R2) |
| R4 | In the DEXPI reference P&ID, the printed number of a control valve is the `ActuatingSystem`'s (`PV4712.02`, a label at 90°). The `ActuatingFunction` number is the same string. The valve body has no label, and its `PipingComponentNumber` is the segment position `C1`. The actuator is identified only by the sub-tag `PV4712.02_YC` and the valve reference by `PV4712.02_YV` (data, not printed). | `data/external/C01V04-VER.EX01.xml`: lines 63, 76 (AS label and number), 103 (`_YC`), 118 (`_YV`), 120 (refers to `GlobeValve-1`), 2393 (AF number), 1849-1891 (`GlobeValve-1`: no `ValveLabel`, number `C1`). A hand valve for contrast: `BallValve-1` has `ValveLabel` "73KH12-50" (line 748) | verified 2026-10-04 (read in the repo) |
| R5 | The ChatP&ID reference answers name control valves by that number: "Shut the main DN80 feed globe valve (HV4750.01)", "globe valve on the recirculation line (PV4712.02)", "HV4750.01 (Globe Valve)". | arXiv:2603.22528v1, App. Table 1, p. 33, transcribed in `data/external/chatpid_ex01_qa.jsonl` lines 12, 14, 15 | verified (transcription in repo) |
| R6 | A valve plus an actuator is "commonly called a control valve". | DOE-HDBK-1016/1-93, Module 2, pp. 4-5 | verified (primer B5a) |

What R1–R6 together say: a reader, an ISA-trained engineer, the DEXPI reference model and the published
benchmark all call the control valve `FV-…`. The generator gives that name to the actuator and a second, unrelated
name to the valve body. That is the defect. The models are not wrong.

**Not found:** no source read shows an actuator printed with a tag of its own (e.g. `FZ-…`) on a P&ID. ISA-5.1's
letter Z exists (R2), but how it is used on P&IDs was not seen.

## 3. Options

| | What | Realism | Cost and risk | Verdict |
|---|---|---|---|---|
| **A-i** | valve ← `FV-u-n`; actuator untagged; AS number ← `FV-u-n` | best match with R3, R4 (one printed tag per control valve) | ~9 files, each a small edit (None-safety + naming). Evidence-node recall no longer sees the actuator, because it has no tag | **chosen** |
| A-ii | valve and actuator both `FV-u-n` | matches R4's data (AF number = AS number) | breaks tag uniqueness (`validation.py:146`), and every tag-keyed join (API-01, routing gold, anchors) becomes ambiguous | no |
| A-iii | valve ← `FV-u-n`; actuator ← `FZ-u-n` | the letter is sourced (R2); no source shows an actuator printed with such a tag | smallest change: everything stays tagged and unique | fallback if the user wants the least code |
| B | keep the tags; contract actuator + valve into one item in `ItemGraph` | none; the data stays unrealistic | fixes only plant arms. Occurrence, Cypher and ContextRAG arms keep the ambiguity, so the representation comparison (Q7) gets a naming confound | no |
| C | primer-only: "the actuator carries the loop's V tag" | contradicts R1–R4: a rule invented to fit the generator | — | no (user rule 3) |
| D | accept the actuator's tag as correct, or move the reference to it | — | the answer is no longer unique, or the valve's own tag becomes "wrong" (ADR-0040 option B) | no |
| E | reword the question | — | rejected by the user (ADR-0040) | no |

## 4. Design of A-i

### 4.1 Generator and DEXPI model

- **One formula, one place.** `benchmark/generator_models.py` gets
  `def control_valve_tag(variable: str, unit_no: int, loop_no: int) -> str` returning `f"{variable}V-{unit_no}-{loop_no}"`.
  Both builders use it. The `LoopSpec` docstring (`:106-114`) is updated: the backend computes the controlled
  valve's tag, not an actuator tag.
- `DexpiPlantBuilder.add_control_loop` (`pydexpi_builder.py:153-204`):
  - `valve.pipingComponentNumber = control_valve_tag(...)`. The valve object is already in its segment, so the
    assignment shows in the model. Assignment on these objects is already used at `:192`.
  - `ActuatingFunction(id=…, parentStructure=…)` without `actuatingFunctionNumber`. All pyDEXPI 1.2.0 fields are
    optional (checked: `actuatingFunctionNumber: str | None`, not required).
  - `ActuatingSystem(id=…, actuatingSystemNumber=control_valve_tag(...), operatedValveReference=…)`.
- `tests/graph_plant_builder.py:85-131` (the offline builder): the valve node's `tag` becomes
  `control_valve_tag(...)`, and the actuator node has no `tag` key.
- `graph/schema.py:166-170`: the `ACTUATING_FUNCTION` `tag_prefix` becomes `None`. Add
  `UNTAGGED_CLASSES: frozenset[str] = CONNECTOR_CLASSES | {NodeClass.ACTUATING_FUNCTION.value}`. Its docstring
  cites R3/R4: the actuator symbol shares the control valve's printed tag.
- **Minting is unchanged.** The valve still draws `GV-30-4` in step 4 and is renamed in step 5, so later sequence
  numbers do not move. Its unit's `GV` sequence then has a gap. No source read says anything about such gaps, and
  nothing in the generator reads them.
- **What is invariant:** tags consume no RNG (`generator.py:289-297`), and the splitter reads tags only for
  duplicated equipment (`splitter.py:172`). So node ids, edges, sheet membership and `k` must be identical to
  `8d00a17`. A test asserts this (§7, T-G1).
- `plant-generator.md` §3.3 "Ids and tags" (line 207) carries a pointer to ADR-0044.

### 4.2 Importer and validation

- `pydexpi_adapter._map_nodes` (`:186`): write `"tag"` only when `_tag_of` returns a string. A node without a
  printed tag then looks like a connector does today: no key. This also matches what `tagged_nodes_by_tag`
  (`"tag" in data`) and `routing_gold.py:62` already assume.
- **EX01 caution:** the Proteus path shares `_map_nodes`. The acceptance test checks that the EX01 serialized
  context is byte-identical (PROMPT-03: 17,693 chars, and its hash). If an EX01 node had `tag: None` and the
  serializer printed it, the test shows it, and the coder stops and reports.
- `validation.py:39`, `:106`: `tag` is not required for `UNTAGGED_CLASSES`. The duplicate check is unchanged.
  Duplicates cannot arise: `FV-30-6` is unique, because loop numbers are unique per unit (`generator.py:299-303`)
  and no minted prefix is `{var}V`.

### 4.3 Resolver, identity, connectors

- Nothing changes. `SAME_TAGGED_ITEM_AS` and tag variants cover equipment only (C6). Signal connectors still take
  the actuator's `loop_tag` (C4, C5, ADR-0027), and pairing keys (`resolution/pairing.py:24`, `:169`) are unchanged.

### 4.4 Questions and gold

| Family | Effect |
|---|---|
| LOOP_ACTUATED_VALVE | text and `question_id` unchanged (anchor = controller tag); **reference** `GV/BV-u-s` → `{var}V-u-n` for every question; `evidence_tags` loses the actuator |
| LOOKUP_TYPE, LOOKUP_UNIT, identity families over tagged nodes | actuator candidates disappear (fixes C8); questions anchored on a controlled valve are renamed (new `question_id`) |
| NEIGHBOURS_*, FLOW_PATH, CONNECTED, isolation, reach families | references and anchors that contain a controlled valve change string; topology unchanged |
| LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, INSTRUMENTS_OF_ITEM | references unchanged (controller, equipment and sensor tags); evidence tags change |
| UNANSWERABLE_TAG | new (`FV`/`LV`/`PV`/`TV`, unit) groups yield extra absent tags such as `FV-30-7` (`families_abstain.py:43-73`). That is a realistic "does this loop valve exist?" probe. Each unit's GV/BV group may get a different absent tag |
| COUNT_IN_UNIT, CROSS_UNIT | unchanged (class-based) |
| sealed held-out families | regenerated from the new corpora at unseal. Never opened here (ADR-0035) |

- `qa/questions/evidence.py:172-174`: `evidence_tags` skips nodes without a tag, and the docstring says so.
  Evidence-node recall is therefore measured over tagged evidence nodes. For a loop question that is the
  controller and the valve. Whether the actuator was in the context is still visible through `evidence_sheets`
  (node ids) and PG-T3's evidence-edge hops.
- `qa/harness/api_fidelity.py:79`, `:147-157`: the gold side uses `.get("tag")`, with `_UNTAGGED` for edges and a
  skip for items, mirroring the item side. API-01's edge set stays exact: an untagged actuator's edges are still
  told apart by their tagged other end (controller, valve).
- **Canonical programs:** no change (C12). After A-i they return `FV-30-6`.
- **Need classifier:** no change (C13).

### 4.5 Model-facing text

- `qa/schema_text.py:43` and `legend_occurrence.txt`: "Connector nodes have no tag." → "Connector and actuator nodes
  have no tag." `legend_plant.txt`: add "Actuator nodes have no tag." after the chain sentence. These state what is
  in the representation, like the existing connector sentence, and are not domain hints. Prompt hashes change on
  purpose. Legends are not frozen before F1.
- **Primer: no change.** Line 9 (V = valve) now agrees with the data. This closes the tension noted in
  plant-graph-first-and-effort-routing.md §C.3.

### 4.6 A consequence to report: the answer follows convention

After A-i, every loop's valve tag is formed from the loop tag's letter and number: `FIC-30-6` → `FV-30-6`. This
holds by construction. A reader who knows ISA conventions can answer without retrieval, and so can a real engineer
on a real plant (R2, R3). Split-range loops (two valves per loop, `FV301A`/`FV301B`, ISA book p. 95) would break
this, but no source read gives how often they occur. Adding them would mean inventing a rate, so they stay out.
The test suite proves the property (T-Q3). How the family is reported is decision U2.

## 5. What changes per corpus

D100, D1000 (dev) and H100, H1000 (test, H1000 headline) are all regenerated from their seeds:
- **Same:** node ids, edges, sheets, connectors and their `loop_tag`, `PlantSummary` counts, `k` of every question.
- **Different:** the tag of every controlled valve; actuators lose their tag; DEXPI JSON bytes (invariant 9 holds
  run to run, but differs from `8d00a17`); question sets and `question_set_sha256` for every corpus. The PAID-01
  slice hash `0107b9e5…` no longer reproduces, and the new hash is recorded.
- **Neo4j:** the one stored plant is wiped and the new H100 loaded (one-plant rule).
- **History:** PAID-01…04 and PG-P1 stay in `_results.md` as runs on the old naming. Each gets a note: "naming
  before ADR-0044; LOOP_ACTUATED_VALVE and LOOKUP_* rows not comparable with later runs."

## 6. Coder tasks (one Sonnet coder at a time; each green on ruff, mypy --strict, pytest, offline)

| # | Task | Files | Size | Depends |
|---|---|---|---|---|
| **CV-T1** | **None-safety first, no behaviour change.** `UNTAGGED_CLASSES` in schema; validation exempts it; `_map_nodes` omits a `None` tag; `evidence_tags` skips untagged; API-01 gold side `.get`. Every existing test stays green because no generated node is untagged yet. EX01 golden check | `graph/schema.py`, `graph/validation.py`, `adapters/pydexpi_adapter.py`, `qa/questions/evidence.py`, `qa/harness/api_fidelity.py`, tests | S (~40 lines + tests) | — |
| **CV-T2** | **The naming change.** `control_valve_tag`; both builders; AS number; AF untagged; AF `tag_prefix` → `None`; schema-text and legend sentences; `plant-generator.md` pointer is already in place | `benchmark/generator_models.py`, `adapters/pydexpi_builder.py`, `tests/graph_plant_builder.py`, `graph/schema.py` (one line), `qa/schema_text.py`, `qa/prompts/legend_occurrence.txt`, `qa/prompts/legend_plant.txt`, tests and goldens | S–M (~30 lines + tests + golden updates) | CV-T1 committed |

Collision: both touch `graph/schema.py` (CV-T1 adds the set, CV-T2 edits the AF `tag_prefix`), so they run in
sequence. CV-T1 has to land first, or CV-T2's pytest would raise `KeyError` on the untagged actuator in
`evidence_tags`. The legends CV-T2 edits were last changed by PR-T1, which is already committed (`8d00a17`), so
nothing collides with it.

## 7. Tests to add

| Id | Task | Test |
|---|---|---|
| T-V1 | CV-T1 | validation: a plant with an untagged `ActuatingFunction` passes; an untagged `GlobeValve` still fails `missing_property` |
| T-V2 | CV-T1 | `_map_nodes`: a node whose `_tag_of` is `None` has no `"tag"` key; EX01 serialized context equals its recorded hash (PROMPT-03 length 17,693) |
| T-V3 | CV-T1 | `evidence_tags` on an evidence set with an untagged node returns only the tagged ones, never `"None"` |
| T-V4 | CV-T1 | API-01 on a toy with untagged actuators: edges P = R = 1.0; one injected edge change is detected |
| T-G1 | CV-T2 | **structural invariance:** for seeds 0–4 (and the headline preset at n_units 5), the sorted node ids, edges with relations and per-sheet node-id sets equal a golden recorded at `8d00a17` **before** the edit (the coder records it first) |
| T-G2 | CV-T2 | every `control` edge ends at a valve whose tag is `control_valve_tag(var, unit, loop)` of its loop; no `ActuatingFunction` has a `tag`; all tags unique; `validate_plant_graph == []`; DEXPI `ActuatingSystem.actuatingSystemNumber` equals the valve's `pipingComponentNumber` |
| T-G3 | CV-T2 | signal connectors on actuator → valve cuts still carry the controller's `loop_tag` |
| T-Q1 | CV-T2 | LOOP_ACTUATED_VALVE on a toy: text unchanged; reference matches `^[FLPT]V-\d+-\d+$` and equals the valve node's tag; the canonical program returns it |
| T-Q2 | CV-T2 | no generated question (any family) has an anchor or reference that is the tag of an untagged node; LOOKUP_TYPE has no `ActuatingFunction` reference |
| T-Q3 | CV-T2 | documents §4.6: for every loop, reference == controller tag with `IC` replaced by `V` |
| T-P1 | CV-T2 | prompt goldens: only the one legend/schema sentence differs |

## 8. Free checks for the main session after CV-T2 (no model call)

Regenerate the question sets for D100, D1000, H100, H1000 (same seeds and presets), then run:
- **API-01 / API-01b** (H1000): edges P = R = 1.0, item and edge properties all match. The item count falls by the
  number of actuators, which is not known yet and is read from the run.
- **API-02** (H100, H1000): canonical programs = references, per family.
- **NEED-00** (H100): labels per template unchanged; counts change with the sets.
- **ROUTE-01** (all four corpora): routing should move only through question selection; per-family rows recorded.
- **PG-01**: on the regenerated PAID-01 slice, with its new hash recorded.
- **PLANT-01** if it has been run before: the store against the new gold.
Each run gets a `_results.md` row stating "post-ADR-0044 naming".

## 9. Open questions and user decisions

- **U1 (decision):** A-i (untagged actuator, most realistic, two small tasks) or A-iii (`FZ-u-n`, one smaller task,
  a tag no source shows printed). **Recommend A-i.**
- **U2 (decision):** reporting LOOP_ACTUATED_VALVE after §4.6. **Recommend:** keep it in the per-family tables,
  and leave it out of the headline accuracy aggregate as "answerable from the tag convention", decided now,
  before any result on the new naming exists. Alternative: keep it in the aggregate with a footnote.
- **U3 (follow-up, separate ADR before EXP-0001):** our importer tags C01's three control valves `C1` (from
  `PipingComponentNumber`, R4). ChatP&ID's gold calls them `HV4750.01`/`PV4712.02` (R5). An importer rule, "an
  operated valve referenced by an `ActuatingSystem` takes its number as its tag", would make EX01 match the
  published gold. It changes the EX01 graph, so it needs its own decision. **Recommend:** yes, in its own ADR.
- **U4 (information):** the local Neo4j is wiped and reloaded with the new H100.
- **Open:** whether low-effort models now name `FV-30-6` is a paid question. It goes into the next paid step
  already planned (EXP-0006 first stage), with no extra run.

## 10. Sources

- DOE-HDBK-1016/1-93, *Engineering Symbology, Prints, and Drawings*, Vol. 1, Module 2, pp. 4-6 (via the primer's
  verified reading, pid-primer-v1.md §3).
- *Control Loop Foundation: Batch and Continuous Processes*, ISA, Chapter 7 "Control and Field Instrumentation
  Documentation", pp. 95, 105, 107, 111, 113-115.
  https://www.isa.org/getmedia/e122051e-8c8c-48be-97ef-5d344c585771/Chapter7_Control (text extracted 2026-10-04).
- DEXPI reference example C01 (`data/external/C01V04-VER.EX01.xml`), lines cited in R4.
- ChatP&ID, arXiv:2603.22528v1, App. Table 1, p. 33 (`data/external/chatpid_ex01_qa.jsonl` lines 12, 14, 15).
- pyDEXPI 1.2.0 field definitions (`ActuatingFunction`, `ActuatingSystem`), checked in `.venv` 2026-10-04.
