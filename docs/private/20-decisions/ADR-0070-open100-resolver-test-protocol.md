---
adr: 0070
title: Test the frozen resolver on OPEN100 with a two-stage human-verified gold, arrow-read direction, a stub-graph adapter, Tesseract as the noise dial, and three pre-registered criteria
status: proposed
date: 2026-11-28
supersedes: none. Carries out ADR-0005 and ADR-0007 decision 3 (OPEN100 held out for the resolver); takes over ADR-0011 item 7 (the user ticks `verified_by_human`), which never happened.
design: 40-design/open100-resolver-test.md
---

# ADR-0070 — How the sheet connector is tested on OPEN100 (EXP-0010)

## Context

- **What is known.** OPEN100's 12 sheets are the only real drawings in the project (`00-index.md` line 101). The
  answer key has 23 pairs, 42 dangling and 8 unresolved connectors, 96 in total
  (`30-experiments/open100-stage1/open100_manifest.json`).
- **What is not.** Checked 2026-11-28 in the same file:
  - **0 of 96** connectors are `verified_by_human`;
  - `direction` and `raw_text` are empty on all 96;
  - the labels were read by Claude models, not by a person.
- **Two facts force choices.** Both are computed from that file:
  - 10 of the 23 pairs have both flags on the same image edge, so the sheet edge cannot give flow direction;
  - 3 line-number pairs print different service prefixes at the two ends, and 3 pairs have a line number at one end
    only. The resolver's group key needs equal line numbers (`resolution/pairing.py` `_group_key`).
- **The resolver is frozen.** It must not change for this test.
- **What gets measured.** No OCR tool is installed on this machine, and nothing on OPEN100 was ever
  pre-registered.

## Options considered

**1. How the gold is made**
- **A. Use the manifest as it is.** No work. It is not citable: no human checked it, and it was built by the same
  reader that would be tested against it.
- **B. Two-stage human verification of the pre-filled readings.**
  - Step A: one flag at a time, blind to partner and fate.
  - Step C: pair verdicts that show location and reciprocity before line numbers.
  - About 2–2.5 h of the user's time (an estimate, design §8). The risk is anchoring on the pre-fill.
- **C. Full blind re-annotation by the user.** The most independent option. Several hours of typing long line
  numbers, by someone new to P&IDs, so it swaps model reading errors for novice typing errors.

**2. Where flow direction comes from**
- **A. The user reads the arrow on each flag in step A.** It is what is on the drawing, and a real digitiser would
  have to detect it too. It adds a few seconds per card.
- **B. The sheet-edge convention** (left = in, right = out). Free, but wrong for 10 of 23 pairs by construction.
- **C. Let the resolver pair without direction.** This changes frozen code, so the test would no longer test the
  system the thesis reports.

**3. What the resolver is fed**
- **A. A stub graph per sheet**, through the frozen `resolve()`: each connector node with one synthetic neighbour.
  It exercises the contract check, the label reading and the pairing exactly as on generated plants.
- **B. A full GraphML import.** It adds an undirected graph (`00-index.md` line 102) and unreliable classes
  (`pump` = flow-element bubbles, `open100-annotation.md` line 103). No pairing decision changes.
- **C. Call `pair_connectors` directly with `ConnectorLabel`s.** Simpler, but it skips the entry point and its
  contract check.

**4. Which line-number rule is primary**
- **A. As printed (N0) primary, the sequence part (N1) as a dial.** The primary run is the resolver as evaluated on
  generated plants. N1 shows what a grammar-aware adapter adds.
- **B. N1 primary.** It is what an engineer would compare (`docs/Notes/pid-lapkozi-csatlakozok.md`). But it was
  conceived knowing that it rescues 3 gold pairs, so the headline would be tuned on the test set.
- **C. N0 only.** It hides a finding about real drawings: their line numbers are inconsistent.

**5. Which OCR reader**
- **A. Tesseract 5 through its command-line program** (TSV output). Free, Apache-2.0, the standard baseline, no
  Python dependency. It needs one `winget` install by the user.
- **B. RapidOCR** (pip, ONNX models). Free, and nothing needs installing outside the venv. It is a less familiar
  baseline and adds a dependency.
- **C. A vision language model.** Probably the most accurate, but paid. It is not independent of the Claude
  readings that made the pre-fill.
- **D. No OCR.** That leaves no measured reading noise; every result assumes perfect transcription.

**6. When OCR runs**
- **A. After the gold is frozen; never shown during verification.** The OCR score stays clean, and OCR does not
  help the user.
- **B. Before; its disagreements guide the user's attention.** It could catch more reading errors, but the gold
  would lean towards the OCR, and the OCR score would be biased upwards.

**7. What counts as a pass**
- **A. Descriptive only.** Honest, but nothing can fail.
- **B. Pre-register now, before any run, three criteria on the primary run:**
  - C1: no false pair;
  - C2: no gold-dangling connector paired;
  - C3: no miss that the resolver's known rules fail to explain.

  Recall stays descriptive. No recall threshold was ever set for real drawings, and one invented now would be
  arbitrary.

## Decision

**1B, 2A** (with 2B as dial R4), **3A, 4A, 5A** (with 5B as the fallback if the install fails), **6A, 7B.**
- The test id is **EXP-0010**, because ADR-0063 reused EXP-0004.
- **$0.** No language-model call.
- No file under `src/plantgraph/resolution/` changes.

## Rationale

- **The test is there to answer the realism objection** ADR-0005 names: "this is not what real drawings look like".
  It can do that only if:
  - the system under test is the frozen one (2A, 3A, 4A);
  - the gold is human-checked (1B);
  - the criteria were fixed before the numbers existed (7B).
- **C1 is the claim generated plants cannot test.** `kg-construction.md` §5.2 derives precision 1.0 from the fact
  that synthetic pair ends share every label. OPEN100's ends do not.
- **The boring choices are deliberate:** Tesseract, static HTML review pages, the existing `SplitManifest` schema
  (ADR-0005), and the existing `score_connector_pairs`. The novelty budget is not spent here.

## Consequences

- **Easy.** A partial result (R0, R1, R4, R5) as soon as the user has done steps A–D and two adapter tasks exist;
  OCR is added later. The gold becomes the first human-verified multi-sheet P&ID connector key in the project, under
  CC BY-SA 4.0.
- **Hard.**
  - The user's 2–2.5 h is on the critical path.
  - R0's recall has a structural ceiling of 16 pairs with today's labels (design §2.4). The thesis will report a
    recall well below the synthetic one, and must explain it with the miss-reason codes rather than hide it.
- **Foreclosed.** No resolver change may be motivated by this test's outcome and still be reported as this test's
  result. A fix would be a new system, measured on a new set.
- **Revisit if:**
  - the verification changes more than a few pairs, in which case the ceiling and C3's codes are recomputed in the
    pre-registration file before the run;
  - Tesseract cannot be installed (5B);
  - the user wants a vision-model reader anyway (a new ADR with its own cap).
