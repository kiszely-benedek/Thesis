---
adr: 0045
title: Regenerate the H100 test corpus from an unseen generator seed
status: accepted
date: 2026-10-04
amends: ADR-0015 (headline corpora), ADR-0035 (test corpora)
---

# ADR-0045 — H100 gets a fresh, unseen seed

## Context
PAID-01…04 and PG-P1 ran on H100 (seed 0), a **test** corpus, with dev families. Their failures (T-11-1, P-3-1,
LOOP_ACTUATED_VALVE) were inspected and drove general fixes (plant rendering, legends, primer, ADR-0044). The H100
results on dev families are therefore no longer independent (leakage). ADR-0044 regenerates every corpus anyway.

## Options
- **(a)** keep seed 0 and state the leakage as a limitation.
- **(b)** regenerate H100 from a seed no run has used, same headline preset and target size.

## Decision
**(b)**, user, 2026-10-04 (in chat). H100 = headline preset, `--target-sheets 100`, generator/split **seed 2**
(seeds 0 and 1 are used by H1000 and the dev corpora). H1000 keeps seed 0 — no paid run touched it, and its free
checks selected nothing (ROUTE-01's rule chose on D1000). Questions on H100 are generated only for the free checks
until F1; no paid run on H100 before the sealed run. The old seed-0 H100 results stay in `_results.md` as history.

## Consequences
Every H100 free check (API-01/02, NEED-00, ROUTE-01, PG-01, AVAIL-01) is re-run on the new corpus; Neo4j is wiped
and reloaded with the new H100. Teaching note: `docs/Notes/fejlesztoi-es-tesztuzem.md`.
