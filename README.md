# plantgraph

**Tudásgráf-építés műszaki rajzokból és P&ID diagramokból skálázható Q&A rendszerhez**
*(Knowledge-graph construction from P&ID diagrams for a scalable question-answering system)*

BSc thesis project (BME VIK, computer engineering, TMIT). Code, identifiers and
the demo are in English, docstrings and comments in Hungarian.

## What it is

A P&ID is the engineering drawing of a plant's pipes, valves and instruments. A real plant needs hundreds of
sheets, and a pipe leaving one sheet continues on another through an *off-page connector*. Published P&ID
question answering (ChatP&ID, 0.91 accuracy) works on **one sheet** and pastes the whole sheet graph into the
prompt. This project asks what happens at **plant scale** (~100 and ~1,000 sheets) and builds a system for it:

1. **Benchmark** — a seeded generator builds plants as real pyDEXPI `DexpiModel`s, a splitter cuts them into
   sheets with off-page connectors, and the split itself is the answer key (no public multi-sheet P&ID dataset
   with cross-sheet ground truth exists).
2. **Knowledge graph** — sheets (or a real DEXPI/Proteus file) are imported, cross-sheet references are resolved
   into one plant graph, and both the as-drawn and the merged plant layer are loaded into **Neo4j**.
3. **Q&A** — `cascade_v3`: an LLM writes a Cypher query first; if it flags its own answer as unsure, a graph-tool
   agent answers by composing six plant primitives (walk upstream/downstream, path, instruments, …).
   Baseline: ContextRAG (the whole graph in the prompt, the ChatP&ID method).
4. **Evaluation** — accuracy, token cost, infrastructure cost and latency at 1 → 1,000 sheets, with a sealed
   test on plants never used in development.

## Where it stands (2026-10-23)

All experiments are done and the demo is finished. Every number below is a
measured run (model: GPT-6 Luna via OpenRouter).

| Result | Value |
|---|---|
| Sealed test, held-out plants, n = 460 headline questions | **0.937** at ~100 sheets, **0.917** at ~1,000 sheets |
| Cost / median latency per question | $0.00065 / 8.4 s (H100), $0.00071 / 8.2 s (H1000) |
| Scale effect (primary claim) | accuracy change 100 → 1,000 sheets −0.020 [−0.052, +0.013]: **holds at scale** |
| ContextRAG vs cascade, 1 → 30 sheets | 0.824 → 0.658 vs 0.941 → 0.947; ContextRAG cost ×1.8 → ×41.5; prompt stops fitting at ≈143 sheets |
| Build at 1,000 sheets | ingest 26.1 s, store 19.4 MiB on disk |

What the measurements changed: the cascade leads **from a single sheet on**, so there is no single-sheet
"crossover" on our question families — the scale effect is the growing gap in accuracy and cost. ChatP&ID's
0.91 could not be reproduced on its own example (EX01) because of tag naming in the import.
Not done: a separate evaluation of the cross-sheet resolver on real OPEN100 drawings (EXP-0004).
Tests: 2,048 pass (`uv run pytest`), ruff and mypy clean.

## Layout

```
src/plantgraph/
  benchmark/   plant generator, splitter, answer-key models; open100/ = real-drawing annotation
  adapters/    pyDEXPI build, Proteus import, conversion to the graph schema
  graph/       graph schema and validation
  resolution/  cross-sheet resolver (off-page connectors, tag identity)
  ingest/      CLI: generate or import → resolve → load into Neo4j
  store/       Neo4j loader and settings
  llm/         OpenRouter client, response cache, spend guard
  qa/          question families, strategies (ContextRAG, Cypher, agent), cascade, harness, scoring
  infra/       infrastructure-cost measurement
  demo/        drawing/ = PDF export of every sheet; app/ = FastAPI web demo
tests/         pytest (2,000+ tests, no keys needed)
data/          plants, questions, runs, caches, reports, drawings (see data/README.md)
docs/          design notes, decisions (ADRs), experiments, progress log, teaching notes — see below
```

## Setup

Python 3.12+, [uv](https://docs.astral.sh/uv/), and for the store a local **Neo4j** (tested with 2026.09).

```powershell
uv sync --extra dev
```

Create `.env` in the repo root (never committed):

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
OPENROUTER_API_KEY=...        # only for paid model calls
```

The generated data — plants, question sets, every run with its LLM response cache, the reports and the drawing
PDFs — is committed in `data/` (see `data/README.md`), so the demo and the reports run on a fresh clone; a cached
run replays without paid calls. Neo4j holds **one plant at a time**.

## Running

**Checks** (no data, no keys):

```powershell
uv run pytest            # paid live tests run only with --live-llm
uv run ruff check .
uv run mypy
```

**1. Build a plant's knowledge graph** — generate ~100 sheets, check that resolving the split rebuilds the plant
exactly, load the merged plant layer into Neo4j and write `ingest.json`:

```powershell
uv run python -m plantgraph.ingest synthetic --headline --target-sheets 100 --seed 1 `
  --store-profile plant --corpus-id D100 --check --out data/runs/cv1/neo4jplant/D100
# a real DEXPI drawing instead:
uv run python -m plantgraph.ingest proteus path/to/drawing.xml --corpus-id EX01
```

`--no-neo4j` skips the load; `--target-sheets 1000` gives the D1000 plant.

**2. Generate benchmark questions** (with reference answers from the gold graph):

```powershell
uv run python -m plantgraph.qa.questions --corpus-id D100 `
  --ingest-json data/runs/cv1/neo4jplant/D100/ingest.json --seed 1 --n-per-bin 10 --n-unanswerable 10 `
  --out data/runs/cv1/questions/D100
```

**3. Run an experiment** — the harness freezes a run config, then asks every question. Without
`--allow-paid-calls` it only replays the response cache; paid runs need `--max-spend-usd`.

```powershell
uv run python -m plantgraph.qa.harness --run-id MY-RUN --experiment demo --corpus D100:dev `
  --strategy cypher_rag_plant --pin-json <model pin JSON> `
  --corpora-root data/runs/cv1/neo4jplant --questions-root data/runs/cv1/questions `
  --allow-paid-calls --max-spend-usd 0.50
```

**4. Cascade** — combine stored tier runs into the cascade report, or ask one question live:

```powershell
uv run python -m plantgraph.qa.cascade report --corpus D100 --questions-root <questions> --out <dir>
uv run python -m plantgraph.qa.cascade ask "Which valves isolate pump P-101 upstream?" --corpus D100 `
  --policy cascade_v3 --run cypher-luna=<run dir> --run agent-luna=<run dir> --corpora-root data/runs/cv1/neo4jplant
```

**5. Demo** — draw every sheet into one PDF, then start the web app (English UI, every question answered live
through the real cascade, with the route, the Cypher query and the agent's tool calls shown):

```powershell
uv run python -m plantgraph.demo.drawing --corpus D100 --corpora-root data/runs/cv1/neo4jplant
uv run python -m plantgraph.demo.app --config data/runs/cv1/demo/demo_config.json --port 8765
```

Then open <http://127.0.0.1:8765>. The config format is `src/plantgraph/demo/app/demo_config.example.json`;
the committed one is `data/runs/cv1/demo/demo_config.json`. Switching plants in the page loads that plant into
Neo4j.

**Real drawings (OPEN100)** — the 12 real sheets in PID2Graph (Zenodo 14803338):
`uv run python -m plantgraph.benchmark.open100 "<path>/Complete/PID2Graph OPEN100" out/stage1`, then
`... .open100.stage2` with the same arguments and `out/stage2` builds their cross-sheet answer key.

## How it was built

The work was done with an AI-assisted workflow; its full configuration and record are in this repository:

- `CLAUDE.md` — the project rules (design before code, every decision as an ADR, no invented numbers).
- `.claude/agents/` — `architect` (designs and ADRs, no code), `coder` (implements an agreed design for a human
  reader), `researcher` (papers, novelty checks). `.claude/skills/` — session routines (catch-up, progress log,
  paper intake, teaching notes, literature-gap check, comment audit).
- `docs/private/20-decisions/` — 55 ADRs, `40-design/` — design notes, `30-experiments/_results.md` — every
  measured run, `50-progress/` — weekly log, `ALLAPOT.md` — status page (Hungarian). `docs/Notes/` — teaching
  notes (Hungarian).

Every change was reviewed and committed by the author.

## Licence

**AGPL-3.0** — see `LICENSE`. pyDEXPI, which this imports, is AGPL-3.0.
