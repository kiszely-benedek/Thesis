---
adr: 0050
title: Switch the answering model from GLM-5.3-flash to GPT-6 Luna (low effort, host pinned) for the agent tier, and for the Cypher tier if it is not worse there; re-run the dev sweeps under the new model
status: accepted (user, 2026-10-11) — conditional on the Cypher-tier check, see "Cypher-tier check"
date: 2026-10-11
supersedes: in part — the model named in ADR-0048 (cascade v2 tiers); ADR-0014 (one model per sweep) holds and is why the dev sweeps are re-run
evidence: 30-experiments/_results.md rows BAKEOFF-1, BAKEOFF-2, MODEL-SWITCH; Technology_research/2026-10-10-faster-openrouter-models.md
---

# ADR-0050 — Model switch to GPT-6 Luna

## Context

The cascade's tail latency on GLM-5.3-flash was the problem the user raised on 2026-10-10 ("Nagyon nem jó hír,
hogy ennyire lassú… más modellek próbáljunk ki"). A two-stage bake-off (user-approved) compared seven pinned
model/host configurations on the agent tier (`graph_agent_low_steps`, max_steps 40, deadline 120 s):

- Stage 1 (18 D100 dev questions, one per family): C (GLM @ Fireworks, high) and F (GPT-6 Luna @ OpenAI, low)
  advanced; G (gpt-oss-120b @ Cerebras) was fastest but 12/18; unpinned GLM was served by 15 different hosts.
- Stage 2 (the other 72 questions, combined to 90):

| Config | Correct /90 | Median | p90 | Max | TIMED_OUT / PARSE_FAILURE | $/question |
|---|---|---|---|---|---|---|
| F GPT-6 Luna, low | 86 | 8.3 s | 19.8 s | 44.8 s | 0 / 0 | 0.00054 |
| A GLM, unpinned (current) | 85 | 8.3 s | 41.0 s | 120 s | 2 / 1 | 0.00101 |
| C GLM @ Fireworks, high | 83 | 7.8 s | 29.4 s | 42.3 s | 0 / 0 | 0.00182 |

On Artificial Analysis' general index Luna is *below* GLM (38 vs 42 at max effort; 22 at low), yet it wins on
this tool-calling task — the general index does not predict task accuracy here (findings log L18).

## Decision

1. GPT-6 Luna (`openai/gpt-6-luna`, host `openai` pinned, `allow_fallbacks: false`, `require_parameters: true`,
   reasoning effort low, seed 0, temperature not sent — the host takes none) answers the agent tier.
2. The Cypher tier switches to the same pin **if** Luna is not worse there on the dev corpora (Cypher-tier check
   below); otherwise the Cypher tier stays on GLM low and the policy mixes models per tier (each tier's pin is
   already recorded per tier in the policy, so the ADR-0014 rule "one model per sweep" holds per tier run).
3. All dev sweeps that feed the cascade report are re-run under the new pin(s); the old GLM runs stay as the
   comparison arm and are not deleted.
4. The live demo switches with the policy (its tier runs and pins come from the demo config).

## Alternatives

- **Keep GLM, pin the host (C).** Tail improves (p90 29.4 s) but accuracy drops (83/90) and cost triples.
- **Keep GLM unpinned (A).** One more correct than C, but p90 41 s, two timeouts and 15 hosts — latency is not
  reproducible.
- **gpt-oss-120b @ Cerebras (G).** p90 10 s but 12/18 in stage 1 — fails the accuracy gate.

## Consequences

- **Determinism.** Luna's host accepts no `temperature`; answers come from the provider's default sampling.
  Run-to-run variance is larger than under GLM at temperature 0 and must be stated in the thesis.
- **Price/availability risk.** Luna was three days old at the switch; its price or behaviour may change. The pin
  and the provider actually serving each call are recorded (`ChatResponse.provider`).
- **Cost of the switch.** Re-running the four dev sweeps (Cypher + agent × D100 + D1000) plus the paraphrase
  robustness run; estimated from the bake-off rates at well under $1.

## Cypher-tier check

Filled in from runs `CYP2-{D100,D1000}-low` (GLM, round-2 prompt) and `CYPL-{D100,D1000}` (Luna, same prompt),
joined with the agent tier `AGL3-{D100,D1000}` (Luna, final answer at high effort) in the cascade report
(cutoff 120 s), 2026-10-11:

| | D100 | D1000 |
|---|---|---|
| Cypher tier alone, GLM low | 137/180, 13 RETRIEVAL_ERROR | 138/180, 12 RETRIEVAL_ERROR, 1 TIMED_OUT |
| Cypher tier alone, Luna | 132/180, 31 RETRIEVAL_ERROR | 129/180, 38 RETRIEVAL_ERROR |
| tier-1 accept precision, GLM / Luna | 0.945 / 0.976 | 0.926 / 0.975 |
| `cascade_v3_mixed` (GLM Cypher + Luna agent) | 173, $0.00029/q, p90 20.0 s | 169 acc@120, $0.00036/q, p90 18.2 s |
| `cascade_v3` (Luna both tiers) | **176**, $0.00055/q, p90 17.0 s | **175**, $0.00058/q, p90 17.4 s |

Alone, Luna's Cypher tier is worse (more generated queries fail in Neo4j). In the cascade it is better: a failed
query is a loud failure that escalates to the agent, whereas GLM's misses are more often quiet wrong answers that
the accept rule takes. The condition "not worse there" is read on the cascade, where the tier is used, so the
Cypher tier switches too, at about twice the mixed policy's cost per question. The agent tier's pin is the
final-high variant (steps stay low); the `cascade_v3*` / `always_g_luna` policy files pin it.
