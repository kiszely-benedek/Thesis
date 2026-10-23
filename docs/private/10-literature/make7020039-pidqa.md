---
id: make7020039
doi: 10.3390/make7020039
title: "PIDQA - Question Answering on Piping and Instrumentation Diagrams"
authors: Mohit Gupta, Chialing Wei, Thomas Czerniawski, Ricardo Eiris
venue: Machine Learning and Knowledge Extraction 7(2), article 39
year: 2025
month: June
status: stub (full text not read - MDPI returned HTTP 403)
relevance: core prior art (largest P&ID QA evaluation found so far)
tags: [qa-dataset, neo4j, lpg, cypher, text2cypher, single-sheet, synthetic]
found: 2026-09-08 during the ontology sweep (ontology-landscape.md)
---

## Why this note exists

Found while answering the professor's ontology question. It was **not** on the reading list and it is the
**largest P&ID question-answering evaluation in the literature** - 64,000 QA pairs over 500 sheets, versus
ChatP&ID's 19 QA pairs over 1 sheet. It must be cited in the related-work chapter, and it changes how we
have to phrase "the evaluations in this field are tiny".

## Claim (from the abstract, verified via the ASU Pure record)

Natural-language QA on P&IDs through a three-stage pipeline: entity recognition on the image -> base entity
graph -> Labeled Property Graph "enriched with semantic attributes" -> an LLM translates the question into
**Cypher** and executes it on Neo4j. Reported: with GPT-3.5-turbo, dynamic few-shot sampling improved
accuracy by "10.6-43.5%" over schema contextualization alone.

## Evaluation setup (verified from the authors' GitHub README, `mgupta70/PIDQA`)

- **500 P&ID sheets**, from **Dataset-P&ID** (Paliwal et al., synthetic) - the same 500 synthetic pages
  that PID2Graph also uses as a test set.
- **64,000 QA pairs**; **128 questions per sheet**, 32 per category.
- Four categories, 16,000 each: simple counting, spatial counting, spatial connections, value-based.
- Ground truth is **programmatic**: every question ships with "a syntactically correct Cypher query".
  No human-authored answers.
- **Every question is scoped to a single sheet.** No cross-sheet or multi-document questions.
- Licence CC0-1.0.

## Ontology / vocabulary

**None.** The README states the symbols "are named as numbers ranging from 1 to 32" - the graph labels are
integers. No DEXPI, no ISO 15926, no RDF/OWL. (Recorded in `ontology-landscape.md` section 2.1.)

## Relation to this dissertation

- **Does not take our territory.** Scale in *questions* is not scale in *documents*: 500 unrelated
  synthetic single sheets, never joined into a plant, no off-page connectors, no cross-page ground truth.
- **It does raise the bar on evaluation size.** Our benchmark cannot ship 19 questions and claim novelty on
  scale; PIDQA shows that generating tens of thousands of template questions with executable ground truth
  is cheap. Our differentiator must be **cross-sheet** questions, not question count.
- **Method to steal:** question templates paired with a reference graph query, so ground truth is
  executable rather than hand-written. That is directly reusable for the multi-page generator, and it is a
  stronger design than ChatP&ID's "to the best of our knowledge" answers.
- **Warning for our claim wording:** "text-to-Cypher over a P&ID LPG" is now published twice
  (PIDQA 2025, ChatP&ID 2026) on single sheets.

## TODO

- [ ] Get the full text through the university library (HTML only - MDPI blocks direct fetch with 403).
- [ ] Check how the LPG schema is contextualized in the prompt, and how "high lexical diversity" is
      defined - it may be the closest thing in the literature to our prompt-serialization baseline.
- [ ] Check whether the 500 sheets have any shared tag namespace (if so, a synthetic cross-sheet set could
      in principle be derived - unlikely, but worth five minutes).
