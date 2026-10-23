---
adr: 0003
title: Accept AGPL-3.0 obligations from pyDEXPI
status: accepted
date: 2026-08-23
accepted: 2026-09-10
supersedes: none
---

# ADR-0003 — Accept AGPL-3.0 obligations from pyDEXPI

## Context

pyDEXPI is the natural choice: it is the DEXPI data model as **Pydantic classes**, with Proteus XML loading, NetworkX graph conversion, graph abstraction, SVG export and **synthetic P&ID generation** — the last being the foundation of ADR-0004's benchmark generator. It is also what the prior art uses, which makes baselines comparable.

Its licence is **AGPL-3.0** (verified 2026-08-23 from the repository README, which additionally states that commercial or proprietary use requires contacting the maintainers for alternative licensing).

**This needs stating clearly because it is easy to get wrong:** under (A)GPL, *importing a library into your program creates a derivative work when you distribute that program.* "We only use it, we do not modify it" is not an exemption. If this repository is published on GitHub while importing pyDEXPI, the repository must itself be AGPL-3.0. AGPL goes one step further than GPL: providing access over a **network** counts as distribution, so a hosted demo of the chatbot would also trigger the obligation.

## Options considered

**A. Use pyDEXPI, license this work AGPL-3.0.** Zero friction, keeps comparability with prior art, and is normal for academic work. Forecloses any later proprietary or closed use by the professor's industrial partner without relicensing.

**B. Reimplement the DEXPI subset we need.** Full licence freedom. Costs weeks of work on a solved problem, spends the novelty budget on plumbing, and risks subtle divergence from the standard that would undermine comparability.

**C. Keep pyDEXPI behind a process boundary** (separate CLI/service, data exchanged as files). A widely used pattern, but its legal standing is contested and it is not worth relying on for a dissertation.

## Decision

**Accepted 2026-09-10: A.** Use pyDEXPI and license the dissertation code AGPL-3.0.

The two open questions were put to the professor and answered on 2026-09-10 (relayed by the user):
**"we will be AGPL compliant, do not worry."** That resolves both together — no university IP policy
blocks copyleft on thesis code, and no industrial partner is expecting proprietary use. The
provisional application from 2026-09-06 therefore stands as the final state; nothing needs undoing,
and pyDEXPI may now be imported without a licence caveat.

**How it was applied, 2026-09-06 (originally provisional).** The user confirmed the work is non-commercial
research and is already public on GitHub, so option A was put into effect without waiting:
`LICENSE` (AGPL-3.0 text) added at the repository root, `license` set in `pyproject.toml`, README
licence section rewritten. The status stayed `proposed` for four days while the two questions above were with
the professor (see `50-progress/2026-W36.md`, 09-06 entry). His answer made the provisional state
permanent.

## Rationale

The dissertation's value is the method, the benchmark and the measurements — none of which are diminished by a copyleft licence. Reimplementing DEXPI to avoid it would be a poor trade of three scarce months.

## Consequences

- ~~Add `LICENSE` (AGPL-3.0) and state the pyDEXPI dependency and its licence in the README.~~ Done 2026-09-06.
- Isolate pyDEXPI usage behind a thin internal adapter module regardless of the licence outcome — good design anyway, and it keeps option B survivable if the answer to question 2 turns out to be yes.
- ~~**Ask the professor when he returns from holiday.**~~ Done 2026-09-10; answer was "we will be AGPL compliant". This ADR is closed.
- Anything that links against this code inherits AGPL-3.0, including a hosted demo of the chatbot — the network clause applies. Keep that in mind before publishing any live endpoint.
