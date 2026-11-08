---
name: study-map
description: Build or update the user's interactive learning map of the whole project — one ordered path from the problem to the demo, each station with its decisions (ADRs), design, code in reading order with what calls what, results and teaching notes — published as an Artifact. Use when the user asks for the study map, or after code, ADRs or results changed and the map must follow.
---

# Study map

The user must understand the project as an engineer, well enough to explain and defend it at the defence
(user, 2026-11-06). The map is **one path through everything**, in the order things should be learned, from the
foundations up. The user walks it station by station, skips what they choose, and asks Claude to summarize the rest.

## Sources of truth

- **Content:** `docs/private/80-study-map/study_map.json` (committed). It holds the stations and records the commit
  it describes (`"commit"`).
- **Page:** `docs/private/80-study-map/study_map.html`, rendered from the JSON and published as an Artifact. Its URL
  is kept in the JSON (`"artifact_url"`). Always republish to that URL, never create a second map.

## Start here (the page opens with it)

Before station 0 the page shows a short overview, one screen long, in plain Hungarian (user, 2026-11-07):

- **What a P&ID is**, in five or six sentences and one small labelled figure: equipment, lines, valves, instruments
  and loops, tags, sheets and off-page connectors.
- **What the project does as a whole**, as one picture of the pipeline: generated plant → sheets → plant graph in
  Neo4j → question → cascade (Cypher, then agent) → answer, with the one-sentence claim and the headline result.
- **How to read the map**: the station order and why, the seven parts of a station, the ticks, and that stations 0
  and 1 go deeper into the same ground.

Stations 0 and 1 then teach this in depth. The overview is an entry point, not a replacement for them.

## Station order (the spine)

Keep this order unless the user changes it. Add a station only when a new part of the system has no home.

| # | Station | Covers |
|---|---|---|
| 0 | Problem and claim | the thesis claim, scope, task statement, what is and is not claimed |
| 1 | P&ID and DEXPI basics | what a P&ID shows, tags, lines, loops, sheets, off-page connectors; DEXPI, pyDEXPI |
| 2 | Plant generator (v1 → v2) | seeded topology, patterns, realism decisions |
| 3 | Sheet splitting, connectors | how one plant becomes many sheets, connector labels, duplication |
| 4 | Graph schema, Neo4j ingest | node and edge types, line view, invariants, loading |
| 5 | Identity resolution (+ EXP-0004) | connector pairing, same-tagged items, tag variants, deciders D0–D4 |
| 6 | Questions and gold answers | the families, evidence, `k_identity`, splits, sealing |
| 7 | Answering strategies | ContextRAG, Cypher tier, graph-tool agent, plant API |
| 8 | The cascade | self-flag, escalation, need routing, cutoff |
| 9 | Running, cache, cost | harness, LLM client, cache and replay, spend caps, infra cost |
| 10 | Experiments in time order | EXP-0001 → 0002 → 0007 (V2T, R4, R5, INFRA-2) → 0004: question, setup, result, meaning |
| 11 | Demo | what it shows and how it uses the system |
| A | Outside the core | everything the map does not teach in depth, one line each, so nothing is lost |

## What every station holds

```json
{
  "id": "5", "title": "...", "minutes": 90, "prerequisites": ["3", "4"],
  "summary": "3-5 sentences, Hungarian: what this part does and why it exists",
  "why":   [{"adr": "ADR-0031", "title": "...", "decision": "...", "alternatives": ["..."], "status": "accepted"}],
  "what":  [{"design": "docs/private/40-design/....md", "gist": "..."}],
  "how":   [{"file": "src/plantgraph/...py", "entry": "function_name", "role": "...",
             "calls": ["a.b → c.d → e.f"], "excerpt": "<= 30 lines, optional"}],
  "proof": [{"claim": "...", "number": "...", "source": "docs/private/30-experiments/...md"}],
  "learn": [{"note": "docs/Notes/....md", "topic": "..."}],
  "fixed": [{"finding": "...", "fix": "...", "effect": "...", "commit": "..."}],
  "check": [{"q": "a professor's 'why this way?' question", "a": "a short answer"}]
}
```

- `how` lists files **in reading order**, with the entry function and the call chain. Tests appear only where a test
  explains the behaviour better than the code.
- `fixed` records the code-review findings that touched this station: what was wrong, how it was fixed, what it
  changed in the results. These are good defence material; never hide them.

## Rules

- **Prose in Hungarian, plain words**; identifiers, file names and ADR titles stay as they are.
- **Never invent a number.** Every number in `proof` names the file it comes from (`_results.md`, a run note, a report).
- **Leave out** `data/`, run scripts, caches, logs and most tests, as the user asked; list them under station A if
  they matter at all.
- **Coverage check before publishing:** every ADR in `docs/private/20-decisions/`, every design note in
  `docs/private/40-design/` and every teaching note in `docs/Notes/` appears in some station (or in A, with a reason).
  Every package under `src/plantgraph/` appears in some station's `how`. Write a short script that checks this and
  prints what is missing; fix the gaps before publishing.
- **Code links:** a GitHub permalink at the map's commit when that commit is pushed, else the repo-relative path.
- **No thesis-drafting content** (chapters, pages, deadlines) on the map; it is about the project.

## Building it the first time

1. Survey station by station with read-only agents (one per two or three stations, not more than four at once):
   each returns the station JSON for its stations from the ADRs, design notes, code, results and notes.
2. Merge, run the coverage check, fill the gaps.
3. Load the `artifact-design` and `artifact-capabilities` skills, then render the page: a left-hand path of
   stations, each expandable into its seven parts; a "megnéztem" tick per station and per item, kept with a runtime
   capability that persists state (browser storage only as a fallback); a filter for unticked items.
4. Publish, store the URL in the JSON, tell the user in Hungarian what is on the map and how to use it.

## Updating it

1. `git diff --name-only <map commit>..HEAD` plus new or changed ADRs, design notes, notes and `_results.md` rows.
2. Map each changed file to its station(s); re-survey only those; update `fixed` for review fixes.
3. Coverage check, re-render, republish to the stored URL, set `"commit"` to HEAD.
4. Tell the user in the chat which stations changed and why (the ticks they set stay).
