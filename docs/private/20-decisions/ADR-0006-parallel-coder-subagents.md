---
adr: 0006
title: Run coder subagents sequentially; planning on Opus by default, Fable 5.1 on explicit request
status: accepted
date: 2026-09-06
supersedes: none
---

# ADR-0006 — `coder` subagents run sequentially; planning on Opus by default, Fable 5.1 on explicit request

> **Accepted 2026-09-06 with option A, not the proposed B.** The user dropped the parallelism request
> and kept only the model-assignment part. The options and the rationale for B below are preserved as
> written on 2026-09-06 so the reasoning stays auditable; the decision that stands is under
> *Decision*. Note also that context point 2 is stale: `docs/private/` and `.claude/` have been tracked
> since the publish commit of 2026-09-05 (`daaa826`), and the working tree was clean at acceptance.

## Context

The user asked on 2026-08-31 for a way to run several Sonnet `coder` subagents in parallel on
implementation work, with planning staying on Opus (`50-progress/2026-W36.md`). The splitter is the
first candidate job and the four retrieval strategies in phase 3 are the real one.

Three constraints make this non-obvious.

1. **The professor reads every pull request.** Parallelism has one characteristic failure mode —
   the same helper written twice under two names, one concept named two ways, a diff that reads in
   several voices. That is a review failure, not a test failure, and no gate in `pyproject.toml`
   catches it.
2. **This repository is unusual in what it tracks.** Checked 2026-09-06: `docs/private/` and
   `.claude/` are **untracked**, `.venv/` is gitignored, and the working tree carries 834
   uncommitted insertions across 14 files. Anything that starts from a clean checkout starts
   without the design notes, without the agent definitions, without an environment, and behind the
   user's actual work.
3. **Timeline, not capability, is the reason to do this at all.** The skill measures nothing and
   contributes nothing to the thesis claim. Its budget is one markdown file.

## Options considered

**A. Do not build it — keep running coders sequentially.** Zero coordination cost, one voice in the
diff, one context that accumulates the conventions as it goes. Costs wall-clock on genuinely
independent work, and on a four-way component like `retrieval/*` it serializes work that has no
reason to be serial.

**B. Parallel subagents with strict file ownership in the shared checkout.** A contract-first
sequential wave 0 freezes the models and signatures; each parallel task then owns a disjoint list of
files and may write nothing else; the orchestrator (main Opus session) owns `pyproject.toml`,
`uv.lock`, registry `__init__.py` files and all docs, runs every gate, and does the readability
pass. No git operations by subagents. Cheap, no infrastructure, and the merged result is one PR.
Its weakness is that isolation is by discipline rather than by mechanism — a subagent that ignores
its brief can write outside its lane, and only the diff will show it.

**C. Parallel subagents with `isolation: worktree`.** Claude Code supports `isolation: worktree` in
subagent frontmatter and enforces it mechanically: file edits into the main checkout are blocked, as
are git redirects out of the worktree. Collisions become impossible rather than merely forbidden.
Costs, all confirmed against the Claude Code docs and this repo: a worktree is a fresh checkout, so
`docs/private/` and `.claude/` (untracked) and `.venv/` (gitignored) are absent unless a
`.worktreeinclude` copies them; subagent worktrees branch from the **default branch**, not the
parent session `HEAD`, unless `worktree.baseRef` is set to `"head"`, so they would not see the
current uncommitted work; and merge-back is a manual merge of N branches.

**D. Built-in multi-session machinery — agent teams, or the `/batch` skill.** `/batch` splits one
change into 5–30 worktree-isolated subagents that each open a pull request; agent teams give a lead
plus messaging teammates, but do not isolate teammates in worktrees, so file partitioning is needed
there anyway. Both are built and maintained by someone else. Both are sized for changes an order of
magnitude larger than anything in this repository, and `/batch`'s PR-per-task shape is the opposite
of what the professor's review needs.

## Decision

**Option A — do not build the parallel skill.** `coder` subagents run one at a time, each on a
finished design note, exactly as before. The design in `40-design/parallel-coder-skill.md` stays on
file as a rejected design; nothing in `.claude/skills/` is created for it.

**Model assignment, which is the part the user kept:**

| Role | Model | When |
|---|---|---|
| Planning, architecture, ADRs (`architect`, and the main session when it plans) | **Opus** | default |
| Same roles | **Fable 5.1** | only when the user says so for that task, and while Fable credits last |
| Implementation (`coder`) | **Sonnet** | always |

Falling back from Fable to Opus (credits exhausted, or the user did not ask for Fable) needs no
decision and no note. Moving implementation off Sonnet would need a new ADR.

## Rationale

The user's call, 2026-09-06, and it matches the ADR's own analysis of A: "genuinely defensible",
zero coordination cost, one voice in the diff, one context that accumulates conventions. The case for
B rested entirely on `retrieval/*` in phase 3, months away; building tooling now for a wall-clock
saving then is speculative, and the professor's review — one coherent voice per pull request — is
the constraint that actually binds. The four open questions the proposed version carried
(concurrency cap, splitter model placement, plan file, acceptance) are moot; `splitter.md` §2 stays
as written.

Planning on the strongest available model and implementation on the cheapest adequate one is the
same policy that has been in the agent frontmatter since the start (`architect: opus`,
`coder: sonnet`); this ADR only writes it down and adds the Fable override rule.

## Consequences

**Enables** — nothing new to build or maintain; the splitter starts immediately as an ordinary
sequential `coder` run.

**Costs** — independent tasks in phase 3 are serialized. Accepted.

**How the override is applied** — the `architect` frontmatter keeps `model: opus`. When the user asks
for Fable on a planning task, the main session passes `model: "fable"` in the Agent call for that
task only. If the main session itself is running on Fable 5.1 (as on 2026-09-06), that already
counts as "the user said so" for planning done directly in the session, not for subagents.

**Revisit when** — phase 3 has four retrieval strategies specified and frozen and the timeline is
actually short. Then the rejected design is the starting point, and a new ADR supersedes this one.

## Outcome log

**2026-09-25 (user).** *"please update so I can use opus 5.5."* The policy is unchanged in substance —
planning on the strongest available model, implementation on the cheapest adequate one — but the wording
now says **"the latest available Opus"** instead of naming a version, and records **Opus 5.5 at high
reasoning effort** as the current planning model. This ADR is **not** superseded: nothing about the
sequential-coder decision or the Fable override changes. Model *selection* happens in the user's client
(`/model`), not in this repository; this entry only records which model the policy intends.
