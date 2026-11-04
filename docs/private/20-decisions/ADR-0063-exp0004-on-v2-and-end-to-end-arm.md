---
adr: 0063
title: Run EXP-0004 on the v2 corpora with v2 tag operators as a post-split transform, three deciders (exact, string, string + unit) plus one chat LLM, resolution claims at duplication 1.0, and an end-to-end arm of the frozen V2T-A on the sealed H1000g2 questions under a replay-proved freeze E8
status: accepted (user, 2026-11-04: all eight open questions answered as recommended)
date: 2026-11-04
supersedes: ADR-0031 in part (corpora, operator table, D1 normaliser, D3, D5, where variants are drawn; its option C, the held-out naming family, blocking key and qualitative OPEN100 use carry over). ADR-0032 in part (its EXP-0004 decider role; the router role is untouched). Reuses ADR-0060 option 1B for the freeze. ADR-0028, ADR-0053, ADR-0061 carry over unchanged.
design: 40-design/exp0004-v2.md
---

# ADR-0063 — EXP-0004 on generator v2, with an end-to-end arm

## Context

The user (2026-11-04) decided EXP-0004 must be done, not left as a limitation. ADR-0031 (accepted 2026-10-02) was
designed on v1 and none of it was built: there is no `tag_variants.py`, no `identity_candidates.py`, no `exp0004/`.
Since then v2 became the headline corpus (ADR-0057 Q3 = B) and R5 measured V2T-A at 0.911 / 0.891 on H100g2 /
H1000g2 with exact tags. Checked against the code on 2026-11-04 (design note §1, §2, §8):

- **v2 tag grammar.** Equipment tags are `CODE-UNITSEQ[SPARE]`, sequence of fixed width 2 (`P-1203A`,
  `benchmark/v2/tags.py`). ADR-0031's operator table and its "natural hard negative" were written for `P-7-3` and do
  not apply; its D1 normaliser (strip leading zeros per digit run) is lossy on v2.
- **A/B spares share the blocking key** (ADR-0057's warning, confirmed): 118 of 579 blocked negatives at D1000g2
  (dev seed, rate 0.25), 357 of 1,034 at rate 1.0. Every gold link still survives blocking.
- **Few gold links at the headline rate.** The test seeds hold 21 (H100g2) and 215 (H1000g2) gold links
  (sealed `ingest.json`s). Rate 1.0 gives about 4× as many on the same plant (dev seed: 93 vs 23, 872 vs 220).
- **Exposure.** 112 of 560 sealed H1000g2 questions (97 of 560 at H100g2) have `k_identity > 0`.
- **D3 is not possible on the pinned model.** `openai/gpt-6-luna` lists no `logprobs` / `top_logprobs`
  (`openrouter-models-2026-10-10.json`).
- **D5 has no client.** `llm/systemone.py` was never built.
- **The freeze covers whole directories.** `V2T_FROZEN_FILES` includes `benchmark/`, `resolution/`, `ingest/`,
  `llm/`, `qa/corpus.py`, and `E7.sha256` hashes `splitter.py` and `split_models.py`. Any EXP-0004 code in those
  directories makes `require_v2t_freeze` refuse.
- **The splitter's RNG.** The legacy `_tag_variant` draws from the splitter's own RNG, so drawing variants there
  would change R5's split.

## Options considered

**1 — Scope**
- **A. Resolution only** (P/R/F1 per decider). Cheapest (deciders ≈ $0.55 upper bound), no freeze issue. It cannot
  say whether the 0.891 headline depends on exact tags.
- **B. Resolution plus an end-to-end arm on the sealed H1000g2 questions (chosen).** Three arms (resolver D0, D2,
  D4) of the frozen V2T-A on the variant copy `H1000g2V`, paired with R5 through a copied cache. Upper bound
  ≈ $4.44; the real figure comes from a free replay-only dry run before any cap.
- **C. B on a fresh test seed with a fresh question draw.** Leaves the sealed set untouched, but needs a new paid
  exact-tag baseline arm, about 1.5–2 h of question generation, and no cache pairing. That makes it about 3× the paid
  calls for the same claim.

**2 — Where variants are drawn**
- **A. Inside the splitter, behind new `SplitConfig` fields (ADR-0031).** Changes two E7-hashed files and the
  splitter's RNG stream, so the variant copy no longer has R5's split.
- **B. A post-split transform with a per-reference RNG (chosen).** `splitter.py` and `SplitConfig` are untouched.
  The variant copy equals R5's manifest except for reference tags (tested).

**3 — Deciders**
- **A. All six of ADR-0031.** D3 cannot run on Luna. D3 on another model breaks the one-model rule (ADR-0014). D5
  needs a new client in `llm/` (a system-side path), a paid smoke and a repeatability probe.
- **B. D0, D1, D2, D4 (chosen).** Every decider runs without any system-side code change.
- **C. Free deciders only.** It has no model arm, so it cannot test whether context plus knowledge generalises to
  the unseen family (claim I3).
- **D. A listwise LLM (one call per reference, choose among its block).** Fewer calls, but the unit of decision
  changes, so the deciders no longer share candidates and answer key.

**4 — Duplication rate of the resolution corpora**
- **A. 0.25 only.** Matches R5, but has 21 gold links at 100 sheets.
- **B. 0.25 (E2E and headline-rate resolution) plus 1.0 (resolution claims) (chosen).** Same plant, a second split.
- **C. 1.0 only.** The E2E arm could then not reuse R5's questions.

**5 — How V2T-A is shown unchanged**
- **A. Keep E7 and put every line of EXP-0004 outside the frozen directories**, with a second harness. That second
  harness would itself be a new system to verify.
- **B. Freeze E8 by ADR-0060's method 1B (chosen).** Data-side edits only, no system-side diff from E7,
  byte-identical cache-only replays of the R5 headline runs, and a default-path golden ingest.
- **C. Treat V2T-A on variant corpora as a new system.** Then E2E says nothing about R5's system.

## Decision

1. **Scope 1B.** Resolution claims I0–I4 on `H1000g2d100V` (I4 descriptive across `H100g2d100V`). End-to-end
   claims E1–E4 on `H1000g2V`, arms D0 / D2 / D4, baseline R5's `S7-*-H1000g2` (design note §6, §7). `H100g2V` E2E
   only by a separate user decision.
2. **Variants 2B**, with the v2 operator table: format = `drop_separator`, `swap_separator`, `split_number`,
   `unpad_sequence`, `spare_separator`, `case`; naming (held out) = `class_synonym` (`P/PU`, `E/HX`, `K/C`) and
   `unit_prefix`. Every operator keeps `node_class` and the order of non-zero digits; no synonym equals a code its
   class already uses.
3. **Deciders 3B.** D1's normaliser is upper-case plus alphanumerics, with no zero or synonym handling. D2 adds
   "the units agree". D4 uses the V2T-A Cypher-tier Luna pin with JSON output and no threshold. Grouping adds a
   one-to-one rule per sheet pair. D3 and D5 are cut from EXP-0004.
4. **Corpora 4B** on the registered seeds only: dev `D100g2d100Vf` (format only, τ tuning), descriptive
   `D1000g2d100Vf`, test `H100g2d100V`, `H1000g2d100V`, `H100g2V`, `H1000g2V`.
5. **Tuning.** τ₁ and τ₂ maximise pair F1 on `D100g2d100Vf`; ties go to the higher τ. Nothing is changed after the
   first test-corpus call. The τ's, the D4 prompt, card format and pin hashes, the arm list and the claims are fixed
   in a user pre-registration commit before that call.
6. **Sealed set.** It is reused through a copied question file (only `corpus_id` changed, with a proof file) and a
   copied `cache_s7.sqlite`. Neither original is written. R5's numbers are never re-reported. No V2T change follows
   from any E2E result.
7. **Freeze 5B (E8).** Every R5 record is committed before the first EXP-0004 change to a frozen directory.
8. **Money.** Each paid stage (pilot, dev D4, test D4, E2E) is estimated, capped from measured counts (IDBLOCK-01;
   the E2E dry run's miss list) and approved by the user before it starts.

## Rationale

- **Thesis claim.** R5's 0.891 at 1,000 sheets rests on exact tags. E2E measures what a realistic tag mismatch does
  to that number at plant scale, and what the resolver wins back. The resolution claims measure whether context, and
  then a model, generalise beyond the tuned variants. That is the circularity question ADR-0031 raised.
- **Boring where possible.** The blocking key, scoring, bootstrap, claims code, run scripts and freeze method are
  existing ones. The novelty budget is spent on the identity measurement itself.
- **Measured, not assumed.** Candidate counts, exposure, Luna's parameter list, per-call cost and the freeze
  coverage were all read from the repo or measured by free probes on the dev seed. Test-seed counts and E2E cache
  misses are measured free before any money is committed.
- **Cuts follow cost and evidence.** D3 is technically impossible on the pin. D5 costs a client, a smoke and a
  probe in system-side code, for a readout that arXiv 2609.32160 finds has no independent accuracy advantage.

## Consequences

- **Makes easy:** a free resolution result early (X-T1–X-T3, IDBLOCK-01, dev τ). One plant per seed for all
  variant copies. Paired E2E differences concentrated on the identity-exposed questions.
- **Makes hard:**
  - Every later V2T run must pass E8 instead of E7.
  - D2's unit rule leans on a generator property (references stay inside their unit; 93/93 on the dev probe).
  - Blocking completeness is 1.0 by construction for these operators.
- **Forecloses:** Jev and label-probability readouts in EXP-0004 (ADR-0032's router role is not affected). Variants
  that change digits stay a stated limitation.
- **Revisit if:**
  - completeness < 0.99 on `D100g2d100Vf`;
  - D4's pilot parse failures exceed 2 %;
  - an E8 replay differs without a timing note;
  - the E2E dry run's miss count prices E2E above the user's approved cap;
  - Luna's listing gains `top_logprobs` (D3 becomes possible);
  - the user asks for the Jev arm.

## Status

Proposed 2026-11-04, awaiting the user. Open questions Q1–Q8 with recommendations: design note §12.

**Accepted 2026-11-04 (user, in chat: "mind elfogadva").** Q1–Q8 as recommended in design note §12: end-to-end arm on
H1000g2V with D0 / D2 / D4; Jev cut; D3 cut; duplication-1.0 corpora added; freeze E8; sealed questions reused;
synonyms `P/PU`, `E/HX`, `K/C`; E4 margin 0.03.
