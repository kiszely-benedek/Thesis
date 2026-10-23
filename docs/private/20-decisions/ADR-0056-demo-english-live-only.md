---
adr: 0056
title: Make the demo English and live only — a fresh live cascade with an empty in-memory cache for every ask, an explicit plant switch that reloads Neo4j, the ask's real trace recorded by a demo-owned HTTP transport and shown as an interactive route view, a title-block design system, tag lookup and a presentation mode; no replay, no comparison across plants, no session history
status: accepted (user, 2026-10-16)
date: 2026-10-16
supersedes: in part ADR-0055 — decision 3A (the demo reads the merged cache), decision 4A's language and "free replay" reason, decision 8A's language, decision 1A's replay rationale, the eager paid open, the agent-only D100 mode, U1, U3, U4. ADR-0055's other decisions (1A's rule, 2A, 5A, 6A, 7A, 8A's mechanism) carry over unchanged.
design: 40-design/demo-polish.md revision 2 (§17–§27)
---

# ADR-0056 — Demo: English, live only, explicit plant switch

## Context

On 2026-10-16 the user asked for a demo that is beautiful and understandable for a non-specialist and useful for a
P&ID engineer, accepted an intro box, glossary tooltips and a presentation mode, asked with high priority to see
"how the model got there" interactively, and decided:

- **The demo is English.** The chat and the thesis stay Hungarian. For the record, PARA-R1 measured Hungarian
  rewordings at least as well answered as English (cascade_v3 on D100: hu 142/144, en 102/108, `_results.md`); the
  switch is an audience choice. Carried out in DP-T11 (`b068363`).
- **Live only — no cache replay, ever.** Stored answers returned in a fraction of a second, when the measured median
  is several seconds, misrepresent the system.
- **A plant is chosen deliberately, then all questions go to that plant.** Switching plants is an explicit action;
  no reload inside an ask, no bouncing between D100 and D1000.

Constraints: the F1 freeze (only `src/plantgraph/demo/`, demo tests and `data/runs/cv1/demo/` may change); Neo4j
holds one plant at a time (user rule; D1000 now); the frozen paid client always reads its SQLite cache first
(`llm/client.py`, `qa/harness/clients.py`) and has no switch to turn reads off; `LiveAnswer` carries the answer,
per-tier figures and the sheets read, not the agent's path, the Cypher text or rows.

## Options considered

**1 — Running with no cache reads**
- **A. A fresh cascade per ask from the frozen `open_live_cascade` with `cache_path = Path(":memory:")`: each client
  gets a private, empty, in-memory SQLite database; the cascade is closed after the job; a per-call `from_cache`
  guard proves it.** Correct by construction; the open time per ask is unmeasured and shown separately.
- B. A temporary cache file per ask, deleted afterwards. Same effect; files on disk, Windows file-lock risk.
- C. One cascade per plant, reopened only before an ask whose exact text it has already seen. Cheaper; relies on
  every request carrying the question text (unverified).
- D. A write-only mode in the LLM cache or client. Changes frozen code.
- E. Keep the merged cache and label replays as stored. Rejected by the user.

**2 — Which plant Neo4j holds**
- **A. An explicit plant switch: selecting the other plant starts a load job (wipe the held plant, `load_corpus` with
  the plan the demo already built — public, frozen functions) with a visible phase and its measured time; asking is
  disabled while it runs; an ask on a plant the database does not hold is refused, never auto-loaded; the demo starts
  on the plant Neo4j holds.** The recorded load stage: 2.25 s (D100), 8.59 s (D1000), `neo4jplant/D*/ingest.json`;
  the D1000 wipe is unmeasured.
- B. Load inside the ask when needed (the architect's first proposal). Rejected by the user: it hides a reload inside
  a question and invites bouncing between plants.
- C. Only D1000 can be asked. No live small-versus-large view at all.
- D. D100 agent-only with a notice. Not the evaluated cascade.
- E. Spawn the ingest CLI. Regenerates the plant (INFRA-1 full ingest 26.1 s at D1000) and writes new records.

**3 — Where the real trace of an ask comes from** (the query and the rows; each tool call, its arguments and what
came back)
- **A. A demo-owned recording HTTP transport.** The demo already passes an `httpx2.Client` through
  `open_live_cascade` to `openai.OpenAI(http_client=…)`; a wrapping transport keeps every request and response body.
  The agent resends the whole conversation each step (observations are `user` messages) and the Cypher final step's
  prompt holds the rows as JSON lines, so the trace is complete as the model saw it, with no frozen change. Joined
  with the call log for purpose, cost and cache flag. Limit: rows only as far as the prompt held them (row cap).
- B. The per-ask in-memory cache. It stores the cache key (a hash of the request) and the response only: replies
  without rows or tool results.
- C. The call log alone, plus re-running the deterministic plant-API primitives locally. Tool results would be a
  re-run, not what the model saw.
- D. Expose the strategies' traces through `LiveAnswer`. Changes frozen code.

**4 — Label file name.** **A. `labels.en.json`** (done in DP-T11); B. `labels.json` (language implicit); C. keep
`labels.hu.json` with English content.

**5 — Theme.** **A. Light and dark token sets; the system setting decides by default, plus a manual three-way toggle**
(user, Q5); B. media query only; C. light only.

**6 — Fonts.** **A. System stacks only, Bahnschrift (ships with Windows) as the title-block label face**; B. one
`system-ui` stack; C. a vendored web font.

**7 — Same question on the other plant**
- A. The other plant's example of the same family, asked live after the first, with a reload between.
- **B. Drop it.** It requires switching plants within one comparison, which contradicts "one plant, then all
  questions to it; no bouncing" (user, Q1). The measured scale effect stays on the Results tab.

**8 — Showing the route**
- **A. An interactive route view: the items the model saw, step by step (from the recorded trace), with the direct
  drawing edges between them from the demo's item graph; deterministic time-layered layout; step through and watch
  the explored part grow; the answer (and a path answer's hops: solid, sheet-crossing, or dashed when no direct edge)
  highlighted; hover for tag, class, sheets; click to jump the PDF.**
- B. Only the answer's items and the edges between them. Shows the result, not the route.
- C. A demo-computed shortest path between the asked items. Looks like the system's reasoning while it is not.
- D. A text step list only. Kept as the first version (DP-T7) until the graph lands.

**9 — Tag lookup.** **A. A server route over the loaded item graph**; B. ship a tag-to-sheets table to the page;
C. ask the model.

**10 — Session history.** A. `sessionStorage`, labelled entries. **B. None** — dropped by the user ("why would we
need it?").

**11 — Presentation mode.** **A. Sequences in the local `demo_config.json`, one plant per sequence (no reload
mid-sequence), every step asked live** (confirmed by the user); B. no presentation mode.

## Decision

1A, 2A, 3A, 4A, 5A, 6A, 7B (dropped), 8A, 9A, 10B (dropped), 11A. Also: typed questions stay FREE_TEXT and an
unchanged example keeps its type so it can be scored (ADR-0055 1A's rule); examples are English (D100: the 36 English
originals of the PARA-R1 base; D1000: `examples/D1000.jsonl`) and run live with their reference and verdict;
plain-English class names; the replay path (`--replay-only`, `needs_paid`, `tier2_only`, `cache_path`, the
`seed-cache` and `coverage` commands) is retired; the k / u explanation follows the `Question` field definitions
(k counts evidence edges that cross sheets, not sheets). The English wording drafts are accepted as written (Q4).

## Rationale

No novelty is spent: each choice is the plainest that keeps the frozen system untouched and the screen honest. 1A,
3A and 8A show exactly what one live ask of the evaluated cascade does, sees and costs. 2A keeps the real two-tier cascade on
whichever plant is chosen, honours the one-plant rule, and makes the reload a deliberate, visible act instead of a
hidden cost inside a question.

## Consequences

- Every ask is a paid call (about $0.0005 each: $0.01865 for 36 live D1000 asks in the ADR-0055 warm-up, divided by
  36) and takes seconds; the card shows answer time, model time, cost and preparation time separately.
- Switching plants takes a load (a few seconds for D100, about 9 s plus the wipe for D1000); a session should end on
  D1000.
- Coders make no paid call; every live check is the user's, after DP-T7.
- Coder tasks: DP-T12 → DP-T13 → DP-T14 → DP-T6 → DP-T7 (the user tries the demo; the trace as a step list) →
  DP-T18 → DP-T19 (the interactive route view) → DP-T8 → DP-T9 → DP-T10 → DP-T15 → DP-T16 → DP-T20; DP-T11 done
  (`b068363`); DP-T17 dropped.
- **Revisit if** the per-ask open is slow (→ 1C), the D1000 wipe makes a switch too slow to show, or the request or
  call-log format changes (unparsed parts are kept raw and flagged).
