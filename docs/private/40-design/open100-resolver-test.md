---
design: EXP-0010 — the frozen sheet connector (resolver) tested on OPEN100, the only real drawings in the project
date: 2026-11-28
status: proposed (with ADR-0070)
related: ADR-0005 (annotate OPEN100), ADR-0007 decision 3 (OPEN100 held out for the resolver), ADR-0011 item 7, ADR-0023 (DRAWING_ONLY labels), 40-design/open100-annotation.md, 40-design/kg-construction.md §5
adrs: ADR-0070 (proposed)
---

# EXP-0010 — Does the sheet connector work on a real drawing set?

**Why this exists.** Every resolver number in the thesis comes from generated plants. On those, the two ends of a
cut pipe carry identical labels by construction, so `kg-construction.md` §5.2 can say "pair precision is 1.0 at every
dial". OPEN100 is the only place where that claim meets drawings a human drafted. This test is the external-validity
check the roadmap planned as phase 5 ("EXP-0004: OPEN100 23 pairs + label dials", `00-index.md` line 74). It never ran.

**Why a new id.** ADR-0063 reused the id EXP-0004 for tag-variant identity on v2. This test is EXP-0010.

**Link to the claim.** It does not measure scale. It defends the methodology: the plant graph that every retrieval
strategy in the scale sweep runs on comes from the resolver. If the resolver fails on real flags, the scale results
are about an idealised plant graph. 12 sheets are a point, not a curve (ADR-0005, "Limits").

**Scope.** Connector pairing only: which flag on sheet A continues as which flag on sheet B. Out of scope:
- tag identity, because no GraphML node carries a tag (ADR-0031 D, ADR-0063: OPEN100 stays qualitative);
- the merged graph and Q&A on it, because the GraphML has no text to ask questions about;
- symbol detection, because the connector boxes come from PID2Graph's human annotation, not from a detector.

---

## 1. Facts checked on 2026-11-28

| Fact | Value | Source |
|---|---|---|
| OPEN100 files on this machine | 12 `.png` + 12 `.graphml` in `C:/Users/Otthon/Desktop/Munka/PID2Graph/Complete/PID2Graph OPEN100` | directory listing. **The path in `00-index.md` line 100 (`C:/Users/Otthon/Desktop/PID2Graph`) does not exist.** |
| Off-page connector nodes (`label == "inlet/outlet"`) | 96; 95 have degree 1; one (`7/35`) has degree 2 | counted from the 12 GraphML files |
| What a GraphML node carries | `label` + bounding box only; no text, tag or line number | `10-literature/pid2graph.md` lines 72–78 |
| PID2Graph `connector` label | a line junction point, **not** an off-page connector (2,408 of them) | `pid2graph.md` line 76 |
| Annotated fates | 23 pairs, 42 dangling, 8 unresolved; 2×23 + 42 + 8 = 96 | `30-experiments/open100-stage1/open100_manifest.json` (written 2026-09-05) |
| Evidence class of the 23 pairs | 19 `line_number`, 2 `grid_mutual`, 2 `service_direction` | same file; the pairs are a hand-written list in `benchmark/open100/manifest.py` `PAIRS` |
| Human verification | **0 of 96** connectors have `verified_by_human = True` | same file |
| `raw_text` and `direction` | empty on all 96 | same file |
| Who read the labels | Claude models (2026-08-31, re-read 2026-09-05), plus a few user corrections (2026-08-31) | `open100-annotation.md` lines 95–127 |
| Line numbers in the 23 pairs | 16 pairs print the identical string at both ends; 3 `line_number` pairs differ in the service prefix only (`ES`/`ESS`, `ESS`/`CND`, `COND`/`CND`); 1 `grid_mutual` pair prints two different numbers; 3 pairs have a line number at one end only | computed from the manifest |
| Pairs with both flags on the same image edge | 10 of 23 | computed from the manifest (`side` field) |
| Fields present | target sheet on 94 of 96, line number on 79, grid cell on 26 | computed from the manifest |
| Earlier resolver runs on OPEN100 | none found (`data/runs/`, `tests/`) | grep |
| OCR tools installed | none (no Tesseract binary, no `pytesseract`, `easyocr`, `rapidocr`, `paddleocr`) | checked on this machine |
| Python of the project venv | 3.12.10 | `.venv/pyvenv.cfg` |

**So, the "23 reliably linked pairs".** The count of 23 is correct. "Reliably" is not yet true:
- none of the 23 has been checked by a human;
- 2 rest only on elimination (`service_direction`), and one of them (`7/33 ↔ 8/54`) contradicts its own grid cell
  (`open100-annotation.md` line 127).

The test uses whatever count survives the user's check in §3. The change from 23 is itself reported.

---

## 2. What is measured

### 2.1 Primary metric

**Pair precision, recall and F1** of the resolver's `connector_pairs` against the verified gold pairs.
- A pair is an unordered key set: `eval/resolution_scoring.score_connector_pairs`, reused unchanged.
- Each figure is reported with its counts (TP, FP, FN) and a Wilson 95 % interval, because n is about 23.
- Pairs the user marks `unsure` are left out of the gold. A predicted pair that touches an `unsure` key counts as
  neither TP nor FP. It is listed separately.

### 2.2 Secondary metrics

- **Abstention.** Of the gold-dangling connectors (target drawing not among the 12), how many the resolver pairs.
  The expected value is zero.
- **Miss reasons.** Every false negative gets the first matching code from a fixed list, computed from the
  resolver's own input labels, never from gold notes:
  1. `no_reference`: one end has no readable drawing reference;
  2. `not_reciprocal`: an end's reference does not name the other end's sheet;
  3. `same_direction`: the two arrows do not point opposite ways (or one is unknown);
  4. `line_one_sided`: one end has a line number, the other does not;
  5. `line_differs`: both have one, and they differ after this run's normalisation;
  6. `ambiguous_group`: the resolver reported the key as ambiguous;
  7. `unexplained`: none of the above.
- **OCR field accuracy** (OCR runs only). Exact-match rate of drawing reference, sheet number and line number
  against the verified transcription, per field.

### 2.3 Label dials

Each dial changes **one** factor from the primary run R0. All runs use the frozen `resolve()`.

| Run | Text source | Line number | Direction | What it asks |
|---|---|---|---|---|
| **R0 (primary)** | verified | as printed (N0) | arrow (read by the user) | the frozen resolver on correct labels |
| R1 | verified | sequence part (N1) | arrow | how much an adapter that knows the line grammar recovers |
| R2 | OCR | N0 | arrow | real reading noise, no human in the loop |
| R3 | OCR | N1 | arrow | R2 with the grammar-aware adapter |
| R4 | verified | N0 | sheet edge (left = in, right = out) | what a naive "edge convention" digitiser gets |
| R5 | verified | withheld | arrow | the weakest label: drawing reference only |

- **N0** means stripped, upper-cased, whitespace collapsed, dash variants unified. Nothing else.
- **N1** means the sequence token only, for example `SIZE-ESS-140083-SPEC-HC-X` → `140083`. The teaching note
  `docs/Notes/pid-lapkozi-csatlakozok.md` explains why the sequence part is the line's identity.
- OCR cannot read an arrow. The OCR runs keep the user's arrow reading, so they vary the text only.

### 2.4 Pass criteria: pre-registered here, before any run

Nothing on OPEN100 was pre-registered before. These criteria are, from the commit of this note. They bind R0 only.
Every dial is descriptive.

| Id | Criterion | Why this one |
|---|---|---|
| **G0** (gate) | `check_contract` passes; in every run, 2 × pairs + unresolved = all connectors; the adapter reads no gold file | correctness, not a result |
| **C1** | R0 produces **no false pair** | the design claim of `kg-construction.md` §5.2, so far only shown on generated plants |
| **C2** | R0 pairs **no gold-dangling connector** | abstention: a missing drawing must stay missing |
| **C3** | R0 has **no `unexplained` miss** | makes recall falsifiable without inventing a threshold. Every miss must follow from a known rule of the resolver |

- **Recall is descriptive.** No recall threshold was ever set for real drawings, and inventing one now would be
  arbitrary.
- **Prediction, derived from the code and the current labels, not from a run.** The frozen group key needs equal
  `line_number` values, and `None` never equals a printed number (`pairing.py` `_group_key`). With today's labels,
  R0 can therefore recover **at most the 16 identical-line pairs** of §1, and R1 at most 19. Direction and
  ambiguity can only lower this. If the verification changes labels, the ceiling is recomputed before the run and
  written into the pre-registration file.
- **Result sentence, fixed in advance:** "On 12 real sheets, the frozen resolver linked *x* of *n* verified pairs
  with *y* false links. C1, C2, C3: pass or fail."

---

## 3. The ground truth: independent of the resolver's input

### 3.1 The independence problem, stated plainly

The resolver and the gold both start from what is printed on the flags. They cannot be fully independent. What can
be kept apart is the following:
- the **transcription**: what each flag says, read one flag at a time;
- the **link judgement**: which two flags are one pipe, decided by a human with more evidence than the resolver
  gets. The human sees both drawings, the printed grid border, where the pipe runs, and elimination.

The resolver sees only the transcription. The test therefore asks: given correct readings, do the resolver's
generic rules recover what a human decides from the whole drawing?

There is a known shared signal. 19 of the 23 gold pairs were labelled `line_number`, the resolver's own rule. To
keep the user from simply re-approving line-number matches, step C shows the location and reciprocity evidence
first and the line numbers last.

### 3.2 Steps (detail in §8)

| Step | Who | What | Blind to |
|---|---|---|---|
| A | user | check each of the 96 flags alone: drawing number, sheet, grid cell, line number of **its own** pipe, arrow direction, "is it a flag at all" | partner, fate, pairing notes |
| B | user | check the 12 title blocks: drawing number and sheet of each file | — |
| C | user | judge each proposed pair: the 23 from the manifest, plus candidates for the 8 orphans | resolver output (not yet run) |
| D | user | decide the items step C leaves open | — |
| freeze | main session | hash the gold and the transcription into the pre-registration file | — |
| OCR | machine | run only **after** the freeze; never shown to the user before it | the gold |

- **Pre-fill.** The step A cards are pre-filled from `annotations.py` (fields only). Its `note` column is dropped,
  because it holds pairing rationale. Typing all 96 from scratch would be more independent but much slower, and a
  novice's typing errors would replace the model's reading errors. The anchoring risk is listed in §6.
- **Line-number rule for step A,** taken from `opus_recheck.py`: record the number printed on the pipe run that
  ends at this flag. If the nearest label belongs to another branch or to a merged header, leave it empty.

### 3.3 Files (all under `data/open100/`, licence CC BY-SA 4.0, see `README.md` there)

| File | Written by | Content |
|---|---|---|
| `transcription_prefill.csv` | O-T1 | 96 rows, pre-filled, `verified_by_human = false` |
| `review/transcription.html`, `review/pairs.html`, `review/crops/` | O-T2, O-T3 | the review pages; generated, not committed (they can be rebuilt) |
| `transcription_verified.csv` | user (export button) | 96 rows, `verified_by_human = true`, `changed_fields` |
| `pair_verdicts.csv` | user (export button) | one row per proposed pair: verdict and evidence ticks |
| `open100_gold.json` | O-T3 | a `SplitManifest` (ADR-0005: same schema as the splitter), confirmed pairs only, `verified_by_human` and the parsed fields filled |
| `ocr/raw_tokens.jsonl`, `ocr/transcription_ocr.csv` | O-T5 | OCR tokens with boxes and confidence; the parsed rows in the transcription schema |

```python
class ConnectorTranscription(BaseModel):          # benchmark/open100/transcription.py
    model_config = ConfigDict(frozen=True)
    key: str                       # "5:inlet/outlet43", equal to ConnectorObservation.key
    sheet_file: str
    node_id: str
    is_offpage_flag: bool          # False for a detector false positive (7/35 today)
    ref_pid: str | None            # drawing number printed on the flag, "100"
    ref_sheet: int | None          # its sheet number, 2
    ref_grid: str | None           # "C-1"; the resolver never sees it
    line_number: str | None        # as printed on this flag's own pipe run
    direction: Direction | None    # from the flow arrow; None = cannot tell
    source: str                    # "prefill:annotations.py" | "user" | "ocr:<engine> <version>"
    verified_by_human: bool
    changed_fields: tuple[str, ...] = ()
    comment: str | None = None

class Verdict(str, Enum):
    CONFIRMED = "confirmed"; REJECTED = "rejected"; UNSURE = "unsure"

class PairVerdict(BaseModel):                     # benchmark/open100/gold.py
    model_config = ConfigDict(frozen=True)
    first_key: str
    second_key: str
    proposed_by: str               # "manifest-2026-09-05" | "orphan-candidate"
    evidence: tuple[str, ...]      # "mutual_reference", "grid_consistent", "traced", "line_same_sequence", "elimination"
    verdict: Verdict
    comment: str | None = None
```

The old files in `30-experiments/open100-stage1/` stay as the record of the model readings. `open100_gold.json`
supersedes `open100_manifest.json` as the answer key.

---

## 4. Mapping OPEN100 into the resolver

### 4.1 What the resolver needs, per connector

`resolution/connector_labels.py` reads node attributes only:
- `node_class`: one of the four off-page connector classes. It encodes direction (in or out) and kind (pipe or
  signal).
- `connector_number`: required.
- `referenced_drawing_number`: required, and it must equal a `sheet_id` to be paired.
- `line_number`, `fluid_code`, `loop_tag`: optional, part of the group key.
- exactly one incident edge, whose `relation` is part of the group key.

### 4.2 What OPEN100 has and lacks, and how the adapter copes

| Resolver input | OPEN100 | Adapter rule (`benchmark/open100/resolver_input.py`) |
|---|---|---|
| `sheet_id` | file stems `0`–`11`; the drawing number is in the title block | `sheet_id` = file stem, so resolver keys equal gold keys and nothing has to be remapped |
| `referenced_drawing_number` | printed on the flag | `(ref_pid, ref_sheet)` → file stem via `sheets.BY_REF`, the title-block lookup an engineer would use. If the drawing is absent: `"PID-<pid>-<sheet>"`, which is not a sheet id, so the resolver reports "referenced drawing not in corpus". If no reference: attribute missing, so the resolver reports "no reference label" |
| `connector_number` | **not printed** (real flags do not carry one, ADR-0023) | the GraphML node id. `referenced_connector_number` stays `None`, so rule 1 never fires. This is the `DRAWING_ONLY` regime of the headline corpora |
| direction (via `node_class`) | **not in the GraphML**; the side of the sheet is wrong for 10 of 23 pairs | the user's arrow reading. R4 uses the edge convention. `None` → the connector gets no reference and is reported unresolved, never guessed |
| `kind` | the GraphML has solid lines only | `PIPE` for all |
| `line_number` | printed beside the pipe, not inside the box | per run: N0, N1 or withheld (§2.3) |
| `fluid_code` | flags print the **partner** system's code, so the two ends differ (`open100-annotation.md` line 109) | `None`. Filling it from `service` would split every true pair |
| single stub edge, `relation` | GraphML neighbour is a junction (`connector`) for 95 of 96 | one synthetic neighbour `"<node_id>#pipe"` of class `GenericItem`, `relation = send_to`, edge oriented by direction |
| tags, equipment | none | none, so identity groups are 0 by construction |

**Stub view, not a GraphML import.** The test feeds the resolver one small graph per sheet: each connector plus one
neighbour. Pairing reads nothing else. A full import would add two problems without changing a pairing decision:
- the GraphML is undirected (`00-index.md` line 102);
- its classes are unreliable (`pump` marks flow-element bubbles, `open100-annotation.md` line 103).

ADR-0070 item 3 records this choice.

**The resolver is not touched.** No file under `src/plantgraph/resolution/` changes. The run records the commit
and the SHA-256 of each `resolution/*.py`.

**The hold-out, honestly.** ADR-0007 says the 23 pairs must never be used to develop label parsing. The resolver's
rules were not tuned on them. But:
- the per-corpus grammar in this adapter (reference pattern, N1) is written by people who have read these labels;
- the N1 idea is known to help 3 gold pairs.

That is why N0 is primary and N1 is a labelled dial. All the adapter's unit tests use made-up strings, not the 96
real ones.

---

## 5. The OCR arm (R2, R3)

- **Engine: Tesseract 5**, called through its command-line program with TSV output. No Python wrapper and no new
  Python dependency. The user installs it once: `winget install -e --id UB-Mannheim.TesseractOCR`.
  - **Fallback if the install is blocked:** RapidOCR (`pip install rapidocr onnxruntime`, no system binary), behind
    the same `read_crop(image) -> list[OcrToken]` function. ADR-0070 item 5.
- **Crops, with fixed parameters from existing code and notes, not tuned on the 12:**
  - the flag box for the reference;
  - a wide crop for the line number: 6 × box width and an 80 px margin, the 2026-09-05 re-read setting
    (`open100-annotation.md` line 107).
- **Preprocessing, fixed in advance:** grayscale, 3× Lanczos upscale, Otsu threshold. Page-segmentation mode 11
  (sparse text). A character whitelist of `A–Z 0–9 - ( ) /` and space.
- **Development data:** the 13th OPEN100 sheet, `C:/Users/Otthon/Desktop/valos-pid-mintak/open100/open100_spentfuelcooling_1.png`.
  It is not among the 12. It is the same drafter and font, but has no GraphML. A handful of flag boxes are cropped
  by hand coordinates. Settings may be checked there, **never on the 12**.
- **Parsing** (`benchmark/open100/flag_grammar.py`):
  - one function per field, shared by every arm;
  - reference: `PID[\s-]*(\d{3})[\s-]+0?(\d{1,2})`;
  - grid: `\(\s*([A-H])\s*-\s*(\d{1,2})\s*\)`;
  - line number: tokens matching `^(SIZE|SPEC)-[A-Z]{2,5}-[0-9A-Z]{5,8}-`; the one whose box centre is nearest the
    flag box wins, and a tie gives `None`.
- **Blindness.** The OCR runs once, after the gold freeze. Its settings and engine version go into the
  pre-registration file.

---

## 6. Threats to validity

| Threat | What it does to the result | What the design does |
|---|---|---|
| **One plant, one author ("MAJ"), one CAD tool, one date** (`pid2graph.md` line 42) | a single drawing convention: one flag grammar, one line grammar, one drafter's habits. A sample, not a distribution | stated as a limit. The grammar lives in a per-corpus adapter (ADR-0005 guard 2), never in `resolution/` |
| **Nuclear power plant, not chemical** | process content differs: steam cycle, cooling water, reactor systems | the pairing mechanism does not depend on process content. The flag convention (drawing number + sheet + zone, line number on the pipe) is the codified one (HNF-64103 §3.2.5.1, `00-index.md` line 112), also seen on the Hanford and municipal sets (`10-literature/real-pid-samples-2026-10.md` line 159) |
| **Labels typed by hand: the drafter's** | real inconsistencies: service prefixes differ between ends; grid cells off by a row or more; a mistyped drawing number (7/34); references that point one way only (9/2, 9/59) (`open100-annotation.md` lines 111–129) | this is the realism the test is for. The miss-reason codes make each failure traceable to one of them. These are one drafter's errors, not a rate |
| **Labels typed by hand: ours** | the gold may hold reading errors; the user verifies pre-filled fields, so anchoring can let a wrong digit through | blind per-flag step A; zoomed digits; `changed_fields` reported as a change rate; OCR as an independent second reader after the freeze (its disagreements are reported, not used to edit the gold) |
| **Gold and resolver share the line-number signal** | recall can be inflated where both rely on equal numbers | step C shows the non-line evidence first; the evidence ticks are reported per pair |
| **The hold-out has been looked at** | the adapter grammar and N1 were written by people who know these labels | N0 primary; no change to `resolution/`; pre-registration hashed before the run |
| **Small n (about 23 pairs, 12 sheets)** | one false pair moves precision by several points | counts and Wilson intervals; no claim of a rate |
| **Perfect detection assumed** | the boxes are PID2Graph's human annotation; a real digitiser also misses flags | stated. OCR (R2, R3) is the only digitisation noise measured |
| **Preliminary design drawings** ("INFORMATION ONLY – NOT FOR CONSTRUCTION", ADR-0005) | unfinished placeholders (`FCV XXX`) | stated |

---

## 7. Coder task list

Rules for every task:
- no edit under `src/plantgraph/resolution/` or `src/plantgraph/eval/resolution_scoring.py`;
- small functions, docstrings, at most two levels of nesting;
- ruff, format and `mypy --strict` clean;
- one coder at a time (ADR-0006).

| Id | What | Acceptance | Tests | Size | Machine time (estimate) |
|---|---|---|---|---|---|
| **O-T1** | `benchmark/open100/transcription.py`: `ConnectorTranscription`, CSV load/save, `prefill_from_annotations()` → `data/open100/transcription_prefill.csv`; `data/open100/README.md` with the CC BY-SA 4.0 notice and provenance | 96 rows; keys equal the 96 GraphML `inlet/outlet` keys; no `note` text copied | round trip CSV ↔ model; key set equals `Open100Corpus.observations()`; no pairing words in any field | S | seconds |
| **O-T2** | `benchmark/open100/review_transcription.py`: one static HTML page, a card per flag (box crop + wide crop + 3× zoom of the digits), editable pre-filled fields, an arrow-direction choice, a "not a flag" box, an "Export CSV" button (in-browser download, no server) | opens offline in a browser; the export loads as 96 valid `ConnectorTranscription` rows | leak test: the HTML contains no partner key, fate or `PAIRS` note; 96 cards; export schema test on a saved sample | M | < 1 min for the crops |
| **O-T3** | `benchmark/open100/gold.py` + `review_pairs.py`: candidate list (the 23 + for each orphan the flags on its referenced sheet that point back); pair page showing both crops, both sheets downscaled with the flag boxed so the printed grid border is visible, reciprocity and location first, line numbers last; verdict export; `build_gold(transcriptions, verdicts) -> SplitManifest` → `open100_gold.json` | `accounted_for()` holds; confirmed pairs are symmetric and disjoint; dangling = references to drawings absent from `sheets.BY_REF`; `unsure` pairs absent from `connector_pairs` and listed in the report | unit tests on a 3-sheet made-up example; schema test against `SplitManifest` | M | seconds |
| **O-T4** | `benchmark/open100/flag_grammar.py` (reference, grid, line patterns, N0, N1) + `resolver_input.py`: `to_sheet_graphs(rows, observations, config) -> list[SheetGraph]` per §4.2; `InputConfig(text_source, line_norm, direction_source)` | the frozen `resolve()` accepts the output; one edge per stub; direction `None` → no reference | grammar tests on made-up strings only; `check_contract` passes; an import test asserting the module does not import `manifest`, `annotations` or `gold`; every config builds | S–M | seconds |
| **O-T5** | `benchmark/open100/ocr.py`: `read_crop` (Tesseract CLI, TSV), fixed preprocessing, `OcrToken`, nearest-line choice, writer for `ocr/raw_tokens.jsonl` and `ocr/transcription_ocr.csv`; records the engine version | refuses to run on the 12 sheets unless `open100_gold.json` exists and its hash matches the pre-registration file | parser and nearest-token tests on made-up tokens; a test skipped when the binary is absent; a refusal test | M | estimated ≤ 5 min for 192 crops; measured and reported |
| **O-T6** | `src/plantgraph/exp0010/`: `configs.py` (R0–R5), `run.py`, `scoring.py` (reuses `score_connector_pairs`; Wilson interval; miss-reason codes; dangling check; OCR field accuracy), `report.py` → `data/runs/exp0010/results.json` + `report.md`; CLI `python -m plantgraph.exp0010 run` | report holds per run TP/FP/FN, P/R/F1 with intervals, C1–C3 verdicts on R0, miss reasons, the resolver commit and file hashes | a made-up 3-sheet corpus with known P/R; one test per miss-reason code; G0 conservation in every run | M | seconds |
| **O-T7** (main session) | `data/runs/exp0010/prereg/PREREG.md` + `PREREG.sha256`: hashes of this note, ADR-0070, the gold, the verified transcription, `resolver_input.py`, `flag_grammar.py`, `resolution/*.py`; the recomputed ceiling | written and committed (on the user's order) before O-T5's run and before `exp0010 run` | — | S | — |

**Order, and what comes early.**
1. O-T1, O-T2: the user can do step A.
2. O-T3: the user does steps B, C and D.
3. O-T4, O-T6: R0, R1, R4 and R5 are ready. **This is a partial result, without OCR.**
4. O-T7, then the run.
5. O-T5: R2 and R3 are added to the same report.

---

## 8. The user's part, step by step

The concepts are in two existing Hungarian teaching notes:
- `docs/Notes/pid-lapkozi-csatlakozok.md`: how to read a flag, and why the arrow, not the sheet edge, gives
  direction;
- `docs/Notes/open100-csatlakozo-megoldokulcs.md`: paired, dangling and unresolved.

The time figures are estimates, not measurements. The basis is 96 pre-filled cards at about 30–45 s each, and
about 1–2 min per pair.

| Step | What the user looks at | What the user decides | Time (estimate) |
|---|---|---|---|
| 0 | a terminal | runs the one `winget` line of §5, or chooses RapidOCR instead (open question 2) | 5 min |
| A | `data/open100/review/transcription.html`, one card per flag | for each flag: is the drawing number right; the sheet number; the grid cell if any; the line number on **this** pipe (empty if unsure which pipe); does the arrow point into the sheet or out; is it a flag at all. Then press Export and save the file as `transcription_verified.csv` | 50–75 min, in two sittings |
| B | the 12 title blocks (a strip on the same page) | does file *n* say drawing *X*, sheet *k* of *m* | 5 min |
| C | `data/open100/review/pairs.html` | for each proposed pair: do both flags name each other's drawing; does the flag sit where the other one's grid cell says (±1 row is normal on OPEN100); do the arrows point opposite ways; only then, are the line numbers the same. Verdict: confirmed, rejected or unsure. For each orphan: is any candidate its partner | 35–50 min |
| D | the items left open in C, with the earlier notes (for example `7/33 ↔ 8/54`, `5/114 ↔ 10/14`) | the verdict; when in doubt, unsure (it leaves the score, it does not count against the resolver) | 10 min |
| E | the commands printed in the chat | orders the commit of the gold and the pre-registration file **before** the run | 2 min |
| F | the results table in the chat | nothing to decide; read the result | 15 min |

**Total: about 2 to 2.5 hours, spread over two or three sittings.**

---

## 9. Cost

**$0.** No language-model call anywhere:
- OCR, the adapter, the resolver and the scoring are local;
- the review pages are static HTML.

A vision-model reader was considered as a third OCR engine and rejected (ADR-0070 item 5):
- it is not independent of the earlier Claude readings;
- it is paid.

If the user wants it anyway, it needs its own estimate and cap first.

---

## 10. Open questions (the user's to decide)

1. **Primary line-number rule.** N0 (as printed) or N1 (sequence part)? Recommendation: **N0**, with N1 beside it
   in every table. N1 was conceived knowing it helps 3 gold pairs.
2. **OCR engine.** Tesseract (one `winget` install by the user) or RapidOCR (pip only)? Recommendation:
   **Tesseract**, the standard baseline a professor will recognise.
3. **`unsure` pairs.** Leave them out of the score (recommended) or count them as gold?
4. **The 13th sheet** (spent fuel cooling, website copy, no GraphML). Use it as the OCR development sheet only?
   Recommendation: **yes**, never in the score.
5. **Release.** Commit the gold, the transcriptions and the OCR outputs (small, CC BY-SA 4.0), and not the crops or
   review pages (they can be rebuilt from PID2Graph)? Recommendation: **yes**, as `open100-annotation.md` open
   question 3 already preferred.
6. **Thesis wording.** "An external-validity check on 12 real sheets with three pre-registered criteria; recall
   descriptive." Acceptable?

## 11. Housekeeping for the main session (not decisions)

- `00-index.md` line 100 and `open100-annotation.md` line 15 give OPEN100 paths that do not exist on this machine.
  The real path is in §1.
- `00-index.md` line 74 still names this test EXP-0004. It is EXP-0010 from now on.
- `30-experiments/open100-stage1/pairs_review.html` says "22 pairs". It predates the 23rd and is superseded by
  O-T3's page.
