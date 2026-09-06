# plantgraph

GraphRAG at plant scale for P&ID engineering diagrams. Master's dissertation, work in progress.

## What this is trying to show

A P&ID (piping and instrumentation diagram) is the engineering drawing of a plant's pipes, valves and instruments. A real plant is described by hundreds of such sheets, and a pipe that leaves one sheet continues on another through an *off-page connector*: a labelled arrow that says "continues on drawing 120, sheet 1, grid cell D-1".

Published work on question answering over P&IDs (ChatP&ID and its follow-ups) converts **one sheet** into a graph, condenses it, and pastes the whole graph into the prompt. On one sheet that wins. The dissertation tests one claim:

> The best retrieval strategy for GraphRAG over engineering diagrams depends on **corpus scale**. The single-sheet optimum is an artifact of single-page evaluation and inverts once the corpus is a whole plant region (roughly ten documents of about a hundred pages each).

Two supporting contributions make that measurable:

1. **A multi-sheet P&ID benchmark with cross-page ground truth.** No public dataset has it today: PID2Graph, the largest annotated P&ID set, is 500 independent single pages.
2. **Cross-sheet entity resolution, measured properly.** Linking off-page connectors between sheets, and recognising that the same piece of equipment drawn on two sheets is one machine.

## Where the work stands

Phase 0: environment and benchmark construction. There is no retrieval pipeline yet. What exists is the ground-truth side:

- A Pydantic data model for the benchmark answer key (`SplitManifest`), shared by two producers: a synthetic sheet splitter (designed, not yet implemented) and a real-drawing annotation.
- The real-drawing annotation: the 12 OPEN100 nuclear-plant sheets inside PID2Graph carry 96 off-page connectors whose text exists only in the images, not in the GraphML. This repo locates them from the GraphML bounding boxes, crops them, records what each one says, and pairs them across sheets. Result: 22 confirmed pairs, 42 references to drawings that are not in the dataset (deliberate "the answer is not here" cases), 10 unresolved. Every one of the 96 has been read at least twice from crops cut straight out of the source sheets.

The roadmap, decisions and progress log live under `docs/`.

## Repository layout

```
src/plantgraph/
  benchmark/
    models.py            answer-key data model (BoundingBox, ConnectorObservation,
                         ConnectorPair, DanglingReference, IdentityGroup, SplitManifest)
    open100/
      sheets.py          which OPEN100 file is which drawing; drawings referenced but absent
      extract.py         find connector bounding boxes in the PID2Graph GraphML
      crops.py           crop connectors and lay them out on readable montages
      corpus.py          the 12 sheets as one object; stage 1 orchestration
      annotations.py     what each of the 96 connectors says (read by eye, verified)
      manifest.py        pairing decisions and the final SplitManifest
      __main__.py        stage 1 CLI: find and crop
      stage2.py          stage 2 CLI: build the manifest and a review CSV
tests/                   pytest, 12 tests
docs/
  private/00-index.md    start here: thesis claim, phase, roadmap, open questions
  private/10-literature  one note per paper
  private/20-decisions   ADRs (numbered, dated)
  private/30-experiments results table and run notes; OPEN100 manifest and crops
  private/40-design      component designs (splitter, OPEN100 annotation)
  private/50-progress    weekly log
  Notes/                 teaching notes on topics learned along the way
  Academic_papers/       the PDFs
```

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for environments and dependencies. Nothing here uses `pip install`; the lock file `uv.lock` is committed and is the source of truth.
- The PID2Graph dataset for anything that touches drawings (see below). The tests do not need it.

Libraries: **Pydantic** (data model and validation), **Pillow** (cropping the drawings), **NetworkX** (graph handling, reserved for the splitter). Planned but not yet used: **pyDEXPI** for DEXPI conversion and synthetic P&ID generation (AGPL-3.0, licence decision pending in ADR-0003) and **Neo4j** as the graph store (ADR-0002, not final).

## Setup

Clone into a folder of your choosing, then install. The folder name is up to you; git names it after the repository (`Thesis`) unless you pass a target path as the last argument.

```powershell
# Option A: let git create a folder named "Thesis" where you are
git clone https://github.com/kiszely-benedek/Thesis.git
cd Thesis

# Option B: clone into a folder you name yourself, here "Thesis" under Projects
mkdir C:\Projects\Thesis
git clone https://github.com/kiszely-benedek/Thesis.git C:\Projects\Thesis
cd C:\Projects\Thesis

# Option C: you are already inside the empty folder that should hold the code
git clone https://github.com/kiszely-benedek/Thesis.git .

# Then, in every case:
uv sync --extra dev
```

That creates `.venv/` inside the folder with the runtime and development dependencies. Run everything through `uv run` so the right interpreter is used. All commands below are given relative to that folder.

## Running

**Tests** (no data needed):

```powershell
uv run pytest
```

**Lint, format and type checks.** Ruff handles linting and formatting, mypy runs in strict mode. Both are configured in `pyproject.toml` and both must pass before a commit.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

`uv run ruff format .` rewrites files in place; `uv run ruff check . --fix` applies the safe autofixes.

**Getting the data.** Download PID2Graph from Zenodo (record 14803338, about 9.3 GB) and unpack it anywhere. The code needs the folder that holds the twelve OPEN100 sheets as `0.png` … `11.png` with a `.graphml` beside each one. In the archive that is `Complete/PID2Graph OPEN100`.

**Stage 1: find the connectors and crop them for reading.**

```powershell
uv run python -m plantgraph.benchmark.open100 "<path to>/Complete/PID2Graph OPEN100" out/stage1
```

Prints how many connectors were found (expected: 96, 55 on right-hand page edges and 41 on left) and writes eight montage images plus a tag-to-key map into `out/stage1`.

**Stage 2: build the answer key.**

```powershell
uv run python -m plantgraph.benchmark.open100.stage2 "<path to>/Complete/PID2Graph OPEN100" docs/private/30-experiments/open100-stage1
```

Reads the verified transcriptions in `annotations.py` and the pairing decisions in `manifest.py`, and writes `open100_manifest.json` (the `SplitManifest`) and `open100_connectors.csv` (one row per connector, for human review). It refuses to write if any connector would be left unaccounted for.

The committed manifest and CSV under `docs/private/30-experiments/open100-stage1/` are the current answer key. The folders `wide_crops_2026-09-05/` (one crop per connector, cut wide from the full sheet) and `recheck_2026-09-05/` (extra evidence for the contested rows) are what the rows were checked against; a CSV key such as `5:inlet/outlet47` corresponds to the crop `5_47_wide.png`.

## How the code is written

The code is read by a professor in pull requests, so it is written for a reader, not a compiler:

- Small functions, type hints everywhere, docstrings shorter than the function they describe.
- Docstrings and comments in **Hungarian**, identifiers and error messages in English. Domain terms are explained for a programmer with no process-engineering background.
- At most two levels of nesting, no stacked loops, no file over 400 lines.
- Design before code: non-trivial components get a design note in `docs/private/40-design/` first. Anything with a real alternative gets an ADR in `docs/private/20-decisions/`.
- No invented numbers. Every figure in a note comes from a run that happened or a paper that was read, and says which.

## Licence

Not decided yet. The intended dependency pyDEXPI is AGPL-3.0, which would make this code AGPL-3.0 as well; see `docs/private/20-decisions/ADR-0003-pydexpi-agpl-licensing.md` for the open questions.
