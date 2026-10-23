---
component: tooling/parallel-implement (skill)
status: dropped — ADR-0006 accepted with option A (sequential), 2026-09-06; kept as a rejected design
related: [ADR-0006, splitter.md, .claude/agents/coder.md]
date: 2026-09-06
---

# Design — `/parallel-implement`, a skill for running several `coder` subagents at once

Requested by the user 2026-08-31 (`50-progress/2026-W36.md`). This is **tooling, not a thesis
component**: it makes no measurement and supports the claim only through the timeline. Its whole
artifact is one markdown file, `.claude/skills/parallel-implement/SKILL.md`. No Python, no new
dependency. If it does not pay for itself in three uses, delete it (see §7).

## 1. Input and output

**In** — a finished design note path: `/parallel-implement docs/private/40-design/<name>.md`.
Optional `--wave <n>` to run one wave only.

**Out**
- a plan file `docs/private/40-design/<name>-tasks.md` — the wave table and file-ownership map,
  written *before* any subagent starts and shown to the user for a yes/no;
- the implemented source and tests in the working checkout;
- one appended entry in `docs/private/50-progress/<year>-W<week>.md`;
- a merged-result report in the chat: gate output, repair rounds, deviations from the design.

Planning, wave decomposition, gate-running and the readability pass stay in the **main Opus
session**. Only implementation tasks go to `coder` subagents, which are **Sonnet** by frontmatter
(`.claude/agents/coder.md`). The orchestrator is not a subagent — it needs the design note, the
ADRs and the conventions already in context.

## 2. When to parallelize — the rule

Run a parallel wave only when **all four** hold:

1. **≥ 3 tasks** that are independent *after* the shared contract exists — no import edge and no
   specification edge between them.
2. **Each task ≥ ~100 lines** of source plus tests. Below that, writing the brief costs about what
   writing the code costs.
3. **The contract is frozen** — Pydantic models, function signatures and any node-attribute
   convention are already written down (in the design note, or produced by a preceding wave-0
   task). A parallel wave over an unfrozen contract multiplies one wrong assumption by N.
4. **The design note has no open questions left.** `splitter.md` closed all four on 2026-08-25;
   that is the bar.

Fail any one → run sequentially and say so. The skill must be allowed to refuse its own premise.

A **specification edge** is the dangerous one because it is invisible in the import graph: two
modules that must agree on a convention neither of them owns. Treat it exactly like an import edge.

## 3. Worked example — the splitter

Modules from `splitter.md` §2, re-laid-out so each task owns its own file (this also respects the
400-line cap: `benchmark/models.py` is already 304 lines, so splitter models get a new package).

```
src/plantgraph/benchmark/splitter/
    models.py                   SplitConfig, OffPageConnector, SheetGraph, OPC stub-node contract
    strategies/flow_greedy.py   strategies/modularity.py
    strategies/utility_aware.py strategies/random_split.py
    strategies/__init__.py      the registry — orchestrator-owned, never a parallel task
    split.py                    orchestration: partition → cut → insert OPCs → manifest
    rejoin.py                   the inverse, used by the round-trip test
```

| Wave | Mode | Tasks | Why |
|---|---|---|---|
| 0 | **sequential**, 1 agent | `splitter/models.py` + its tests | Everything imports it. This *is* the contract, including the exact attributes an OPC stub node carries. |
| 1 | **parallel**, 3 agents | T1 `flow_greedy.py` + `random_split.py`; T2 `modularity.py`; T3 `rejoin.py` | Disjoint files, no import edge, each ≥100 lines with tests. `random` rides with `flow_greedy` because both spend the same sheet budget and must count it identically — a specification edge. |
| 2 | **sequential**, 1 agent | `utility_aware.py`, `split.py`, `strategies/__init__.py`, `__main__.py`, the round-trip property test | `utility_aware` *is* `flow_greedy` after hub extraction — import edge. `split.py` must satisfy the `rejoin.py` from wave 1, so it goes last and can read it. |

Two consequences worth stating plainly:

- **Writing `rejoin` before `split` is deliberate.** `rejoin` is defined entirely by the manifest
  contract, so it parallelizes cleanly, and having it exist first turns `rejoin(split(G)) == G`
  into a real acceptance gate for wave 2 rather than a test its own author wrote to pass.
- **The splitter only just clears the bar** — one wave of three. The expected saving is modest, and
  the honest reason to run it here is that it is a low-risk first exercise of the skill. The
  component that will actually repay it is `retrieval/*`: four strategies (ContextRAG, VectorRAG,
  PathRAG, CypherRAG) behind one interface, no import edges, all four needed before any crossover
  number exists. That is the textbook case, and it is the one the claim depends on.

## 4. How subagents avoid colliding — strict file ownership, one checkout

**Recommendation: strict file ownership in the shared checkout, after a contract-first wave 0.**
Not worktree isolation. The alternatives and the argument are in **ADR-0006**; the load-bearing
facts, checked on this repo 2026-09-06:

- `docs/private/` and `.claude/` are **untracked**, so a fresh worktree contains neither the design
  note nor the `coder` agent definition — the subagent would be briefed from nothing.
- `.venv/` is gitignored, so every worktree pays its own `uv sync` before it can run a test.
- Subagent worktrees branch from the **default branch**, not the parent session's `HEAD`, unless
  `worktree.baseRef` is set to `"head"`. This checkout currently carries 834 uncommitted insertions
  across 14 files that such a worktree would not see.
- Merge-back is N branches, which turns the one professor-readable PR into N.

Ownership rules, restated in every brief:

- A task **may write only the files listed in its brief**. Everything else is read-only.
- **Orchestrator-owned, never touched by a subagent**: `pyproject.toml`, `uv.lock`, any
  `__init__.py` acting as a registry, `docs/**`, `.claude/**`, `.gitignore`. A task that needs a new
  dependency **returns the request**; it does not run `uv add`.
- No task commits, branches, or runs `git` beyond read-only inspection. The user commits.
- Two tasks never own the same file. If the decomposition cannot achieve that, the wave is wrong —
  merge those tasks and run them sequentially.

## 5. The brief and the return

**Brief** — constructed by the orchestrator, one prompt per subagent:

1. **Task id and a one-sentence goal.**
2. **The design-note section, quoted inline** — not a path to go and read. The subagent must not
   have to reconstruct context, and quoting keeps every agent looking at the same words.
3. **Files it owns**, exact paths, source and test, plus the sentence that all else is read-only.
4. **The interface it must implement**, as literal signatures, plus the models it must import from
   the wave-0 contract file and must not redefine.
5. **The tests it must make pass** — named test functions and the fixtures it may assume, or an
   explicit instruction to write them where the design leaves the cases to the implementer.
6. **The conventions, compressed**: Hungarian docstrings / English identifiers, 400-line cap, two
   nesting levels, `uv run` for everything, no silent failures. (`coder.md` carries these already;
   the brief names them so a truncated context cannot lose them.)
7. **What not to do**: no edits outside owned files, no `uv add`, no `git`, no `mypy` run.

**Return** — a fixed six-part report, no free-form prose:

1. files created/modified, with line counts;
2. the public API actually implemented, as signatures;
3. test names and the real `uv run pytest <own test paths>` output — pass counts, not adjectives;
4. `uv run ruff check <own files>` and `uv run ruff format --check <own files>` results;
5. **deviations from the design**, or the explicit sentence that there were none;
6. open questions, and any dependency it wanted but did not add.

`mypy --strict` is configured over all of `src`, so a subagent running it would see failures caused
by siblings that do not exist yet. Type checking is an integration gate only (§6).

## 6. Verification before the user sees it

The **orchestrator** runs this in the main checkout after every wave, in order, and reports the
actual output:

1. `uv run ruff format --check .`
2. `uv run ruff check .`
3. `uv run mypy`
4. `uv run pytest`
5. **line cap** — every touched file under 400 lines; report the largest.
6. **Readability and consistency pass** — the one gate no tool runs, and the reason the orchestrator
   is Opus. It looks for exactly the failure mode parallelism introduces: the same helper written
   twice under two names, one concept carrying two names across two files, docstrings that are
   grammatical Hungarian but assume the reader already knows what an off-page connector is, and a
   diff that reads in several voices. Fix by rewriting, not by asking the subagents again.

**On failure.** The failing command and its output go back to the *owning* subagent, once. If the
same task fails a second time, the orchestrator finishes it sequentially and records in the progress
log which task it was and why — a task needing two repair rounds is evidence the decomposition was
wrong, and that is worth more than hiding it. **Never** send two agents at the same file.

The skill commits nothing. The user reviews the diff and commits, so the professor still sees one
coherent pull request.

## 7. Invocation, logging, and how the skill measures itself

```
/parallel-implement docs/private/40-design/splitter.md
```

Steps: read the design note → derive the module DAG → apply §2 → write the plan file → **ask the
user to confirm the plan** (a cheap human gate before N agents spend tokens) → wave 0 → gates →
wave 1 in parallel → gates → wave 2 → gates → readability pass → progress-log entry.

The log entry records, per run: the design note, the wave table (task, files owned, outcome), the
gate results as numbers (tests passed, largest file, gate failures), **repair rounds per wave**, and
wall-clock per wave. That last pair is the skill reporting its own accuracy — the only honest
question about a parallelism tool is whether coordination cost exceeded the saving. Decide after
three runs: if any run needed more than one repair round in a wave, or a wave came out slower than
the sequential estimate, drop the skill and keep the file-ownership discipline, which is worth
having on its own.

## 8. Which part of the claim it serves

Indirectly, and only through the timeline: phases 2–4 each contain a four-way independent structure
(four retrieval strategies, several corruption types, several metrics) on a three-month budget. It
buys nothing for the claim by itself, which is why its novelty budget is zero and its whole
implementation is one markdown file.

## Open questions for review

1. **Three concurrent agents, or two?** Wave 1 above assumes three is comfortable. Running several
   subagents at once multiplies token usage, and the user has been working against a usage window
   (`2026-W36.md`, 08-31). *Recommendation: cap the skill at three concurrent subagents and have it
   refuse a fourth.*
2. **Does the plan file survive review?** It is written under `docs/private/40-design/`, which is
   untracked and therefore invisible to the professor. *Recommendation: keep it anyway — it is the
   audit trail for us; the professor's audit trail is the PR diff plus ADR-0006.*
3. **Splitter model placement.** This note assumes a new `benchmark/splitter/models.py` rather than
   extending `benchmark/models.py` (304 of 400 lines used). That changes `splitter.md` §2 and needs
   the user's yes before wave 0 runs.
