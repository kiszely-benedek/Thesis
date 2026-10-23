---
component: benchmark/splitter
status: draft — awaiting review
related: [ADR-0004, ADR-0001, ADR-0017]
date: 2026-08-25
---

# Design — benchmark splitter

> **Revision pending (2026-09-12).** `plant-generator.md` §5 specifies changes to this design: connector kind
> (pipe vs signal) and visible connector labels, a new `by_unit` strategy, DEXPI class names in
> `equipment_classes`, and `utility_aware` excluded from sweeps. Where the two notes disagree,
> `plant-generator.md` wins until this note is revised. The §3 warning about the professor's documents is
> void (ADR-0007).

Cuts one large plant graph into N sheets, inserting off-page connector (OPC) pairs at every cut edge, and emits the ground truth as a separate artifact. See `docs/Notes/why-a-synthetic-benchmark.md` for why this exists.

## 1. Input and output

**In**
- `plant: nx.DiGraph` — a complete plant graph (from pyDEXPI synthetic generation, via the adapter)
- `config: SplitConfig` — strategy, sheet size budget, seed

**Out**
- `sheets: list[SheetGraph]` — one subgraph per sheet, each with OPC stub nodes replacing cut edges
- `manifest: SplitManifest` — the answer key, serialized to JSON

The splitter emits **graphs, not images.** Rendering to SVG/PDF is a separate component for Phase 5; keeping it out here keeps this module testable and under the line cap.

## 2. Data model

networkx holds topology (fast, standard, what pyDEXPI already produces). Pydantic holds everything that gets **serialized or validated** — config and ground truth. Do not try to model the graph itself in Pydantic; it is the wrong tool for that job.

```
src/plantgraph/benchmark/
    models.py       # Pydantic: SplitConfig, OffPageConnector, ConnectorPair, SheetGraph, SplitManifest
    strategies.py   # partitioning strategies, one function each
    splitter.py     # orchestration: partition → cut → insert OPCs → build manifest
    rejoin.py       # the inverse, used only by tests
```

Key models:

- **`OffPageConnector`** — `tag`, `sheet_id`, `direction` (`outgoing` | `incoming`), `partner_sheet_id`, `partner_tag`, `attached_node_id`
- **`ConnectorPair`** — the ground-truth link: the two connector tags plus `original_edge: (source_node_id, target_node_id)` and its attributes
- **`SplitManifest`** — `source_graph_hash`, `strategy`, `params`, `seed`, `sheets`, `connector_pairs`, `created_at`

`source_graph_hash` and `seed` make every benchmark instance exactly reproducible, which the results table requires.

## 3. Partitioning strategies

**This is the part that decides whether the benchmark is credible.** OPEN100 gives one real reference point (ADR-0004 outcome log) — but **one point is a sanity check, not a calibration target**, and the difference matters.

> ⚠ **Do not fit the generator to OPEN100.** It is a single preliminary nuclear design, one author, one CAD tool, one day, drawn clean rather than scanned, and marked "INFORMATION ONLY – NOT FOR CONSTRUCTION". The professor's factory documents will be older, scanned, multi-author, multi-era, hand-annotated, and quite possibly a different symbol standard and language. A generator tuned to reproduce OPEN100 would produce a benchmark that flatters any system over-fitted to OPEN100 conventions — and that system would then fail on the real documents.
>
> **Use OPEN100 to bound one region of the space, then deliberately generate outside it.** Sheet sizes, connector density and label conventions must all be *variables with ranges*, not constants read off one drawing set. If a downstream component only works when connectors look like `PID 120-1 (C-1)`, that is a bug the benchmark should expose, not hide.

Measured on OPEN100 — treat as one observed sample, not the distribution:

| Property | Measured on OPEN100 (12 real sheets) |
|---|---|
| Nodes per sheet | 181–675, mean **386** |
| Off-page connectors per sheet | **2–12** (96 total) |
| Partition principle | **by system** — Main Steam, Feedwater, Reactor Coolant… (from title blocks) |
| Sheets per system | 1 or 2 — large systems continue onto a second sheet |
| Connector reference format | target sheet + **grid cell** + line number |
| Dangling references | 3 systems referenced but absent (PID 190, 240, 290) |

Generated sheets should be *able* to land in those ranges — and also well outside them. Convention itself is a generator parameter: numbering scheme, label grammar, whether a grid reference exists at all. Downstream components must be tested against conventions they have never seen.

How engineers actually partition drawings — now confirmed by the above, not just convention:
- **By process unit** — a column with its reboiler, condenser, reflux drum and pumps stays on one sheet
- **Sheet order follows process flow** — sheet 1 is feed, later sheets are downstream, so most cross-references point to nearby sheet numbers
- **Utilities get their own sheets** — steam, cooling water, instrument air headers, referenced from many sheets (hub sheets, high degree)
- **Bounded density** — a unit too large spills onto a continuation sheet. ~~roughly 5–15 major equipment items per sheet~~ **Unsourced, struck 2026-09-12:** the researcher's rule sweep (`10-literature/pid-structural-rules.md` §4 and §9) found no source that gives any items-per-sheet number. The sheet budget is a swept parameter, never a calibrated constant; the code default `SplitConfig.sheet_equipment_budget = 10` is an arbitrary starting point, not a claim about real drawings. *(revised 2026-09-26, ADR-0017: the headline corpora now fix the budget at 16, matched to two reference sheets. See "Density calibration" below.)*

Four strategies, all behind one interface so they are swappable:

| Strategy | How it cuts | Represents |
|---|---|---|
| `flow_greedy` **(default)** | Walk downstream from feed nodes, fill a sheet to its budget, cut, continue | How a designer actually works; yields the mostly-path sheet adjacency real sets have |
| `modularity` | Louvain communities, merged/split to meet the budget | "Partitioned by process unit" |
| `utility_aware` | Extract utility headers to dedicated hub sheets first, then `flow_greedy` on the rest | Adds the hub-sheet structure |
| `random` | Balanced random partition | **Control.** Deliberately unrealistic |

Making the strategy a parameter is the point, not a convenience: *does the partitioning strategy change retrieval accuracy?* If `random` and `flow_greedy` produce the same curve, the result is robust and the "your data isn't realistic" objection is answered **empirically**. If they diverge, that divergence is itself a finding worth a section.

### Density calibration (added 2026-09-26, ADR-0017)

- **Root cause.** `flow_greedy` orders cluster owners with `_flow_order`, which was a **breadth-first** walk
  (`strategies.py:208–232`). Every generated unit hangs off an earlier one, so the breadth-first walk from
  the one feed interleaves all units. The two ends of an edge sit a median of 287 order positions apart,
  and `_chunk_by_budget` cuts runs of 4–32, so nearly every inter-cluster edge is cut. In the diagnostic
  (1,000 units, seed 0), `flow_greedy` cut 6,162 / 6,099 of 6,232 cuttable edges at budget 4 / 16, and
  `random` cut 6,230 / 6,220. Before the fix, `flow_greedy` ≈ `random`, so the comparison above would be
  empty. That is a bug, not a modelling choice.
- **The fix.** `_flow_order` becomes a **depth-first** preorder from the feeds, with the same sorted
  tie-break. It is shared with `by_unit` and `utility_aware`. Nothing else in the splitter changes. The
  task is T4b in `kg-construction.md` §10.
- **Headline budget: 16** (`flow_greedy`, `sheet_equipment_budget=16`, all else unchanged). 16 was run.
  Budget 13–14 would give 36 nodes by the measured 2.66 nodes per budget unit, but it has not been run.
  The code default of 10 does not change; the headline sets 16 explicitly. This does not reverse the
  struck bullet above: 16 matches two reference sheets and is not a claim about real drawings in general.
  Sweeping density (budget ∈ {4, 16, 32}) is a could-item (ADR-0017 D4).
- **Two reference densities.** **Nodes per sheet: EX01, 36** (conceptual graph, `kg-construction.md` §2).
  **Connector stubs per sheet: OPEN100, 8.0** (96 connectors over 12 sheets, the table above).
  Depth-first at budget 16 gave 42.6 nodes and 9.1 stubs per sheet (1,566 pairs). Without the fix, budget
  16 gives 42.6 nodes but 35.4 stubs per sheet.
- **These numbers are re-measured.** The depth-first figures come from the architect's scratch
  re-implementation, not from the fixed code. After T4b, **SMOKE-06** re-measures nodes/sheet and
  stubs/sheet at 1,000 and 2,900 units, and only its numbers are cited from then on. SMOKE-01…03 (budget 4)
  stand for time, memory and round trip only. ADR-0017 is revisited if stubs/sheet leaves OPEN100's range
  of 2–12.

## 4. How it is tested

**The round-trip invariant is the main test.** `rejoin(split(plant, cfg), manifest)` must reproduce the original graph exactly — same nodes, same edges, same attributes. Any bug in cutting or OPC insertion breaks it. Run it as a property test over generated graphs and all four strategies.

Also:
- Every cut edge produces exactly one `ConnectorPair`; no orphan connectors
- Connector tags are unique within a sheet and resolvable across sheets
- Sheet sizes respect the budget within tolerance
- Same seed ⇒ byte-identical manifest
- No sheet is empty; no node appears on two sheets *(see open question 3)*
- Pure logic, no database, no filesystem — runs in unit tests

## 5. How it reports accuracy

It does not measure a model; it **manufactures the yardstick**. `SplitManifest.connector_pairs` is the gold set that downstream components are scored against:

- **OPC linking** — precision/recall of predicted pairs vs. the manifest (EXP-0004)
- **Reassembly fidelity** — does the system's merged graph match the original edge set?
- **Scale sweep** — the same plant cut into 10 / 50 / 100 / 500 sheets gives the accuracy-vs-scale curve (EXP-0002)
- **Abstention** — deleting a sheet from the corpus while keeping its manifest entries creates *known-unanswerable* questions (EXP-0005)

## 6. Which part of the claim it serves

Contribution 1 outright, and it unblocks EXP-0002, 0004 and 0005. Without it the thesis claim cannot be measured at all — only argued.

## Open questions for review

1. ~~**Package name**~~ — **decided 2026-08-25: `src/plantgraph/`.**
2. ~~**What counts as "major equipment"**~~ — **decided 2026-08-25: instruments do not count against the sheet budget.** Justified by OPEN100, where sheets carry ~350 instrumentation nodes against a handful of tanks (35) and pumps (16). The budget counts process equipment — vessels, pumps, exchangers, columns, tanks. Instruments, valves, connectors and crossings ride along with whatever equipment they attach to. Needs a concrete pyDEXPI class list at implementation time.
3. ~~**Equipment appearing on two sheets**~~ — **decided 2026-08-25: the splitter manufactures these too.**

   Two distinct cross-sheet mechanisms, and the benchmark must contain both:

   | | Off-page connector | Tag identity |
   |---|---|---|
   | What is split | a **pipe** — one edge cut in two | an **object** — one node drawn twice |
   | Recovering it | reconnect a severed **edge** | merge duplicate **nodes** |
   | Signal | connector label naming the partner sheet | the equipment **tag** string |
   | Failure if missed | graph is disconnected — visibly wrong | graph looks fine but answers are **silently half-complete** |

   The second failure mode is the dangerous one, which is why it earns a place in the benchmark rather than a later design note.

   **Generation.** After partitioning, pick a fraction of equipment nodes (`duplication_rate`) whose neighbours span more than one sheet, and draw them on each such sheet: one **home** occurrence carrying full attributes, and **reference** occurrences carrying the tag and little else — which is how real drawings do it. Record every occurrence group in the manifest as the tag-identity gold set.

   **Do not make the tags trivially matchable.** Real sets have `RC-P102A` and `RCS-PU-102A` for the same pump, and OPEN100 shows exactly this messiness. Tag formatting must be a generator variable, with an exact-match-only mode as the easy control.

   Needs `ConnectorPair`'s sibling in `models.py`: an `IdentityGroup` (tag, home occurrence, reference occurrences). Add before implementing the splitter.
4. ~~**Do we need rendered images in Phase 1?**~~ — **decided 2026-08-25: no.** The user set the order: build the synthetic plant, cut it, read the sheets back, confirm extraction works on clean graphs, *then* render to a scanned-style PDF and test reading from that. Isolate one variable at a time — if retrieval fails on a perfect graph, adding scan noise only tells you it fails harder. A simulated-scan stage (skew, noise, JPEG artefacts) sits between clean graphs and the professor's real documents, using Stürmer's 75.46% edge mAP as the realistic operating point.

**All four open questions are now closed. The splitter is ready to implement.**
