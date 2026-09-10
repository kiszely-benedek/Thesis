# plantgraph

GraphRAG at plant scale for P&ID engineering diagrams. Master's dissertation, work in progress.

## The claim

A P&ID is the engineering drawing of a plant's pipes, valves and instruments. One plant needs
hundreds of sheets, and a pipe leaving one sheet continues on another through an *off-page
connector*: a labelled arrow saying "continues on drawing 120, sheet 1, grid cell D-1".

Published question answering over P&IDs (ChatP&ID and its follow-ups) turns **one sheet** into a
graph, condenses it, and pastes the whole graph into the prompt. On one sheet that wins. This
dissertation tests whether it still wins at scale:

> The best retrieval strategy for GraphRAG over engineering diagrams depends on **corpus scale**.
> The single-sheet optimum is an artifact of single-page evaluation and inverts once the corpus is
> a whole plant region — roughly ten documents of about a hundred pages each.

Two supporting contributions make that measurable: a **multi-sheet benchmark with cross-page
ground truth** (no public dataset has one — PID2Graph, the largest annotated P&ID set, is 500
independent single pages), and **cross-sheet entity resolution measured properly**, meaning
off-page connectors linked between sheets and one machine recognised as one machine when it is
drawn on two.

## Where the work stands

Phase 0: building the ground truth. There is no retrieval pipeline yet.

- **Synthetic side.** A seeded generator builds plant graphs, a splitter cuts them into sheets and
  turns every cut edge into an off-page connector pair, and the resulting `SplitManifest` is the
  answer key. Because the seed fixes every random choice, the same seed gives the same benchmark.
- **Real-drawing side.** The 12 OPEN100 nuclear-plant sheets inside PID2Graph carry 96 off-page
  connectors whose text exists only in the images, not in the GraphML. This repo locates them from
  the GraphML bounding boxes, crops them, records what each one says, and pairs them across sheets.
  Result: 22 confirmed pairs, 42 references to drawings absent from the dataset (deliberate "the
  answer is not here" cases), 10 unresolved. Every one of the 96 was read at least twice.

Both producers emit the same `SplitManifest`, so later code cannot tell synthetic and real ground
truth apart.

## Layout

```
src/plantgraph/
  graph/        graph schema and validation
  benchmark/    generator, splitter, partitioning strategies, answer-key model
    open100/    the real-drawing annotation and its two CLI stages
  adapters/     pyDEXPI conversion and plant summaries
tests/          pytest
```

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). `uv.lock` is committed and is the
source of truth; nothing here uses `pip install`.

```powershell
git clone https://github.com/kiszely-benedek/Thesis.git
cd Thesis
uv sync --extra dev
```

## Running

```powershell
uv run pytest              # tests, no data needed
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

All four must pass before a commit. `uv run ruff format .` rewrites in place; `uv run ruff check
. --fix` applies the safe autofixes.

**Working with the real drawings** needs PID2Graph from Zenodo (record 14803338, about 9.3 GB).
The code wants the folder holding the twelve OPEN100 sheets as `0.png` … `11.png` with a
`.graphml` beside each — in the archive, `Complete/PID2Graph OPEN100`.

```powershell
# stage 1: find the connectors and crop them for reading
uv run python -m plantgraph.benchmark.open100 "<path>/Complete/PID2Graph OPEN100" out/stage1

# stage 2: build the answer key
uv run python -m plantgraph.benchmark.open100.stage2 "<path>/Complete/PID2Graph OPEN100" out/stage2
```

Stage 1 reports how many connectors it found (expected 96: 55 on right-hand page edges, 41 on
left) and writes montage images plus a tag-to-key map. Stage 2 reads the verified transcriptions
in `annotations.py` and the pairing decisions in `manifest.py`, then writes the `SplitManifest` as
JSON and a one-row-per-connector CSV for review. It refuses to write if any connector would be
left unaccounted for.

## House style

The code is read by a professor in pull requests, so it is written for a reader: small functions,
type hints everywhere, at most two levels of nesting, no file over 400 lines. Docstrings and
comments are in **Hungarian**, identifiers and error messages in English. No figure appears in a
note unless a run produced it or a paper stated it.

## Licence

**AGPL-3.0** — see `LICENSE`. pyDEXPI, the DEXPI conversion library this depends on, is AGPL-3.0,
and importing it makes this a derivative work. Applied provisionally on 2026-09-06 while two
questions to the university are still open: the institutional IP policy on thesis code, and
whether any industrial partner expects proprietary use.
