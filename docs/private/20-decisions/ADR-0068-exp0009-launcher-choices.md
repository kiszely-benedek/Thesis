---
adr: 0068
title: Build the EXP-0009 launcher with caps from question counts, an EXP-0009 build command, relabelled B corpus files, a replay of every sealed run, and validation plants in the majority tagging stratum
status: accepted (user, 2026-11-24)
date: 2026-11-24
supersedes: none. Extends ADR-0065's launcher pattern (EXP-0008) to EXP-0009. Leaves ADR-0066 and ADR-0067 unchanged.
design: 40-design/generator-v2-2-handbook-rules.md §19
---

# ADR-0068 — Five launcher choices for EXP-0009 P1

## Context

- **What is fixed.** EXP-0009 P1 runs two arms on the same v2.2 plants (ADR-0067). The launcher follows the EXP-0008
  launcher (ADR-0065), which was proven over a 17.7 h sealed stage.
- **What changes the setting:**
  - the drawn sheet targets;
  - the per-document tagging override;
  - a second corpus id per plant;
  - a hard cap of $35 (user, 2026-11-24).
- **Five points have a real alternative.** The evidence is in design §19.

## Options considered

**1. How a paid run gets its cap**
- **A. As in EXP-0008.** A free dry run with canned replies counts the cache misses. The cap is misses × cost × 1.5.
  - It gives an exact count when the cache holds hits.
  - It costs about 12 min per run at 1,000 sheets (measured in the EXP-0008 M6a log), about 4 h over P1c.
  - B would need a dry-run tool of its own.
- **B. Caps from question counts.** The cap is n questions × cost × 1.5. Then come the same ceiling, ledger and resume
  rules.
  - Every EXP-0009 stage has a fresh cache, so misses equal n on a first run anyway.
  - On a resume, the resume rule adds what was already spent.
  - The cap can only be higher than a dry run's, and the ledger and the $35 still bind.

**2. How a plant with a drawn target and a tagging allocation is built**
- **A. Extend the ingest CLI.** It would need a seed-plan path flag, a nominal-size id and a tagging-override flag.
  It touches the CLI that the goldens and the EXP-0008 scripts use, and it re-runs the size search at every build.
- **B. An EXP-0009 build command.** It composes the config from `plan.json`, written before PREREG A, and calls
  `run_synthetic` directly. It uses the frozen writer and the EXP-0009 seeds file. The ingest CLI stays untouched.

**3. Where a B corpus's `ingest.json` comes from**
- **A. A second build under the B id.** One more 1,000-sheet generation per plant (8–12 min) for identical content.
- **B. A relabel of A's file.** Only `corpus_id` changes, the S3 pattern for questions, with a byte test and a
  rebuild-count test.

**4. Which runs are replayed**
- **A. Every sealed run, as EXP-0008.** About 10 h of P1c at 1,000 sheets. The Cypher replay took 47.5 min on
  H1000g21p2.
- **B. Only the replays E10 requires.** These are one per A2 tier (G0f) and one per B tier of the validation runs.
  It saves the time, but the sealed record would be weaker than EXP-0008's.

**5. The tagging of the validation plants**
- **A. Drawn, p = 0.75 untagged per document.** The 100-sheet validation plant would be tagged with a chance of 0.25,
  and then G1-B would barely test descriptors at that scale.
- **B. The majority stratum.** VAL100g22 is untagged, and VAL1000g22 gets round(0.8 × documents), as the sealed rule
  does.

## Decision

1B, 2B, 3B, 4A, 5B.

## Rationale

- **1B, 2B, 3B are the boring options.** They have fewer moving parts, they repeat nothing that a test can prove
  equal, and each keeps a frozen or proven tool unchanged.
  - 1B keeps EXP-0008's ceiling and ledger rules.
  - 2B keeps the ingest CLI as EXP-0008 ran it.
  - 3B keeps one plant behind two ids, which is what the paired design needs.
- **4A.** The replay is the reproducibility evidence of every sealed number. The thesis claim is tested on these
  runs, and the user has put accuracy above time (consultant, 2026-10-27).
- **5B.** The gates G1-B and G1-B2 decide whether B runs sealed. They should be measured on the population the sealed
  plants mostly are: 0.8 untagged.

## Consequences

- **Makes easy:**
  - no B dry-run tool;
  - about 4 h less in P1c, and about 5 fewer corpus generations per 1,000-sheet plant (4 dry runs and 1 B build);
  - the ingest CLI and the EXP-0008 scripts stay byte-unchanged.
- **Makes hard:**
  - a cap can sit above the true need on a resumed run, and the ledger absorbs that;
  - P1 machine time is about 54–64 h (§19.10).
- **Revisit if:**
  - a stage ever starts with a warm cache, for then 1A's exact count matters;
  - the relabel test fails on a real plant;
  - P1c's replays push the run beyond what the machine can host in one sitting.
