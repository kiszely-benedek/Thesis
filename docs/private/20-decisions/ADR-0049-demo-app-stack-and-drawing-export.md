---
adr: 0049
title: Build the demo now; draw each sheet from the system's own input with a pure-Python layered layout and fpdf2; serve it with FastAPI and the browser's PDF viewer; answer free questions through the offline cascade walk, replay-first, with paid calls behind a CLI flag, a per-question confirmation and a session cap
status: proposed
date: 2026-10-10
supersedes: in part — ADR-0024 point 5 (timing: "after the headline"); ADR-0024 points 1–4 and its Must/Should/Could log carry over unchanged
design: 40-design/demo-app.md
---

# ADR-0049 — Demo application: how it is built

## Context

ADR-0024 fixed what the demo is (simplified drawings, one PDF per corpus, PDF left / questions right, evidence
sheets shown, replay-cache by default, paid calls only after confirmation). It left open how. On 2026-10-10 the user
asked for it **before** the headline runs: *"Make me a demo app where I can start asking the app questions. And
export the 100-sheet plant and the 1000-sheet plant to PDF."* Facts measured for this ADR (architect scratch,
2026-10-10, design note §1):

- Sheets carry **no coordinates**: a localized sheet is a directed graph of 16–62 symbols (D100) / up to 75 (D1000)
  with tags, classes, line numbers and connector labels only.
- No graphviz binary is installed on the development machine; the project venv has no PDF or web library.
- The existing renderer (`qa/context_render.py`, commit `65cfe6d`) writes **prompt text** (occurrence and plant
  serialisations with legends); it has no geometry and cannot be reused for drawings.
- A free-text question is never in the experiment caches, and no live cascade runner exists: the cascade is
  evaluated offline by joining per-tier runs (`qa/cascade/join.py`, `policy.decide`).

## Options considered

**1. When.** After the headline (ADR-0024 point 5) / **now, PDF export first (chosen, user 2026-10-10)**.

**2. What a page is drawn from.**
- **A. The localized sheets** (`CorpusArtifacts.localized_sheets`) — exactly what ingest hands the system, already
  filtered to visible properties (chosen).
- **B. The raw split sheets** (gold side) — same content plus original ids; a drawing made from gold could show
  something the system never reads.
- **C. DEXPI/Proteus graphics** — pyDEXPI 1.2.0 exports equipment only (index, 2026-09-20); would need a full
  exporter first.

**3. Layout for sheets without coordinates.**
- **A. Pure-Python layered layout (Sugiyama style)** on networkx: break cycles, longest-path layers, dummy nodes on
  long edges, barycenter ordering, instruments in a band above (chosen). Measured on D1000: 6–28 layers, column
  height with dummies ≤ 14, 3 sheets with a cycle.
- **B. Graphviz `dot`.** Best-looking layered layout, but needs the Graphviz binary (not installed; the `graphviz`
  PyPI package only shells out to it, `pygraphviz` needs a C build on Windows) — a system dependency the professor
  must install to regenerate a figure.
- **C. networkx force-directed (`spring_layout`).** No flow direction, overlapping labels, seed-dependent.
- **D. Grid in tag order.** Trivial; shows no structure, so a page would not explain an answer.

**4. PDF library** (licence must be AGPL-3.0-compatible, Windows wheel, no system binary).
- **A. fpdf2** (LGPL-3.0, pure Python, ships `py.typed`): prototype 1000 pages in **4.6 s, 2.47 MB** with 1000
  outline entries and internal links (chosen).
- **B. reportlab** (BSD): same prototype **8.9 s (2.4 s of it layout), 3.31 MB**; no type information, so
  `mypy --strict` needs stubs or an override.
- **C. matplotlib `PdfPages`.** Heavy, no simple outline or internal links.
- **D. PyMuPDF** (AGPL-3.0, compiled). Licence-compatible, but a large native dependency for what fpdf2 does.
- **E. SVG then convert.** `cairosvg` needs the Cairo DLL.

**5. Web stack and PDF viewer.**
- **A. FastAPI + uvicorn, one static HTML page with plain JavaScript, the browser's built-in PDF viewer in an
  `<iframe>`, page jumps by `#page=N`** (chosen). Request and response bodies are the project's Pydantic models;
  sync endpoints run in a thread pool, so a 120 s question does not block the PDF.
- **B. Flask + the same page.** Equally boring; no Pydantic validation of bodies without extra code.
- **C. Streamlit / Gradio.** Python-only UI, but the script reruns on every interaction, a PDF with page jumps
  needs a third-party component, and the dependency tree is large.
- **D. Vendored pdf.js viewer.** Programmatic page control and highlighting; several MB of vendored JS. Kept as a
  fallback if `#page=N` proves unreliable (Could).

**6. How a free question is answered.**
- **A. A lazy live walk over the same `walk_question` / `decide` the offline report uses (chosen):** run the tier
  the walk reports missing, add its `Signals`, repeat. The live decision equals the offline one by construction.
- **B. A separate live cascade implementation.** Two code paths that can disagree with the reported numbers.
- **C. Run every tier, then decide.** Pays for tier 2 on the ≈ 2/3 of questions tier 1 settles.

**7. Paid-call guard.**
- **A. Replay-first; a cache miss returns a cost estimate; a paid call needs the server's `--allow-paid-calls` flag
  and a per-question confirmation, within a per-session `SpendGuard` cap; the demo has its own cache and call log;
  one question at a time; bound to 127.0.0.1** (chosen).
- **B. Confirm once per session.** Fewer clicks; one forgotten confirmation spends all session.
- **C. Share the experiment caches.** Free replays of benchmark prompts, but demo calls would enter caches whose
  provenance belongs to reported runs.
- **D. No live path.** Free-text questions impossible — the user's main use.

## Decision

1. Build now; the drawing-set export is the first coder task.
2. Draw from the **localized sheets** only (2A); every visible property of every symbol appears on the page.
3. **Layered pure-Python layout** (3A), A3 landscape, uniform scale-down for wide sheets.
4. **fpdf2** (4A), one outline entry per sheet grouped by hundreds, every off-page connector flag a link to its
   target sheet's page, searchable text, deterministic bytes.
5. **FastAPI + static page + iframe viewer** (5A).
6. **Lazy live walk** over the offline policy code (6A), with the 120 s cutoff carried across tiers.
7. **Guard 7A**, default session cap $0.50 (user to confirm).

## Rationale

No novelty is spent here: the thesis contribution is retrieval at scale and cross-sheet resolution, so every choice
is the well-understood one that runs on one Windows machine without system binaries. Drawing from the localized
sheets keeps the demo honest — the page shows exactly what the system reads, no gold. Reusing `walk_question`
means a tier, latency and cost shown in the UI are computed the way the thesis tables compute them.

## Consequences

- New runtime dependencies `fpdf2`, `fastapi`, `uvicorn`; dev dependencies `pypdf`, `httpx` (TestClient).
- The demo shows per-tier latency and cost live, so the D100 → D1000 latency effect (ADR-0048) is visible by hand.
  Demo answers are never reported numbers (`reported=False`, own cache and log).
- Tier 1 needs Neo4j to hold the selected corpus in the plant profile; otherwise the app offers a tier-2-only mode
  labelled as not the evaluated policy.
- The live policy file (`cascade_v2.json`) comes from CV2-T5; the demo refuses a label-routing policy.
- **Revisit if** `#page=N` jumps fail in the user's browser (→ 5D), the layout is unreadable on the densest sheets
  (→ revisit 3B as an optional backend), or a 1000-page PDF exceeds 20 MB or 60 s of render time.
