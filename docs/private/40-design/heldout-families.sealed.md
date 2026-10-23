---
component: SEALED — held-out question families and held-out wordings for EXP-0006
status: sealed 2026-10-02 — do not open, quote or summarise before the QAR freeze (F1)
opened_by: only the coder task QAR-T10, after F1 (question-aware-retrieval.md §9, ADR-0035)
author: architect (Opus 5.5), 2026-10-02
---

# SEALED — do not read before the QAR freeze

**If you are writing or tuning any retrieval strategy, need rule, prompt, primitive or parameter: stop here.**
This file is the held-out half of EXP-0006 (ADR-0035). Its sha256 is recorded in ADR-0035 and in
`question-aware-retrieval.md` §9, so any edit after 2026-10-02 is visible. Changing it after the freeze makes every
held-out number "post hoc" and needs a new ADR.

Rules for the coder of QAR-T10:
- Implement exactly what is written here. If something is ambiguous, choose, and write the choice into the
  module docstring; do not ask a strategy author.
- Do not edit any file listed in the freeze manifest (`data/freeze/qar-freeze.json`); a test asserts their hashes.
- Allowed edits: new members in `QuestionFamily` (`qa/models.py`); new modules
  `qa/questions/families_heldout.py`, `qa/questions/templates_heldout.py`; the harness-side family metadata
  (`qa/harness/family_meta.py`: split and gold need labels); the sampler's family registry; tests.
- Every family below reads only `tag`, `node_class`, `unit_id` and `send_to` / signal topology of the
  **ground-truth plant** (ADR-0013, ADR-0021). Answers are tags, unit ids, counts or "yes"/"no".
- `k`, `k_connector`, `k_identity`, `u` come from `build_question` over the stated evidence (ADR-0028, ADR-0029).
- Candidate enumeration at H1000 must finish inside 600 s (ADR-0029 criterion). Use the per-anchor cap of
  ADR-0029 (at most one question per family, source anchor and k-bin; target drawn with a seeded rng).
- Question sets for these families are generated **on test corpora only** (H100, H1000, seed 0). Never on a dev
  corpus.

## Part A — six held-out families

Shortest paths: over `send_to`, ties broken by the lexicographic tag sequence, exactly as `FLOW_PATH`
(`families_flow.py`). "Operated valve" = `OPERATED_VALVE_CLASSES`; "valve" = `VALVE_CLASSES`; "equipment" =
`EQUIPMENT_CLASSES` (`graph/schema.py`).

| # | Family id | Template (one phrasing) | Answer type | Reference (ground-truth plant) | Evidence | Gold need (acceptable labels) |
|---|---|---|---|---|---|---|
| H1 | `FIRST_MEETING_POINT` | "Which item is the first place where the flow from {A} and the flow from {B} come together?" | `TAG` | `D = desc(A) ∩ desc(B)` over `send_to`. The answer is the `m ∈ D` from which every other member of `D` is reachable. Candidates: `A`, `B` equipment, neither reachable from the other, such an `m` exists, is unique and is equipment or a valve | shortest path `A → m` ∪ shortest path `B → m` | `GENERIC` (composite: two traversals and an intersection) |
| H2 | `DOWNSTREAM_ISOLATION` | "To cut {X} off from all downstream equipment, which valves must be closed?" | `TAG_SET` | mirror of `UPSTREAM_ISOLATION`'s walk along `send_to` **successors**: on each route the first operated valve; check valves are passed through. Precondition: every downstream route meets an operated valve before a node with no successor; otherwise no candidate | the walked edges | `DOWNSTREAM_TO_FIRST_VALVE`, `DOWNSTREAM_ALL` |
| H3 | `VALVES_ON_PATH` | "How many valves does the flow pass between {A} and {B}?" | `COUNT` | number of valve nodes strictly between `A` and `B` on a shortest `send_to` path. Candidate only if **every** shortest path has the same count (check min and max over the shortest-path DAG) | the lexicographic shortest path | `PATH` |
| H4 | `FEEDING_UNITS` | "Which units deliver process flow directly into unit {U}?" | `UNIT_SET` | `{unit(u) : (u, v) send_to, unit(v) = U ≠ unit(u)}`; empty answers skipped | those edges | `UNIT_SCOPE` |
| H5 | `UNITS_REACHED` | "Through how many other units does the flow leaving {X} eventually pass?" | `COUNT` | `|{unit(v) : v ∈ desc(X) over send_to, unit(v) set, unit(v) ≠ unit(X)}|`. Candidates: equipment with at least one descendant | edges of the BFS tree of `desc(X)` (successors visited in sorted node-id order) | `DOWNSTREAM_ALL` |
| H6 | `ROUTE_AVOIDING` | "Can flow get from {A} to {B} without passing through {V}?" | `BOOLEAN` | `"yes"` iff `B` is reachable from `A` over `send_to` in the plant with `V` removed. Candidates: `A → B` reachable; `V` an item strictly inside the lexicographic shortest path. Within each k-bin draw "yes" and "no" alternately (seeded) so neither dominates | yes: the shortest `A → B` path avoiding `V`; no: the BFS tree of `A`'s descendants in the plant without `V` | `GENERIC` (composite; expected outside the primitive set — `path` has no exclusion argument) |

## Part B — held-out wordings (should-tier)

The same reference function, evidence, `k` and answer type as the dev family; only the text differs.
`template_id` = the dev template id + `_P1`. Unit anchors keep the literal word "unit" before the id, so that
anchor extraction (`anchors.py`) behaves as it does for the dev wording.

| Dev family | Held-out wording |
|---|---|
| `LOOKUP_TYPE` | "{tag}: what kind of equipment or component is it?" |
| `LOOKUP_UNIT` | "{tag} belongs to which plant section?" |
| `NEIGHBOURS_DOWNSTREAM` | "Name every item that is fed directly by {tag}." |
| `LOOP_ACTUATED_VALVE` | "Control loop {loop_tag} drives which valve?" |
| `LOOP_MEASURED_EQUIPMENT` | "The sensor of loop {loop_tag} sits on which piece of equipment?" |
| `FLOW_PATH` | "List, in flow order, the equipment and valves the process stream passes from {A} until it reaches {B}." |
| `UPSTREAM_ISOLATION` | "Before maintenance on {X}, which valves have to be shut to stop every incoming flow?" |
| `CROSS_UNIT` | "Unit {U} passes material straight on to which other units?" |
| `COUNT_IN_UNIT` | "What is the number of {class_plural} belonging to unit {U}?" |
| `SHEETS_OF_TAG` | "{tag} appears on which drawing sheets?" |

## Acceptance for QAR-T10 (offline)

- On a hand-built split toy plant, each family's reference answer, evidence and `k` equal hand values; H1's
  uniqueness rule rejects a toy with two incomparable meeting points; H3 rejects a toy whose two shortest paths
  hold different valve counts; H6 yields both answers on a toy.
- The freeze-manifest test passes (no frozen file changed).
- Same seed → byte-identical question JSONL; the availability report lists every held-out family per k-bin.
- Generated on H100 and H1000 only; the CLI refuses a corpus whose `CorpusRecord.role` is `dev`.
