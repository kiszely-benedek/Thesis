---
topic: Published grounding for the design of the benchmark question set (families, k-strata, held-out families, decoys, sample size and clustering, generator gold and its validation, P&ID task relevance)
date: 2026-11-24
status: sources located and checked as stated per entry; seven new papers recommended for full /paper-intake
related: [40-design/qa-system.md §9, 40-design/question-aware-retrieval.md §8-9, ADR-0013, ADR-0029, ADR-0035, ADR-0044, ADR-0053, ADR-0065, ADR-0067, ADR-0069, 40-design/review-fixes.md §5.1-5.3, 40-design/generator-v2-2-handbook-rules.md §19.6, 30-experiments/EXP-0008-v2-rerun.md]
---

# Grounding the question set in the literature

**Legend.** **[repo]** means the source already has a note in `10-literature/`. **[new]** means it was located in this
session. "Read" means I read the full text of the sections cited. "Abstract" means only the abstract or landing page
was checked; such claims are worded as abstract-level. Numbers are quoted exactly as the source gives them.

## 0. What the question set actually is (read from the repo first)

Two points in the brief differ from the code and the ADRs. The thesis must describe what was built.

1. **`k` is not graph distance in hops.** `k = |evidence_edges ∩ cut|` is the number of **sheet-boundary crossings**
   (off-page connector pairs) in the evidence subgraph of the reference answer (`qa-system.md` §9 "Evidence and k";
   `qa/questions/evidence.py`). The bins are **doubling**: {0}, {1}, {2}, {3–4}, {5–8}, {9–16}, {17–32}, {33+}, plus
   an unanswerable bin (`availability.py` `KBin`; ADR-0029, which superseded the original {0, 1, 2, ≥3}). A report may
   collapse them into 0 / 1–2 / ≥3, but the sampler works on the doubling bins. `k` measures how far the evidence is
   spread across **drawings**, not how many relations the answer chains.
2. **"Two wordings per family" means something narrower.** Every family has **one** dev wording
   (`templates.py`; `qa-system.md` §9 says "one phrasing each; paraphrases are a could-item"). Ten dev-old families
   also have **one sealed held-out wording** (`_P1`, `wordings_heldout.py`; ADR-0035 point 1). Since ADR-0053 the
   held-out wordings are excluded from the headline aggregate.

**The set, in numbers taken from the repo:**

| Part | Content | Source |
|---|---|---|
| dev-old families | 12: lookups, neighbours, loop valve and loop equipment, flow path, upstream isolation, cross-unit, count, two decoys (`UNANSWERABLE_TAG`, `NO_PATH`), sheets-of-tag | `qa-system.md` §9 |
| dev-new families | 6: `CONNECTED`, `DOWNSTREAM_IN_UNIT`, `INSTRUMENTS_OF_ITEM`, `UPSTREAM_SOURCES`, `SAME_UNIT`, `LOOPS_NEAR_ITEM` | `question-aware-retrieval.md` §8.2 |
| held-out families | 6, sealed (sha256 `905c7984…`), opened only after the freeze | ADR-0035; `models.py` |
| scope X (EXP-0009) | 5 families: open valves to isolate (up and down), the isolation families without the untagged refusal, valve position | ADR-0067 |
| headline exclusion | `LOOP_ACTUATED_VALVE`: the answer can be read off the loop tag by ISA convention | ADR-0044 U2 |
| draw | `n` per family, seeded shuffle, dealt round-robin over the family's k-bins; yes/no families alternate yes and no | `per_family.py`, `sample.py` |
| EXP-0009 size | 10 per family per plant; scope R = 235 per plant; V2T-A2 answers 275 and V2T-B 285; 5 plants per scale | `generator-v2-2-handbook-rules.md` §19.6; ADR-0065 B4 |
| interval | two-stage cluster bootstrap: plants with replacement, then questions within each drawn plant; equal-weight mean over plants; paired arms share one draw; Q4 (S1000 − S100) unpaired | `review-fixes.md` §5.2 |
| gold | reference functions over the generator's ground-truth `networkx` graph; they never touch the store under test | `qa-system.md` §9; ADR-0013 |
| scorer audit | `claude-sonnet-5.5` judges blind to the scorer's verdict; it sees the reference labelled "the benchmark's reference, which may be wrong" | `review-fixes.md` §5.3; ADR-0069 |

**Validation steps I could not find in the design.** I found no written protocol for an "independent second
derivation" of the gold or for a "human spot check" of the question set. The nearest items are ADR-0061's line-view
check "against the gold's independent `next_path_items`" (P = R = 1) and the main session's script check of every
audit disagreement against the graph (`review-fixes.md` §5.3, "Disagreement handling"). §6 below grounds both steps,
but the thesis may describe them only once they exist.

---

## 1. Template-based question generation over a knowledge graph

**Our choice.** Each family is a fixed English template plus a reference function over the ground-truth graph.
Anchors are sampled with a seed, and the answer is computed, never written by hand.

### Supporting sources

| Source | Status | One-line paraphrase (with location) |
|---|---|---|
| Johnson et al., **"CLEVR: A Diagnostic Dataset for Compositional Language and Elementary Visual Reasoning"**, CVPR 2017, arXiv 1612.06890 | [new], read §1–§4 | Defines a **"question family"** as one program template plus several text templates. 90 families, "an average of four text templates" each. Answers come from executing the program on the scene graph. Rejection sampling within a family gives "an approximately uniform answer distribution" to remove question-conditional bias (§3). Synthetic programs "facilitate in-depth analyses not possible with traditional VQA datasets" (§1, §5). |
| Trivedi, Maheshwari, Dubey, Lehmann, **"LC-QuAD: A Corpus for Complex Question Answering over Knowledge Graphs"**, ISWC 2017, LNCS 10588 pp. 210–218, doi 10.1007/978-3-319-68204-4_22 | [new], repo README and bibliographic record only | 5,000 questions over DBpedia. SPARQL templates are instantiated on 2-hop subgraphs around seed entities. Intermediary template questions are then corrected by hand in a two-step correct-and-review process. |
| Dubey, Banerjee, Abdelkawi, Lehmann, **"LC-QuAD 2.0: A Large Dataset for Complex Question Answering over Wikidata and DBpedia"**, ISWC 2019, doi 10.1007/978-3-030-30796-7_5 | [new], read §1–§4 | 30,000 questions, "10 types … spread over 22 unique templates" (§4.1). Template questions (QT) are verbalised (QV) and then paraphrased (QP) on Mechanical Turk, with a third task verifying both (§3). Paraphrases let models "escape over-fitting to a particular syntax of questions" (§1). |
| Gu, Kase, Vanni, Sadler, Liang, Yan, Su, **"Beyond I.I.D.: Three Levels of Generalization for Question Answering on Knowledge Bases" (GrailQA)**, WWW 2021, arXiv 2011.07743, doi 10.1145/3442381.3449992 | [new], read §1–§3, §5.1–§5.3 | Logical forms are generated from the ontology, a graduate student annotates a canonical question, and the crowd paraphrases it (the Overnight pipeline, §3.1). Gold is executable. 64,331 questions, 4,969 canonical logical forms (§3.2). |
| Zhang, Dai, Kozareva, Smola, Song, **"Variational Reasoning for Question Answering with Knowledge Graph" (MetaQA)**, arXiv 1709.04071 (v5, Nov 2017; the arXiv page lists no venue; it is commonly cited as AAAI 2018, which I did not verify) | [new], read §6.1 | 2-hop and 3-hop questions are generated "by random sampling from a text template pool": 21 types of 2-hop and 15 types of 3-hop questions (§6.1). |
| Talmor and Berant, **"The Web as a Knowledge-base for Answering Complex Questions" (ComplexWebQuestions)**, NAACL 2018, arXiv 1803.06643 | [new], read §4 | Complex SPARQL queries are generated from WebQuestionsSP (4,737 questions) and rendered as machine-generated questions through manually written templates. AMT workers then paraphrase them, giving 34,689 examples (§4.1). |
| **PIDQA**, Gupta, Wei, Czerniawski, Eiris, *MAKE* 7(2):39, 2025, doi 10.3390/make7020039 | [repo] (stub, README-verified) | 64,000 template QA pairs over 500 single P&ID sheets, 4 categories. Gold is "a syntactically correct Cypher query". This is the P&ID precedent for executable template gold. |
| Gadekar, Sakhinana, Runkana, **TopoPID-VQA**, arXiv 2609.05880 (2026) | [repo], read | 3,000 template questions in 28 families over 100 synthetic sheets. "Gold answers never pass through a language model" (A.10). This is the closest P&ID precedent for programmatic topology gold. |

**What these sources support.** They support three advantages, and the thesis can cite each one:

- **Exact gold.** CLEVR §3, GrailQA §3, PIDQA and TopoPID-VQA all execute a program to get the answer.
- **Coverage and control.** In CLEVR §1 and §4 the program says exactly what each question requires, so results can
  be sliced by reasoning type. Our families and the k strata do the same.
- **Bias control.** CLEVR §3 uses rejection sampling for a uniform answer distribution. Our sampler alternates
  `yes` and `no` in `CONNECTED` and `SAME_UNIT` (`sample.py` `_ordered_pool`), which is the same idea in a small form.

### Counter-evidence and limitations to state

- **Naturalness.**
  - CWQ §4.1 says plainly: "the question distribution is artificial from a semantic perspective."
  - GrailQA §3.1 filters every generated logical form with the question "could we reasonably expect a real human user
    to ask this question?" The overall approval rate was 86.5%. In other words, about one form in seven was rejected
    as unnatural. We apply no such filter; our families were written as natural questions under a user rule.
- **Template artefacts.**
  - MetaQA §6.1 criticises WikiMovies because it "is generated from very limited number of text templates, which is
    easy to be exploited by models and of limited practical value".
  - CLEVR §3 warns about "degenerate questions that are seemingly complex but contain simple shortcuts".
  - **We have a concrete instance:** `LOOP_ACTUATED_VALVE` is answerable from the loop tag alone, which is why it is
    excluded from the headline (ADR-0044 U2). The thesis should present this as a template artefact we caught.
- **The paraphrase gap.** Herzig and Berant, **"Don't paraphrase, detect! Rapid and Effective Data Collection for
  Semantic Parsing"**, EMNLP-IJCNLP 2019, arXiv 1908.09940 **[new], abstract**. Data collected by paraphrasing
  generated utterances mismatches the real distribution in both logical forms and language. On two datasets, accuracy
  on the true distribution was 51.3% with paraphrase-based collection, against 70.6% with their method.
  - Our set has **no** crowd or engineer paraphrases.
  - The project's own probe, PARA-R1 (`30-experiments/_results.md`), had 36 D100 dev questions reworded blind, 7 ways
    (3 English, 4 Hungarian), by a fresh LLM agent: `cascade_v3` scored 244/252, against 35/36 on the originals.
  - Its caveats, stated in the row itself: dev plant, an earlier system, and "rewordings were written in-session, not
    collected from users".
- **Low lexical diversity is normal here, not a defect to hide.** TopoPID-VQA has "only 792 unique question strings,
  ~511 after masking" over 3,000 questions [repo note]. Report our distinct-string count the same way.

---

## 2. Difficulty strata

**Our choice.** Questions are stratified by `k`, the number of sheet-boundary crossings in the evidence (doubling
bins, §0), and drawn round-robin over the bins inside each family.

### Supporting sources

| Source | Status | Paraphrase |
|---|---|---|
| MetaQA (above) | [new], read §6.1 | It is the canonical dataset reported in **1-, 2- and 3-hop strata**, in its Vanilla, NTM and Audio versions alike (§6.1, Table 2). |
| GrailQA §5.3.2 | [new], read | "The performance of all models degrades rapidly as questions become more complex" (results by number of relations, 1–4; Fig. 4). Its stratification uses the structure of the logical form. |
| Tang and Yang, **"MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries"**, arXiv 2401.15391 (2024; the arXiv page lists no venue, and a COLM 2024 venue is unverified) | [new], read §3.1–§3.2 | 2,556 queries, stratified by the **number of evidence documents** (Table 4): 2 docs 1,078, 3 docs 779, 4 docs 398, and 0 (null) 301. **This is the closest published analogue of our `k`**: evidence spread over several documents rather than relation hops. |
| Trivedi, Balasubramanian, Khot, Sabharwal, **"MuSiQue: Multihop Questions via Single-hop Question Composition"**, TACL 2022, arXiv 2108.00573 | [new], abstract | 25K questions of 2–4 hops, built so that every hop is needed. A single-hop model loses "about 30 F1" against earlier datasets. |
| Press, Zhang, Min, Schmidt, Smith, Lewis, **"Measuring and Narrowing the Compositionality Gap in Language Models"**, Findings of EMNLP 2023, arXiv 2210.03350 | [new], abstract | For GPT-3, single-hop accuracy improves faster with model size than multi-hop accuracy, so the gap does not close with scale. |

### Counter-evidence and limitations to state

- **Nominal steps are not effective difficulty.**
  - Min, Wallace, Singh, Gardner, Hajishirzi, Zettlemoyer, **"Compositional Questions Do Not Necessitate Multi-hop
    Reasoning"**, ACL 2019, arXiv 1906.02900 **[new], abstract**. A single-hop BERT model reaches 67 F1 on HotpotQA,
    comparable to multi-hop models of the time.
  - CLEVR §4 (read) shows the same effect: accuracy is "unrelated to question size" but decreases with **effective**
    question size, the smallest pruned program that still gives the answer.
- **Our `k` is a property of the drawing set, not of every system.** A system that queries a resolved plant graph
  (Cypher, the graph agent) never sees the connectors. For it, high `k` mostly means a long path, not a cross-document
  join. Only document-bound strategies (ContextRAG, sheet routing) pay for each crossing directly. The thesis should
  say that `k` is the difficulty axis **for the scale claim**, and that per-arm `k` curves show which arms it binds.
- **Family and `k` are confounded.** Long bins are filled mostly by path-type families (`FLOW_PATH` has thousands of
  candidates, as the `sample.py` docstring notes). A `k` curve pooled over families therefore partly compares
  families. Report the `k` curves per family, or at least within path families.

---

## 3. Held-out question families

**Our choice.**
- Six families and ten wordings were written into a sealed file whose sha256 was recorded before development ended.
- The file was opened only after a git-commit freeze that the run script checks.
- The claims and their decision rules were registered beforehand (ADR-0035, ADR-0053).
- Held-out questions are generated only on test plants.

### Supporting sources

| Source | Status | Paraphrase |
|---|---|---|
| GrailQA §2.2 | [new], read | It defines three levels over **schema items**. **I.I.D.:** every schema item of the test question was seen in training, and the question follows the training distribution. **Compositional:** every schema item was seen, but the specific logical form was not. **Zero-shot:** at least one schema item is unseen. Orthogonal to these, it asks for robustness to "language variation, i.e., different paraphrases". The test split is 50% zero-shot, 25% compositional and 25% i.i.d. (§5.1). Ranking EM is 59.9 i.i.d., 45.5 compositional and 48.6 zero-shot (Table 3). |
| Keysers et al., **"Measuring Compositional Generalization: A Comprehensive Method on Realistic Data" (CFQ)**, ICLR 2020, arXiv 1912.09713 | [new], abstract | Splits that maximise compound divergence while keeping atom divergence low. Accuracy correlates strongly and negatively with compound divergence. |
| Nosek, Ebersole, DeHaven, Mellor, **"The preregistration revolution"**, PNAS 115(11):2600–2606, 2018, doi 10.1073/pnas.1708274114 | [new], bibliographic record and abstract | Fix the questions and the analysis plan before seeing outcomes, to separate prediction from postdiction. This grounds PREREG A and ADR-0053. |
| Dwork, Feldman, Hardt, Pitassi, Reingold, Roth, **"The reusable holdout: Preserving validity in adaptive data analysis"**, *Science* 2015 (volume and pages not verified); preprint arXiv 1506.02629 | [new], landing pages | Re-using a holdout adaptively invalidates it unless access is controlled. This grounds sealing and one-shot use. |
| Sainz, Campos, García-Ferrero, Etxaniz, Lopez de Lacalle, Agirre, **"NLP Evaluation in trouble: On the Need to Measure LLM Data Contamination for each Benchmark"**, Findings of EMNLP (the arXiv comment says 2024), arXiv 2310.18018 | [new], abstract | Test data seen in pretraining inflates scores. Their case for measuring contamination per benchmark is what our freshly generated plants avoid by construction. |

**How our design maps onto GrailQA.**
- Our held-out families use only relations the system already knows: flow, signal, control and unit membership.
  They are **novel compositions of seen schema items**, which is GrailQA's **compositional** level, **not** zero-shot.
- Our held-out wordings test GrailQA's orthogonal **linguistic-variation** axis.
- Fresh plant seeds make the **instances** unseen, by both the model's pretraining and the developers. That addresses
  contamination in the Sainz et al. sense.
- The seal and the freeze address the **researcher's adaptive overfitting** (Dwork et al.), a different risk.

### Counter-evidence and limitations to state

- **A held-out gap is not proof of overfitting.** Recht, Roelofs, Schmidt, Shankar, **"Do ImageNet Classifiers
  Generalize to ImageNet?"**, ICML 2019, arXiv 1902.10811 **[new], abstract**.
  - New test sets cost 3%–15% (CIFAR-10) and 11%–14% (ImageNet).
  - The authors attribute the drops to harder examples, "not caused by adaptivity".
  - So EXP-0008's held-out 0.78–0.79 against the headline 0.91 (EXP-0008 "Threats") mixes tuning with intrinsic
    family difficulty. One held-out family also had a gold defect (`VALVES_ON_PATH`, `review-fixes.md` §5.3).
  - The thesis should not read the whole gap as tuning.
- **The authors of the sealed families are not independent.** The architect wrote the need labels, the primitives and
  the sealed families in one session. ADR-0035 records this as a threat. The should-tier remedy was a second held-out
  set written by a fresh researcher from external sources. I found no record that it was done; say so.
- **Zero-shot is not tested.** No held-out family uses an unseen relation type. Do not claim zero-shot generalisation.

---

## 4. Unanswerable and decoy questions

**Our choice.**
- **`UNANSWERABLE_TAG`:** a well-formed tag, built with the generator's own grammar, that is not in the plant, asked
  with a lookup, neighbours or flow-path wording.
- **`NO_PATH`:** two real items, with no flow path between them.
- Both have `k = None`, are reported in their own column, and are scored correct iff `not_present` is true. Answering
  `not_present` to an answerable question counts towards a **false-abstention rate**.

### Supporting sources

| Source | Status | Paraphrase |
|---|---|---|
| Rajpurkar, Jia, Liang, **"Know What You Don't Know: Unanswerable Questions for SQuAD"**, ACL 2018, arXiv 1806.03822 | [new], read §1–§5 | 53,775 unanswerable questions written adversarially. Two desiderata (§2): **relevance** (otherwise word-overlap heuristics separate them) and **existence of a plausible answer** of the asked type (otherwise type matching separates them). Abstaining on a negative scores 1 (§5, fn. 3). |
| Patidar, Faldu, Singh, Vig, Bhattacharya, Mausam, **"Do I have the Knowledge to Answer? Investigating Answerability of Knowledge Base Questions" (GrailQAbility)**, ACL 2023, pp. 10341–10357, doi 10.18653/v1/2023.acl-long.576, arXiv 2212.10189 | [new], read §3–§5 via ar5iv | **The KGQA precedent.** Unanswerable questions are made by deleting KB elements: schema-level (class, relation) or data-level (entity, fact) (§3). About 33% of the test set is unanswerable: 3,358 of 10,166, the NK column (2,162) plus the NA column (1,196) of Table 2 (corrected 2026-11-28, see `2212.10189.md`). Models often say "no answer" **for the wrong reason**: RnG-KBQA+T on missing facts has answer F1 86.0 but logical-form EM 32.5 (Table 4, §5). |
| Kamath, Jia, Liang, **"Selective Question Answering under Domain Shift"**, ACL 2020, arXiv 2006.09462 | [new], abstract | Abstention as risk–coverage: 56% of questions answered at 80% accuracy with a calibrator, against 48% from raw probabilities. |
| Wen et al., **"Know Your Limits: A Survey of Abstention in Large Language Models"**, TACL (the arXiv comment says 2024), arXiv 2407.18418 | [new], abstract | A taxonomy of abstention from the query, model and human-values perspectives. Use it to place our decoys as "query-side, unanswerable from the knowledge source". |
| Kirichenko, Ibrahim, Chaudhuri, Bell, **"AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions"**, arXiv 2506.09038 (2025, no venue listed) | [new], abstract | 20 datasets and 20 frontier LLMs. Abstention is "unsolved"; reasoning fine-tuning degrades it by about 24% on average. This motivates measuring abstention at all. |
| MultiHop-RAG §3.2 | [new], read | 301 of 2,556 queries (11.78%) are **null** queries whose answer is not in the knowledge base. This is a RAG precedent for a decoy share. |
| ChatP&ID note | [repo] | "No abstention/unanswerable category." Our decoys fill a gap the closest prior art leaves open. |

**The mapping to state in the thesis.** `UNANSWERABLE_TAG` is GrailQAbility's **data-level entity deletion**, applied
to a mentioned entity. `NO_PATH` corresponds to **missing facts** on the path. Our scoring follows SQuAD 2.0
(abstaining scores 1) and adds the false-abstention rate.

### Counter-evidence and limitations to state

- **Automatic negatives are easy.**
  - SQuAD 2.0 §5.3: the best score on SQuAD 2.0 was "15.4 F1 points lower" than on automatically generated TF-IDF or
    rule-based negatives, "suggesting that automatically generated negative examples are much easier".
  - Its §3.1 cites Levy et al. (2017): "65% of these negative examples do not have a plausible answer".
  - Our tag decoys satisfy SQuAD's **relevance** desideratum, since they use the plant's grammar and unit numbers.
    But a system with a tag lookup can reject them with one query. They test **whether the system checks**, not
    adversarial plausibility.
  - `NO_PATH` is the harder decoy, because confirming it requires an exhaustive search.
- **The right answer can come from the wrong reason** (GrailQAbility §5). Our `not_present` flag is scored without
  checking that the system looked. If traces allow, report how many correct abstentions followed an actual lookup of
  the tag or a reachability check.
- The decoy share is our choice. GrailQAbility (about 33% of its test set) and MultiHop-RAG (11.78%) show there is no
  standard. State ours and report the decoys apart from the answerable questions.

---

## 5. Sample size, clustering by plant, and the two-stage bootstrap

**Our choice.**
- 10 questions per family per plant, 235–285 questions per plant, and 5 plants per scale.
- Pooled estimate: the equal-weight mean over plants.
- Interval: a two-stage percentile bootstrap, resampling plants and then questions within each plant.
- Paired arms are drawn identically.
- Why five plants (`review-fixes.md` §5.1): three plants give 10 distinct cluster resamples, five give 126.

### Supporting sources

| Source | Status | Paraphrase |
|---|---|---|
| Miller, **"Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations"**, arXiv 2411.00640, 1 Nov 2024; affiliation printed as "Anthropic" | [new], read §2–§5 | **The core citation.** <br>• **§2:** questions are drawn "from a (hypothetical, infinite, unseen) super-population of questions". <br>• **§2.2:** when questions come in groups (several per passage in DROP, QuAC, RACE and SQuAD; one question translated into many languages in MGSM), the independence assumption "of the Central Limit Theorem (or a bootstrap)" is violated. Use clustered standard errors (Eq. 4); the draws of clusters are assumed independent. <br>• **Table 4:** clustered against naive SE was 1.34 vs 0.44 on DROP (×3.05), 0.51% vs 0.46% on RACE-H, and 1.62% vs 0.86% on MGSM. <br>• **§4.2:** paired differences give a "free" variance reduction. <br>• **§5 and Apps. B–C:** a power formula (Eq. 9) and cluster-adjusted sample sizes. Its worked example gives n ≈ 969 to detect 3 points (illustrative parameters). <br>• **§2.1:** the bootstrap is "unnecessary unless a complicated sampling scheme or estimator is being used". Ours is such a scheme (two stages, equal-weight mean over plants). |
| Card, Henderson, Khandelwal, Jia, Mahowald, Jurafsky, **"With Little Power Comes Great Responsibility"**, EMNLP 2020, arXiv 2010.06595 | [new], abstract | "Underpowered experiments are common in the NLP literature". For example, a 2,000-sentence MT test set has about 75% power to detect 1 BLEU. Cite it to justify stating the minimum detectable difference. |
| Bowyer, Aitchison, Ivanova, **"Position: Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints"**, ICML 2025 (position track), arXiv 2503.01747 | [new], abstract | CLT intervals are too narrow on small benchmarks. This supports not using normal-approximation intervals for per-family or per-bin cells of 10–50 questions. The project already uses Wilson intervals per plant (`review-fixes.md` §5.2). |
| Saravanan, Berman, Sober, **"Application of the hierarchical bootstrap to multi-level data in neuroscience"**, *Neurons, Behavior, Data analysis, and Theory* 2020 (PMID 33644783), arXiv 2007.07797 | [new], read §2–§4 | **This is our scheme exactly:** resample subjects with replacement, then neurons within each chosen subject. <br>• §3.1.1: no conservative bias when the data really are hierarchical. <br>• §3.1.2: conservative when the data points are independent, with error bars "roughly 1.4 times" those of other methods (Fig. 3c). <br>• With very few top-level units, "one must therefore be mindful" because lower-level data are weighted too heavily (the power simulations, Fig. 4b and the text that discusses it). |
| Field and Welsh, **"Bootstrapping clustered data"**, *JRSS B* 69(3):369–390, 2007, doi 10.1111/j.1467-9868.2007.00593.x | [new], abstract | Whether a cluster bootstrap is consistent depends on the model. The cluster bootstrap is consistent under both the transformation and random-effect models. |
| Ren et al., **"Nonparametric bootstrapping for hierarchical data"**, *J. Applied Statistics* 37(9):1487–1498, 2010, doi 10.1080/02664760903046102 | [new], abstract only (paywalled) | They recommend resampling the **highest** level with replacement. I could not confirm the abstract's rule for the lower levels. |
| Cameron, Gelbach, Miller, **"Bootstrap-Based Improvements for Inference with Clustered Errors"**, *REStat* 90(3):414–427, 2008, doi 10.1162/rest.90.3.414 | [new], NBER abstract | Cluster-robust inference "presume[s] that the number of clusters is large". With "few (5-30) clusters" standard tests "can over-reject". Their cluster bootstrap-**t** restores nominal size. |
| TopoPID-VQA (2609.05880) | [repo] | The P&ID precedent: a sheet-clustered percentile bootstrap, B = 10,000, with paired Δ intervals (A.5). Each question was run once. |

### Counter-evidence and limitations to state

- **Five clusters are few.**
  - Cameron, Gelbach and Miller name 5–30 clusters as the over-rejection range. Our interval is a percentile
    bootstrap, not the bootstrap-t they validate.
  - The project already states that resampling five plants understates between-plant variance by about 4/5
    (EXP-0008 "Threats"; `review-fixes.md` §5.2). That is the (G − 1)/G plug-in factor at G = 5. I did not locate an
    external page reference for it in this session; Davison and Hinkley (1997) §3.8 is the standard text, not read.
- **The two-stage step pushes the other way.**
  - Resampling questions inside resampled plants adds within-plant variance a second time. Saravanan et al. §3.1.2
    measured this as conservatism (about 1.4× error bars) when there is no real cluster effect.
  - EXP-0007 found the plant SD on dev families to be about 0.010, "below the question noise" (`review-fixes.md`
    §5.1). That is the near-independent case.
  - Tu, Li, Zeng, Shepherd, arXiv 2303.04880 (stat.ME 2023, §3, read) recommend the one-stage cluster bootstrap,
    because within-cluster resampling biased their estimator. They estimate an ICC, not a mean, so the evidence is
    indirect.
  - **Net:** the two biases point in opposite directions, and their size at G = 5 is unknown. **Recommendation:** a
    free simulation on the saved per-question results, comparing coverage of one-stage and two-stage resampling at
    G = 5. Otherwise, state both directions as a limitation.
- **Power.**
  - Miller's 3-point example needs n ≈ 969 under independence. Our 1,175 questions per scale (5 × 235) are
    clustered, so the effective n is lower by the design effect.
  - Per-family cells (5 plants × 10 = 50 per scale) give a 95% half-width of roughly ±0.08 to ±0.14, depending on
    accuracy. This is a Wald figure I computed, not a measured one. Per-family results are descriptive only, which is
    what the registered analysis already says.
- **One run per question.** Miller §3.1: resampling answers K times reduces conditional variance. The project has
  one repeat on test, plus the concurrency-1 control: 45 of 46 verdicts agreed in EXP-0008. State this.

---

## 6. Gold from the generator, and how it is validated

**Our choice.** The gold comes from reference functions over the generator's ground-truth graph. The deterministic
scorer over typed JSON answers is primary. Its verdicts are audited by an independent LLM judge, and disagreements are
checked against the graph by script.

### 6.1 Generator gold

| Source | Status | Paraphrase |
|---|---|---|
| CLEVR §3, PIDQA, TopoPID-VQA A.10 | [new]/[repo] | Executing a program on the ground-truth structure is the accepted way to get exact gold for synthetic graph QA. |
| Northcutt, Athalye, Mueller, **"Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks"**, NeurIPS 2021 Datasets and Benchmarks, arXiv 2103.14749 | [new], abstract | Human-labelled test sets carry errors: at least 3.3% on average across 10 benchmarks, and at least 6% of the ImageNet validation set. Small error rates can flip model rankings. Generator gold avoids annotator noise. |
| GrailQA §3.2 | [new], read | A 100-question manual check of its own human-and-template pipeline found a 3% canonical-question error rate, 2.1% paraphrase error and 5.6% overall. This is the scale and form of a "small human spot check" that a benchmark paper reports. |
| ChatP&ID note | [repo] | Its gold was written by the authors "to the best of our knowledge". Our programmatic gold is the stronger design here. The PIDQA note says the same. |

**Limitation.** Generator gold is exactly as right as the reference function's reading of the question. EXP-0008's
audit found `VALVES_ON_PATH`, a family whose gold definition did not match its wording (`review-fixes.md` §5.3).
Generator gold removes annotator noise but not **specification error**. CWQ §6 is the textual analogue: in its human
analysis, "11.5% did not contain a correct gold answer".

### 6.2 An independent second derivation of the gold

| Source | Status | Paraphrase |
|---|---|---|
| McKeeman, **"Differential Testing for Software"**, *Digital Technical Journal* 10(1):100–107, 1998 | [new], bibliographic record only; full text not found | Comparing independent implementations of one specification exposes bugs in either. This is the standard name for a second derivation of the gold. |
| Knight and Leveson, **"An Experimental Evaluation of the Assumption of Independence in Multiversion Programming"**, *IEEE TSE* 12(1):96–109, 1986 | [new], bibliographic record and secondary summaries; full text not opened | **Counter-evidence.** Programs written independently from one specification did **not** fail independently. A second derivation written from the same family definition can share the definition's error, so it checks the implementation, not the specification. |

To state: a second derivation guards against coding errors in the reference functions. Only the LLM audit, or a human
reading the question text, can catch a gold that answers the wrong question. As noted in §0, I found no design for
this step in the repo.

### 6.3 LLM-as-judge audit of the scorer

| Source | Status | Paraphrase |
|---|---|---|
| Zheng et al., **"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"**, NeurIPS 2023 Datasets and Benchmarks, arXiv 2306.05685 | [new], abstract | Strong judges exceed 80% agreement with human preferences, but show **position, verbosity and self-enhancement** biases. |
| Panickssery, Bowman, Feng, **"LLM Evaluators Recognize and Favor Their Own Generations"**, arXiv 2404.13076 (2024; no venue on the arXiv page) | [new], abstract | Self-recognition correlates linearly with self-preference. Our judge (Claude Sonnet 5.5) is from a different family than the system's model (GPT-6 Luna), which removes this bias by design. |
| Thakur, Choudhary, Ramayapally, Vaidyanathan, Hupkes, **"Judging the Judges: Evaluating Alignment and Vulnerabilities in LLMs-as-Judges"**, GEM² workshop at ACL 2025, pp. 404–430, arXiv 2406.12624 | [new], read §3, §5.4, Conclusion | Judges graded 400 TriviaQA answers with short reference answers, a setting close to our audit. Human–human agreement was Scott's π 96.2 ± 1.07 (§3). Most judges show a **leniency bias**: P+ "significantly higher than 0.5", e.g. GPT-4 0.69 and Llama3-70B 0.90 (§5.4, App. O). Percent agreement "fails to differentiate between judges effectively". Their recommendation: "We recommend computing both percent agreement and Scott's π". They dropped Cohen's κ for "theoretical issues" (App. B). |
| Kamalloo, Dziri, Clarke, Rafiei, **"Evaluating Open-Domain Question Answering in the Era of Large Language Models"**, ACL 2023, arXiv 2305.06984 | [new], abstract | Lexical matching **underestimates** QA accuracy: more than 50% of its failures are semantically equivalent answers. Automated judges are only a rough substitute and miss hallucinations, and human evaluation remains "irreplaceable". This grounds auditing a deterministic scorer at all. |
| Enginuity (2606.03410) | [repo] | Cross-judge design: no model scores its own outputs. |
| CWQ §6 | [new], read | In the human-baseline error analysis, "in 27% the answer was correct but exact string match with the gold answers failed". |

**How this maps to our design.**
- The judge is blind to the scorer's verdict and is told the reference may be wrong. This guards against anchoring,
  which is a design choice of ours, not a cited finding.
- It is a different model family from the system, which addresses self-preference.
- EXP-0008 reported percent agreement (84.3% on 89 right-scored rows, 86.1% on 144 wrong-scored rows) and Cohen's κ
  of 0.889 on the decisive rows. **Following Thakur et al., add Scott's π.**
- **Leniency is the bias that matters most here.** It would inflate "the system is right, the scorer says wrong"
  verdicts. The registered rule already handles this: every disagreement is re-checked against the graph by script
  before any re-score, and fixes go only into the scorer or gold, family-wide (`review-fixes.md` §5.3). State that
  the judge proposes and the graph decides.

### 6.4 A small human spot check

The precedents are GrailQA §3.2 (100 sampled items, error rates reported) and SQuAD 2.0 §4 (100 sampled negatives,
"93% … are indeed unanswerable"). MultiHop-RAG §3.1 reports a manual review "with a high degree of accuracy" but
gives neither the sample size nor the error rate; treat that as a reporting practice to avoid.

**To state:** the sample size, the sampling rule, who checked (the user, new to P&IDs, or a P&ID engineer), and the
error rate with its interval.

---

## 7. Domain-grounded questions for P&IDs

| Our family | Published or practice anchor | Source and status |
|---|---|---|
| `UPSTREAM_ISOLATION`, `DOWNSTREAM_ISOLATION`, `OPEN_VALVES_TO_ISOLATE*` | ChatP&ID App. Table 1 asks to "isolate tank T4750 from all upstream equipment"; its reference lists the valves | [repo] `2603.22528.md`; wording quoted in `qa-system.md` §9 |
| same | Toghraei, *Piping and Instrumentation Diagram Development*, Wiley/AIChE 2019, §1.1: "One main use of P&IDs is for maintenance personnel to initiate lockout–tag out actions." Pp. 132–134 (Table 8.2) rank isolation types from a single block valve to double block and bleed. Pp. 113–114 list normal positions (NO/NC, LO/LC, CSO/CSC); the scope X position family rests on these. | [repo] `pid-structural-rules.md`, `toghraei-2019-vs-generator.md` |
| same | **HSE HSG253, *The safe isolation of plant and equipment*, 2nd ed. 2006.** In the box after para. 142 ("Adequate planning"): "P&IDs should be used to plan isolations." Its example: a heat exchanger replacement where "No reference had been made to P&IDs", a vent line was missed, and hydrogen bromide was released. The glossary defines positive, proved and non-proved isolation. | [new], read in the HSE PDF |
| same | **OSHA 29 CFR 1910.147**, "The control of hazardous energy (lockout/tagout)". §1910.147(b) defines an energy-isolating device as including "a line valve; a block". §(d)(3) requires devices "physically located and operated in such a manner as to isolate the machine or equipment from the energy source(s)." | [new], read on osha.gov |
| `FLOW_PATH`, `CONNECTED`, `NEIGHBOURS_DOWNSTREAM`, `UPSTREAM_SOURCES` | ChatP&ID "Trace the flow path from tank T4750 to pump P4712" (Path Exploration). "Talking like P&IDs" (Alimin, Goldstein, Schulze Balhorn, Schweidtmann, arXiv 2502.18928) asks for process tracing and "list all valves". TopoPID-VQA families include `connected_process`, `reachable_within_k` and `path_avoiding_type`. PIDQA has a "spatial connections" category. | [repo] |
| `LOOP_*`, `INSTRUMENTS_OF_ITEM`, `LOOPS_NEAR_ITEM` | Toghraei pp. 247–249: all elements of one control loop share the tag number, which "helps us to find elements of one control loop when they are on different P&ID sheets". That is the cross-sheet instrument-association task. HSG253's documentation list includes "loop diagrams". | [repo]; [new] |
| `COUNT_IN_UNIT`, `LOOKUP_*` | PIDQA "simple counting"; ChatP&ID "Graph Query (Single/Multi)" | [repo] |

**What is not published.**
- I found no academic P&ID QA benchmark with **isolation-boundary** or **control-loop association** questions across
  sheets.
- ChatP&ID has one isolation question, on one sheet.
- The only multi-tool isolation and instrument-chain work found is the GitHub repo `shaaz1000/pid-graph-agent`. It is
  software, one DEXPI file per question, and not peer-reviewed (`_novelty-log.md`, 2026-10-10).
- My one web search on 2026-11-24 found nothing new beyond the repo's notes.
- **The thesis can claim** that its isolation and loop families take their task basis from practice (HSG253,
  OSHA 1910.147, Toghraei), not from a prior benchmark.

**Limitation.**
- Our isolation gold is a graph walk: the first operated valve on each upstream route, passing through check valves.
- HSG253's practice involves risk-based method selection (positive, proved or non-proved isolation), bleeds, and
  checking the drawing against the as-built plant.
- State that the families model **identifying the isolation points on the drawing**, which is HSG253's planning step,
  and not a full isolation decision.
- The ISA-5.1 standard text was **not read** (`pid-structural-rules.md` L17 says the same); cite the tagging
  convention through Toghraei.

---

## 8. How to describe the question set: an outline for the methods chapter

1. **Purpose and unit of analysis.** Questions are a sample from a super-population of operational P&ID questions
   about one plant (Miller §2). The plant is the sampled cluster.
2. **Families as program plus wording.**
   - Define a family the way CLEVR §3 does: a reference program over the ground-truth graph plus a fixed English
     wording.
   - List the families in a table with answer type, reference definition and task anchor (§7 above).
   - Say which come from practice (isolation, loops) and which from prior P&ID QA (flow path, lookups, counts).
3. **Gold.**
   - It is computed by the generator's reference functions and never touches the store under test (ADR-0013).
   - Contrast it with author-written gold (ChatP&ID) and cite PIDQA and TopoPID-VQA as precedents.
   - State that the remaining risk is specification error, not annotation noise.
4. **Strata.**
   - Define `k` as sheet-boundary crossings in the evidence, with the doubling bins and their purpose: the scale
     claim needs long cross-sheet questions.
   - Relate `k` to hop strata (MetaQA) and evidence-document counts (MultiHop-RAG).
   - State the caveats: effective versus nominal difficulty (Min et al.; CLEVR §4), and the family–`k` confound.
5. **Splits.**
   - Dev and held-out families, held-out wordings, the seal, the freeze and the pre-registration.
   - Map them onto GrailQA's levels: compositional plus linguistic variation, **not** zero-shot.
   - Explain why fresh plant seeds remove instance contamination.
6. **Decoys.**
   - Two kinds, mapped onto GrailQAbility (entity deletion, missing facts). Scored as in SQuAD 2.0, plus a
     false-abstention rate.
   - State that the tag decoys are easy to reject by lookup (SQuAD 2.0 §5.3).
7. **Sampling.**
   - Seeded; n per family; round-robin over k-bins; yes/no balanced (CLEVR §3).
   - The per-anchor cap, the untagged refusal and the availability gate.
   - Report the realised counts per family, bin and plant.
8. **Size and statistics.**
   - 10 per family, 235–285 per plant, 5 plants per scale.
   - Clustered inference (Miller §2.2), the two-stage bootstrap (Saravanan et al.), and paired comparisons (Miller
     §4.2).
   - A minimum detectable difference (Miller §5, Card et al.).
   - Few-cluster caveats (Cameron et al. 2008) and the two opposing biases.
9. **Validation of gold and scoring.**
   - The audit design and its known biases (Zheng; Panickssery; Thakur: leniency, report Scott's π).
   - Disagreement handling against the graph.
   - The second derivation and the human spot check, only if they were done, with size and error rate.
10. **Threats.**
    - Template naturalness and the paraphrase gap (CWQ; Herzig and Berant), with PARA-R1 as partial evidence.
    - Authors of the sealed families not independent.
    - One run per question.
    - Synthetic plants.
    - The decoys' ease.

---

## 9. New papers worth a full `/paper-intake`

| Priority | Paper | Why |
|---|---|---|
| 1 | Miller 2024, arXiv 2411.00640 | The statistical backbone of §5. Its Apps. A and C (clustered SE, cluster-adjusted sample size) should be quoted exactly. |
| 2 | Gu et al. 2021 (GrailQA), arXiv 2011.07743 | The generalisation-level vocabulary for §3, and the Overnight pipeline for §1. |
| 3 | Rajpurkar, Jia, Liang 2018 (SQuAD 2.0), arXiv 1806.03822 | The decoy desiderata and the "automatic negatives are easy" counter-evidence. |
| 4 | Patidar et al. 2023 (GrailQAbility), ACL 2023 | The KGQA abstention taxonomy, and "right for the wrong reason". |
| 5 | Thakur et al. 2024/2025, arXiv 2406.12624 | Leniency bias, and Scott's π against percent agreement for the audit. |
| 6 | Saravanan, Berman, Sober 2020, arXiv 2007.07797 | Our exact bootstrap scheme, with its conservatism result. Pair it with a read of Davison and Hinkley (1997) §3.8. |
| 7 | Johnson et al. 2017 (CLEVR), arXiv 1612.06890 | "Question family" as a term, bias control, and effective question size. |
| should | Tang and Yang 2024 (MultiHop-RAG), arXiv 2401.15391 | The closest analogue of `k` (evidence-document count), plus null queries. |
| should | Herzig and Berant 2019, arXiv 1908.09940 | The main published case against template plus paraphrase data. |
| should | HSE HSG253 (2006) | The practice anchor for the isolation families. Record the paragraph numbers in a note. |

## 10. Not verified in this session (do not cite without checking)

- MetaQA's venue (AAAI 2018) and MultiHop-RAG's venue (COLM 2024): the arXiv pages list none.
- Dwork et al., *Science* volume and pages. Davison and Hinkley (1997) §3.8, not read. Ren et al. (2010)
  lower-level rule. The full texts of McKeeman (1998) and Knight and Leveson (1986).
- The ISA-5.1 text. The ChatP&ID journal version's page numbers (`_novelty-log.md` already flags this).
- The bias factor of the two-stage bootstrap at G = 5: an open quantity, recommended for simulation (§5).

## Addendum, 2026-11-24 (main session): the independent second derivation now exists

The researcher's choice 6 says no written design or tool existed for an independent second derivation. Since then the tool has been built and committed in `3a935dd`, as `qa/exp0009/gold_crosscheck*.py`, test `tests/v2tb/test_gold_crosscheck.py`.

**What it recomputes.** Every scope X gold answer: the four isolation families and POSITION_OF_VALVE.

**How it differs from the stored derivation.** It uses a separate code path:
- the isolation walk is written fresh, with a different algorithm;
- the descriptor resolver is its own;
- the positions are read from DEXPI through the B view, not from the generator plan.

**What it checked.** 14,266 questions on the forced-untagged and forced-tagged 100-sheet dev plants of seeds 1–5:
- 0 disagreements;
- identical candidate and refusal sets.

**Mutation tests.** These show the check can fail:
- a valve removed from a reference is flagged;
- the positions flipped are flagged.

**What it does not show.** Per Knight & Leveson (1986), it checks the code against the definition, not the definition itself.

The human spot check (GrailQA §3.2 style) is still to be done.
