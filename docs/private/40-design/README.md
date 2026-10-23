# Design notes

One file per component, written by the `architect` agent **before** the `coder` agent implements it.

A design note is finished when it answers all five:

1. **What is the input and what is the output?** Concrete types, not prose.
2. **What is the data model?** Pydantic models, named and located.
3. **How will it be tested?** Unit tests without a database; integration tests with one.
4. **How does it report its own accuracy** against ground truth?
5. **Which part of the thesis claim does it serve?** If there is no answer, it may not belong in scope.

## Planned components

| Component | Purpose | Design | Status |
|---|---|---|---|
| `benchmark/splitter` | Cut a plant graph into N pages, insert off-page connector pairs, retain cross-page ground truth (ADR-0004) | [splitter.md](splitter.md) | **ready — 3 of 4 open questions closed** |
| `benchmark/open100` | Recover real cross-sheet ground truth from the 12 OPEN100 drawings (ADR-0005) | [open100-annotation.md](open100-annotation.md) | **ready to implement** |
| `benchmark/generator` | Seeded random plant graphs (units, branching streams, control loops) for the splitter to cut (ADR-0007) | [plant-generator.md](plant-generator.md) | **draft — awaiting review** |
| `graph/tag-identity` | Same equipment drawn on multiple sheets — node merging, distinct from OPC edge reconnection | — | not started |
| `benchmark/corruptor` | Inject digitization error at measured rates for the propagation study | — | |
| `graph/schema` | Pydantic + Neo4j LPG model: domain vs lexical edges, abstraction levels | [plant-generator.md §4](plant-generator.md) | **draft — awaiting review** |
| `graph/loader` | pyDEXPI → Neo4j, behind an adapter (see ADR-0003) | — | |
| `resolve/entity` | Off-page connector linking and cross-sheet tag identity | — | |
| `retrieval/*` | ContextRAG / VectorRAG / PathRAG / CypherRAG + the hierarchical router | — | |
| `eval/harness` | Question sets, metrics, LLM-as-judge with cross-judge protocol | — | |
| realism pass | Units span sheets, duplication on, signal loop numbers, unit nodes in Neo4j, question reach; utilities parked (ADR-0025…0029) | [realism-units-duplication-reach.md](realism-units-duplication-reach.md) | **draft — awaiting review** (2026-10-01) |
| `qa/cascade` v2 | Cypher tier 1 → graph_agent tier 2 under a pre-registered latency bound; agent fixes; harness question deadline (ADR-0048) | [cascade-v2.md](cascade-v2.md) | **draft — awaiting review** (2026-10-08) |
| `demo/` drawing export + app | One PDF per corpus (one page per sheet, flags link pages) and a local web UI answering through the cascade, replay-first, paid calls guarded (ADR-0024, ADR-0049) | [demo-app.md](demo-app.md) | **draft — awaiting review** (2026-10-10) |
| `infra/` + replays | Infrastructure cost at D100/D1000(/D4000): one-time build, standing footprint, per-question local compute from zero-spend replays; money only via a cited price (ADR-0051) | [infra-cost.md](infra-cost.md) | **draft — awaiting review** (2026-10-10) |
| EXP-0001 (single-sheet end) | ContextRAG (Luna high) vs frozen cascade_v3 and tiers on a size ladder H1/H3/H10/H30 + EX01 anchor (5 ChatP&ID questions); H100 conditional; EX01 runner + report as new files only (ADR-0054) | [exp0001-single-sheet.md](exp0001-single-sheet.md) | **draft — awaiting review** (2026-10-11) |
| *(tooling)* `/parallel-implement` | Run several Sonnet `coder` subagents on one design note, file-owned (ADR-0006) | [parallel-coder-skill.md](parallel-coder-skill.md) | **draft — awaiting review** |

## Standing constraints

- Runs on one developer machine. No cluster assumptions.
- Pure logic separable from I/O so it is testable without Neo4j.
- pyDEXPI stays behind a thin adapter regardless of how ADR-0003 resolves.
- Every component reports a number. A component that cannot be measured cannot support the claim.
