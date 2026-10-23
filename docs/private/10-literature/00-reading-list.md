# Reading list

One row per source. Notes live beside this file. Add rows with `/paper-intake`.

**The column that matters is Eval scale.** In this field the methods are strong and the evaluations are tiny — that gap is the dissertation.

| ID | Short title | Year | Relevance | Eval scale | Note |
|---|---|---|---|---|---|
| 2411.13929 | Digitizing P&IDs with Transformers (Relationformer) | 2024/25 | baseline | 12 real + synthetic sheets, per-page | [note](2411.13929.md) |
| 2502.18928 | Talking like P&IDs | 2025 | core prior art | **1 flowsheet, 3 questions** | [note](2502.18928.md) |
| 2603.22528 | ChatP&ID — GraphRAG for Engineering Diagrams | 2026 | **closest prior art** | **1 sheet, 19 questions** | [note](2603.22528.md) |
| 2606.03410 | Enginuity — VLM benchmark | 2026 | method (evaluation) | 494 figures / 60 QA | [note](2606.03410.md) |
| zenodo.14803338 | PID2Graph dataset | 2025 | dataset | 500 single pages, no cross-page GT | [note](pid2graph.md) |
| 2502.18493 | Rule-based autocorrection of P&IDs | 2025/26 | baseline (validation) | 1 illustrative P&ID | [note](2502.18493.md) |
| 2607.19568 | P&ID Drawings to Process Graphs (MLLM) | 2026 | competitor | **2 P&IDs** | [note](2607.19568.md) |
| 2505.11976 | Discrete Line Segment Integration | 2025 | method | single drawing | [note](2505.11976.md) |
| 2609.05880 | Grounded and Faithful P&ID Reasoning (TopoPID-VQA, 7-primitive graph-tool VLM agent) | 2026 | method (closest to ADR-0034) | **100 synthetic single sheets, 3,000 template questions, 1 run, no cross-sheet** | [note](2609.05880.md) |
| make7020039 | PIDQA - QA on P&IDs (text-to-Cypher) | 2025 | core prior art | **500 single sheets, 64,000 template QA pairs, no cross-sheet** | [note](make7020039-pidqa.md) |

## Not yet read — queued

- Oeing et al., "Graph Learning in Machine-Readable Plant Topology Data", *Chemie Ingenieur Technik* 2023 — GNNs for plant topology consistency checks
- Mani et al., "Automatic Digitization of Engineering Diagrams", CVPRW 2020
- Paliwal et al., DigitizePID
- Microsoft GraphRAG (community summarization), LightRAG, HippoRAG-2, KET-RAG — the scaling techniques we will actually need
- arXiv 2507.03226 — "Towards Practical GraphRAG: Efficient KG Construction and Hybrid Retrieval at Scale"

## Reading order for someone new to the project

1. `2603.22528` (ChatP&ID) — this is what we are extending and arguing against
2. `2411.13929` — where the graphs come from
3. `pid2graph` — and why that dataset cannot test our claim
4. `2502.18493` — the validation baseline
5. `2606.03410` — how to build evaluation metrics that are not garbage
