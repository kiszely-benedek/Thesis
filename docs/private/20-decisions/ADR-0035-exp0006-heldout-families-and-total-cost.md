---
adr: 0035
title: Measure generalisation with sealed held-out question families behind a hash-recorded freeze, count every call in a question's cost, and pre-register EXP-0006's claims
status: accepted
date: 2026-10-02
supersedes: none — extends ADR-0013 (new families and BOOLEAN answers, still programmatically scored), ADR-0029 (same k, u and bins) and qa-system.md §11 (total cost per question)
design: 40-design/question-aware-retrieval.md §8–§11
---

# ADR-0035 — EXP-0006: unseen question types, total cost, pre-registered claims

## Context

The user wants the plant queryable with "very many kinds of questions", including unforeseen ones, and wants every
retrieval option measured. ADR-0033 and ADR-0034 add arms whose whole point is generalisation and cost. Two things
are missing to measure that honestly:
1. **A set of question types no strategy author has seen.** Today all 12 families are visible to whoever writes a
   rule, a prompt or a primitive; any of them can be fitted to the benchmark.
2. **A per-question cost that counts every call.** Today only the final call's tokens, cost and latency reach
   `QuestionResult`; CypherRAG's query call and Hierarchical's router call are dropped, and retrieval calls are
   logged without a question id (`harness/runner.py`, read 2026-10-02).

## Options considered

**A. No held-out set** — all new families visible. Cheapest; the generalisation claim becomes untestable.

**B. Write a pool of new families now, split them at random into dev and held-out after the strategies are built.**
Fair in principle, but strategy authors would have read the whole pool while writing rules and prompts.

**C. A sealed held-out specification written now, its sha256 recorded here, opened only by one coder task after a
freeze (F1) that hashes every strategy-side file and parameter; the visible new families (the user's own examples)
are dev families.** Held-out questions are generated on test corpora only.

**D. As C, plus a second held-out set written after F1 by a fresh `researcher` session that never saw the design or
the code, from external sources.** Strongest, more work; kept as a should-item on top of C.

For cost: (a) each strategy sums its own calls in its trace; (b) a harness-side meter brackets each question and
counts every call made through the run's client; (c) a post-hoc join of `calls.jsonl` by time. (a) relies on every
strategy author remembering; (c) is fragile.

## Decision

**C (D as should-tier), and cost option (b).**
1. **Sealed file:** `40-design/heldout-families.sealed.md`, sha256
   `905c7984dfc1d346cb696c47590d972d545455fd1149517534ad2309955ff63b` (2026-10-02). Six families and ten held-out
   wordings of dev families, each with a reference function over the ground-truth plant, evidence for `k`/`u`, an
   answer type from the existing set (`BOOLEAN` is added with the visible families first), and gold need labels.
2. **Splits:** dev-old (12 built families), dev-new (6 visible: connectivity, downstream within a unit, instruments
   of an item, upstream sources, same unit, loops near an item), held-out (sealed), held-out wordings (sealed,
   should).
3. **Freeze F1** before the seal is opened: `data/freeze/qar-freeze.json` with the hashes of every file under
   `qa/plant_api/`, `qa/need/`, `qa/agent/`, `qa/strategies/`, `qa/prompts/` and the shared selection, serializer
   and final-step modules, the parameter values, and the commit. A test asserts them. A later change makes every
   held-out number "post hoc" and needs a new ADR.
4. **Total cost:** `QuestionResult.retrieval_usage: CallUsage` filled by a harness `UsageMeter`; retrieval calls
   logged with the question id; local compute time in `timings.jsonl` (wall-clock, kept out of `answers.jsonl` so
   replay stays byte-identical). Reported per question: total cost (as first billed), tokens, latency p50/p90.
5. **Pre-registered claims** (all at 95 % paired-bootstrap CIs over questions unless stated; reported either way):

| # | Claim | Supported if | Wording if not |
|---|---|---|---|
| Q1 | Question awareness helps on known types | at H1000, dev families: `hierarchical_need_rules` − `hierarchical` > 0, CI excludes 0 | "no measurable gain on known types" |
| Q2 | It degrades gracefully on unknown types | at H1000, held-out families: the same difference has a CI that contains 0 or lies above it | "question awareness costs accuracy on unseen types" |
| **Q3 (primary)** | **The combination is the scalable answer** | at H1000, held-out families: `hier_agent` is not worse than `graph_agent` and not worse than the best `hierarchical_need_*` (CIs contain 0 or lie above), better than at least one of them (CI excludes 0), and its mean total cost per question ≤ `graph_agent`'s | **refuted** if any arm beats it with a CI excluding 0 at lower or equal mean cost; otherwise "not confirmed" |
| Q4 | Scale robustness | per arm: accuracy(H1000) − accuracy(H100) has a CI that contains 0 or lies above, and cost elasticity `e = ln(c1000/c100) / ln(sheets1000/sheets100)` < 0.5 (threshold chosen here: half of linear growth) | "accuracy falls with scale" / "cost grows near-linearly with the plant" |
| Q5 | A typed plant API beats free-form querying | at H1000, all families: `graph_agent` − `cypher_rag` > 0, CI excludes 0; and − `cypher_agent` if it runs | "free-form Cypher matches the typed API" |

   Also reported, not claimed: the generalisation gap (dev − held-out accuracy, unpaired bootstrap) per arm; the cost–
   accuracy frontier per corpus; need accuracy per classifier; the cascade; per-family tables. Five claims on shared
   questions means some CI may exclude 0 by chance; Q3 is the one primary claim.
6. **Free metrics choose, paid runs confirm**, as ADR-0030: every variant is measured free where possible (NEED-01,
   API-01/02, gates N1/N2); paid runs go to the arms named in the design note §10.4, under the ADR-0019 answer pin.

## Rationale

- The thesis claim is that the best strategy depends on the setting; a strategy that only wins on question types its
  author saw is a fit, not a system. The seal plus the freeze is the cheapest arrangement a reviewer can audit: one
  hash before, one manifest at the freeze.
- Q3 is stated so it can fail: the combination must beat something and lose to nothing at its cost.
- Without the cost fix, every multi-call arm (CypherRAG, the router fallback, all agents) would look cheaper than it
  is, and "low cost" — half of the user's vision — could not be measured.

## Consequences

- Easy: the professor can verify the held-out file is unchanged (sha256) and that no strategy file changed after
  the freeze (manifest).
- Hard: the architect wrote the labels, the primitives and the sealed families in one session — a stated threat;
  the label rule and the primitives' completeness argument are written down in the design note so they can be
  judged. One sealed family is deliberately outside the primitives (a boundary probe).
- Money: at listing prices the minimum EXP-0006 plan costs about $2.7–$25 depending on the answer pin (design note
  §10.4, **estimate**), against a $5 balance that also pays for the headline. The sample size and the pin are user
  decisions.
- `QuestionResult` gains a field; old rows parse (default `None`). No reported run exists yet, so no reported number
  changes.
- **Revisit if** a frozen file must change after F1 (new ADR; held-out numbers relabelled post hoc); a held-out family
  turns out unscorable at H1000 (dropped and reported, never replaced by a new one after results are seen); or the
  budget forces fewer arms than Q3 needs (then Q3 is reported as not run, not weakened).

**Accepted 2026-10-02 (user, in chat), with the main session's recommendations.** U1: 20 questions per family per corpus, **executed in stages** (10 first, extended to 20 only if the first half is informative); U2: the user topped up to $25 total — runs must be budgeted, staged and stopped early when results are clearly poor; U3: classifier pin glm-5.3-flash (logprobs per the 2026-10-02 snapshot); U4: QAR-T1 → T2–T5 (free) → J-tasks → T6–T9; U5: `cypher_agent` should-tier. The answer model is chosen in ADR-0019 from cheaper candidates, not assumed to be gpt-5-mini.
