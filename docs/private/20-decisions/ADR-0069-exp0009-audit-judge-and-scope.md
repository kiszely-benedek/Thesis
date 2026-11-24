---
adr: 0069
title: Judge EXP-0009's B stratum through an EXP-0009 judge entry point with two added answer-type help lines, and draw the main audit sample from scope R only
status: accepted (main session under the user's session authority, 2026-11-24; to be confirmed by the user in the chat report)
date: 2026-11-24
supersedes: none. Amends ADR-0068's audit section and PREREG A §Audit.
design: 40-design/exp0009-launcher-review.md (B2, F9); 40-design/generator-v2-2-handbook-rules.md §19
---

# ADR-0069 — The EXP-0009 audit judge and the audit scope

## Context

The second read-only review of the EXP-0009 launcher, at `501fcdd`, found two audit problems that need a design choice.

- **B2.** The frozen judge (`qa/audit/judge.py`) has help text only for the answer types of EXP-0008. The B stratum holds only VALVE_SET and POSITION rows. The judge would therefore raise a `KeyError` on its first B row.
- **F9.** The main audit sample is drawn from the A2 sealed runs, and these include A2's scope X rows. A2 cannot name an untagged valve. Its scope X answers are therefore wrong by construction, which says nothing about the scorer. Auditing these rows would spend audit money on rows whose scorer verdict is not in doubt.

## Options

**B2: how to judge the B stratum.**

| | Option | Assessment |
|---|---|---|
| (a) | Edit the frozen judge template | Changes the pre-registered prompt sha256 `b56c89d5…`. Rejected. |
| (b) | Add an EXP-0009 judge entry point | It reuses the template file unchanged and adds two answer-type help lines (VALVE_SET, POSITION) in code. |
| (c) | Drop the B stratum | Loses the only scorer check on B's new answer types. Rejected. |

**F9: what the main audit sample covers.**

| | Option | Assessment |
|---|---|---|
| (a) | Keep scope X in the main sample | Pays for rows that are wrong by construction. Rejected. |
| (b) | Draw the main sample from scope R only | The B stratum covers scope X's answer types. |

## Decision

1. **B2 = (b).**
   - `qa/exp0009/` gets a judge entry point. It builds the prompt from the unchanged template file and the frozen help lines, plus one help line each for VALVE_SET and POSITION.
   - The template sha256 `b56c89d5…` and the judge pin sha256 `e4794d07…` stay as pre-registered.
   - The two added lines are recorded verbatim in an amendment to PREREG A, and their sha256 is recorded with them.
2. **F9 = (b).**
   - The main audit sample is drawn from scope R rows of the A2 sealed runs only.
   - The B stratum is half the size of the main sample. It is drawn from VALVE_SET and POSITION rows.

## Consequences

- The PREREG A audit section is amended before P0. The amendment records what changed and why; no plant has been built and no run has started.
- The launcher fix task T13c implements this, together with the review's other blockers.
