---
adr: 0013
title: Evaluate question answering with programmatic ground truth at scale, and an LLM judge only for the ChatP&ID reproduction
status: accepted
date: 2026-09-25
accepted: 2026-09-26
supersedes: none
---

# ADR-0013 — QA evaluation method

## Context

- **No Q&A system and no evaluation harness exist** (`00-index.md`). The scoring method must be fixed
  before the harness is designed, because it decides three things: what the answering step must output,
  what the benchmark ships, and how many questions each run can afford.
- **The claim is about a ranking that changes with scale.** The metric's noise therefore matters. A rank
  swap that sits inside judge noise is not a finding. ChatP&ID's four retrieval tools span
  **0.82–0.91**, with adjacent gaps of **0.01–0.05**, measured on **19 questions** and **2 runs per
  config** (`10-literature/2603.22528.md`). The judge's own noise is not reported.
- **Two methods are published:**
  - **ChatP&ID** (`2603.22528.md`): one file (`DEXPIEX01.xml`) and **19 QA pairs** with ground truth
    written by the authors "to the best of our knowledge". Scoring is by an **LLM judge (GPT-5-mini)** on
    **4 criteria** (relatedness, completeness, correctness, coherence), each **1–5, rescaled to 0–1 and
    averaged**, plus cosine semantic similarity. The judge is from **the same family** as the answerer.
  - **PIDQA** (`make7020039-pidqa.md`, a stub from the README): **64,000 QA pairs** over **500
    single sheets**, **128 per sheet**, **4 categories**. Every question ships with **"a syntactically
    correct Cypher query"**, so the ground truth is programmatic. **Every question is scoped to a single
    sheet.**
- **Our differentiator is cross-sheet questions, not question count** (`make7020039-pidqa.md`, Relation).

## Options considered

**E1. LLM as judge, as in ChatP&ID.**

- **Case.** The result is directly comparable to 0.91. It scores open-ended categories (knowledge
  inference, summarization) that no template can check. It needs no answer format.
- **Cost.**
  - One judge call per answer, which multiplies with questions × strategies × scale points × runs.
  - The judge's accuracy is unmeasured, and a same-family judge adds bias (ChatP&ID note, Gaps).
  - At thousands of questions the judge still needs a reference answer. Those references have to be
    generated programmatically anyway, so E1 at scale needs E2's generator as well as a judge.

**E2. Programmatic ground truth, PIDQA's method.**

- **Case.** Question templates are paired with an executable reference query, and scoring is exact match
  or set match. The result is:
  - deterministic;
  - cheap per question;
  - replayable without any LLM;
  - able to scale to thousands of questions (PIDQA: 64,000).

  The questions and their reference answers become part of the public benchmark (index, supporting
  contribution 1).
- **Cost.**
  - It covers templatable categories only. Summarization and knowledge inference drop out of the scale
    experiments.
  - The answerer must emit a structured final answer, and that format constraint applies to every
    strategy.
  - It is not comparable to 0.91.

**E3. Hybrid.**

- **E1 for EXP-0001 only.** The reproduction number sits next to 0.91.
- **E2 for EXP-0002 and everything after it.** Several thousand questions are generated from the
  ground-truth plant graph. They include **cross-sheet templates whose answer requires crossing at least
  one off-page connector**, which is the thing PIDQA lacks.
- **The judge comes from a different model family than the answerer.**

## Decision

**Recommended: E3.** The design points below are for the harness design note. They are not optional
extras.

1. **Reference queries run on the ground-truth plant graph**, never on the graph the system resolves.
   The ground-truth graph is the unsplit `DiGraph`, and SMOKE-03 shows that `rejoin(split(plant)) ==
   plant` at all 7 sizes (`_results.md`). This way, cross-sheet resolution errors show up as QA errors,
   which is what the claim needs.
2. **Reference queries are plain Python functions over `networkx`, not Cypher.** Truth then does not share
   a query engine with the system under test, which runs on Neo4j. This is the boring option. PIDQA's
   Cypher-shipping variant is the alternative, and it is rejected for that coupling.
3. **Template families.**
   - ChatP&ID's templatable categories: graph query single, graph query multi, path exploration.
   - **Cross-sheet families**:
     - the neighbour across a `CONTINUES_AS` pair;
     - "which sheets show tag T" (`IdentityGroup`);
     - paths between X and Y;
     - counts over a `PlantSection` that spans sheets.
   - One **unanswerable** family (ADR-0011, item 3).
4. **Stratify every question by k**, the number of off-page connectors on the reference answer's path.
   k = 0 is the single-sheet control group. k is the variable along which the crossover should show.
5. **Scoring.**
   - Exact match for scalar answers.
   - Set precision, recall and F1 for set answers, with exact-set match reported as the strict variant.
   - Answers come as structured JSON. **A parse failure is scored wrong and reported as its own rate.**
6. **Fairness.** Every retrieval strategy ends in the **same final answer step** with the same output
   schema. CypherRAG returns rows and ContextRAG returns prose, so without a shared final step the
   formats would differ by strategy, not by retrieval.
7. **The judge reports its own accuracy.** On a seeded sample of E2 questions, run the E1 judge as well
   and report how often it agrees with the programmatic score. This bounds how much the EXP-0001 number
   can be trusted.
8. **The EXP-0001 judge configuration.**
   - The **primary** EXP-0001 number uses ChatP&ID's judge configuration (GPT-5-mini), if the funded API
     reaches it (ADR-0014). That is the comparable number.
   - A **cross-family judge** runs alongside it as a sensitivity check.
   - If GPT-5-mini is not reachable, only the cross-family judge runs, and the comparison to 0.91 is
     reported as looser.
9. **Question counts** per scale point are a parameter set from pilot variance in the design note. They are
   not fixed here. Question sampling is seeded, as the generator is.

## Rationale

- **E2 is the only method whose noise does not grow with question count.** It is also the only one that
  reaches thousands of questions per scale point within a budget that is still unknown (ADR-0014). That is
  what a rank-change claim needs.
- **Scoring against the ground-truth graph lets one number carry both parts of the claim.** Entity
  resolution and retrieval are scored together, so the pipeline-leads framing and the crossover share one
  number.
- **Keeping E1 for EXP-0001 only** preserves the one comparison the claim is built against (0.91) without
  letting judge noise into the scale sweep.
- **The cross-family judge and the judge-agreement check** address the two weaknesses the ChatP&ID note
  records: a same-family judge and self-authored ground truth.

## Consequences

**Enables:**

- a benchmark in which every answer is executable and checkable;
- per-k accuracy curves;
- abstention as a single extra column;
- runs a professor can re-score without any API access.

**Costs and limits:**

- Open-ended categories (summarization, knowledge inference) appear only in EXP-0001. The scale
  experiments do not cover them, and that is a stated limitation.
- The structured-answer requirement is a design constraint on every strategy.
- Templates are a narrower question distribution than human questions. PIDQA and ChatP&ID share this
  limit in different forms.

**Unverified: whether ChatP&ID's 19 QA pairs are published** (paper appendix or repository). Neither our
note nor any file read for this ADR says so.

- If they are published, EXP-0001 reproduces the number.
- If not, EXP-0001 reproduces **the method only**: we write our own questions on `DEXPIEX01.xml` in their
  five categories, and the comparison to 0.91 is at the level of method.
- `DEXPIEX01.xml` is itself not in the repo yet (`00-index.md`, Next action).
- **Action:** a `researcher` check of the paper's appendix and any linked repository.

**Revisit if:**

- the professor asks for open-ended questions at scale;
- the parse-failure rate dominates errors, which would mean the format is measured rather than retrieval;
- the full PIDQA text (ADR-0011, item 9) shows a template design that should be adopted.

## Outcome log

- **2026-09-26:** Accepted by the user 2026-09-26 as recommended (E3). **B2 resolved the same day:** ChatP&ID's 19 QA pairs *are* published — App. Table 1, Appendix B, pp. 28–36 of arXiv 2603.22528v1 (8 graph-query single, 2 multi, 5 path exploration, 3 knowledge inference, 1 summarization). All 8 single-query questions ask for equipment data attributes (e.g. cylinder length of T4750, shaft power of P4711), which the generated plants deliberately do not carry — so that category exists in EXP-0001 only, not in the scale question set.
