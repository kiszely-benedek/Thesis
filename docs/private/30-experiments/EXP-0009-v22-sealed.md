---
exp: 0009
date: 2026-11-27
question: On plants built by the handbook-ruled generator v2.2, does the frozen V2T-A2 cascade still hold its accuracy from about 100 to about 1,000 sheets, and does V2T-B (valve positions and untagged-valve descriptors) answer the new isolation and position questions better?
status: done
---

## Setup

- **Pre-registration.**
  - `data/runs/exp0009/prereg/PREREG_A.md`, with amendments 1–3 that re-point the code commit.
  - PREREG_B and the E10 freeze, committed in `36d619f` at F10, before any sealed plant was built.
  - The deviation note `DEVIATION_B_EXPLORATORY.md`, committed in `b3b63a5`.
- **Launcher.** `data/runs/exp0009/run_all.sh` ran stages P0 → P1a → P1b → F10 → B10 → P1c → P1g → P1d → END. It finished on 2026-11-27 at 13:31 UTC with the line "launcher DONE all stages: runs $19.5807 of $26.87 (left $7.2893); audit $3.5122 of $8.13".
- **Plants.** Generator v2.2 (handbook rules, `generator-v2-2-handbook-rules.md`):
  - five at about 100 sheets, `H100g22p1..p5`, with 110 / 90 / 109 / 109 / 100 sheets;
  - five at about 1,000 sheets, `H1000g22p1..p5`, with 921 / 1,086 / 1,025 / 1,072 / 1,011 sheets.
  - Each plant has an A corpus (275 questions) and a B twin (285 questions).
  - None of the 56 build-time rule checks found a violation on any plant (`analysis.md`, rules table).
- **Systems.**
  - V2T-A2 is the frozen `cascade_v4_iso` (freeze E9, `5d31cbb`).
  - V2T-B is A2 plus `operating_position` and untagged-valve descriptors (`v2t-b-system-revision.md`). It was tuned in P1a and frozen at E10.
  - Both use the same pinned GPT-6 Luna as EXP-0008 setting A: a 30 s Cypher limit and a 120 s cutoff per question.
- **Question scopes.**
  - Scope R is EXP-0008's headline families with the X families left out: 900 questions per scale and system.
  - Scope X is the five extension families: OPEN_VALVES_TO_ISOLATE (up and down), UPSTREAM/DOWNSTREAM_ISOLATION_X and POSITION_OF_VALVE. B answers all five; A2 answers only the isolation families.
- **Deviation.** G1-B failed at P1b, with both isolation families below 50 % on every validation plant. The user chose to run B sealed anyway.
  - Every B claim below is **exploratory**, reported next to that failed gate.
  - The A2 claims are confirmatory, as registered.
- **Pause.** The run was paused by hand once, on 2026-11-26 from 17:35 to 20:38 UTC, while the laptop was unplugged. It was killed during a cache-only replay, which was redone on resume. No paid run was cut.
- **Reports.** Under `data/runs/exp0009/reports/`:
  - `analysis.md` (T17);
  - `glm_comparison.md`;
  - per-plant cascade reports;
  - `rescore_*.json`.
- **Audit.** `data/runs/exp0009/audit/{main,b}/report.md` and `audit/classification.md`.

## Result

### A2 claims, confirmatory (scope R, 5 + 5 plants, acc@C, 95 % two-stage cluster bootstrap)

| Claim | Estimate [95 %] | Verdict |
|---|---|---|
| Q4 (primary): S1000 − S100 | +1.4 points [−1.9, +4.7]; acc@C S100 0.899, S1000 0.913 | PASS |
| K1: cascade against always-agent | −3.1 points [−5.3, −0.8]. $/q −0.00035 [−0.00056, −0.00018], so cheaper. Latency +0.52 s [−0.52, +1.61], so not faster. | FAIL |
| K2: cascade against random escalation | +6.7 points [+5.0, +8.5] | PASS |
| K3: latency | median 5.4 s [5.2, 5.6], p90 30.2 s [25.7, 35.8] | PASS |
| Q5: always-agent − always-Cypher | +12.9 points [+9.2, +16.4] | PASS |

EXP-0008's own verdict lines on these runs agree with every row. For K1 they read "the cascade loses accuracy; the cascade saves nothing", and K1 also failed in EXP-0008.

### B, exploratory (reported beside the failed G1-B gate)

| Claim | Scope | Estimate [95 %] | Printed verdict |
|---|---|---|---|
| Q4-B: S1000 − S100 | R and X | −0.8 [−5.1, +3.4]; acc@C S100 0.786, S1000 0.778 | PASS |
| Q4-B without POSITION_OF_VALVE | R and X | −0.5 [−4.6, +4.0] | PASS |
| SB1: B − A2 | R | +0.1 [−1.7, +1.9] (S100 +1.1, S1000 −0.9) | descriptive |
| SB2: B − A2 | X isolation families | +7.5 [+3.0, +12.2] (S100 +8.0, S1000 +7.0) | PASS |

Scope X per family, both scales, acc@C:

| Family | B | A2 |
|---|---|---|
| UPSTREAM_ISOLATION_X | 0.280 | 0.160 |
| OPEN_VALVES_TO_ISOLATE | 0.260 | 0.140 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 0.120 | 0.070 |
| DOWNSTREAM_ISOLATION_X | 0.040 | 0.030 |
| POSITION_OF_VALVE | 0.960 | – |

On POSITION_OF_VALVE the baselines are computed over the same questions (both scales):
- B scores 0.955 on the questions that name the valve by descriptor; always answering the majority code would score 0.807, and the text prior 0.875.
- B scores 1.000 on the questions that name it by tag; the majority code would score 0.417, and the text prior 0.583.

On questions whose gold holds an untagged valve, B scores 0.305 and A2 0.000. A2 cannot name such a valve at all.

### Precision, recall and F1 of list answers (the cascade's final answers, both scales)

| System | List answers | Precision | Recall | F1 |
|---|---|---|---|---|
| V2T-A2 | 1,064 | 0.790 | 0.753 | 0.757 |
| V2T-B | 1,136 | 0.886 | 0.784 | 0.793 |

### Data effect (A2, v2.2 minus v2.1, 18 shared families, unpaired, descriptive)

| Scale | Difference [95 %] |
|---|---|
| S100 | −7.6 points [−10.1, −5.1] |
| S1000 | −5.6 points [−8.7, −2.7] |

The handbook-ruled plants are harder than the v2.1 plants of EXP-0008.

### GLM comparison arm (descriptive, no claim; `glm_comparison.md`)

The arm ran GLM 5.3 Flash on one pinned host against Luna. Both used the frozen V2T-A2 cascade, on the same scope R questions.

| Plant | Questions | Luna | GLM | GLM − Luna [95 % paired] |
|---|---|---|---|---|
| H100g22p1 | 235 | 0.889 | 0.877 | −1.3 [−5.1, +2.6] |
| H1000g22p1 | 235 | 0.923 | 0.872 | −5.1 [−9.4, −1.3] |

- GLM's Cypher tier is faster: a median of 1.6 s, against Luna's 4.3 s.
- Over both tiers it costs slightly more per question: $0.00233 / $0.00240, against Luna's $0.00177 / $0.00231.

### Scorer audit

- **Main sample:** scope R rows of the A2 sealed runs (ADR-0069).
  - The judge agrees on 91.9 % of the 74 right-scored rows and on 89.8 % of the 88 wrong-scored rows.
  - Cohen's kappa is 0.860. In EXP-0008 it was 0.889.
- **B stratum:** 84 wrong-scored rows, of which the judge agrees with 90.5 %.
  - It held no right-scored rows, so its printed kappa of −0.000 is not a measure of agreement.
- **Disagreements.** All 25 were checked against the plant graph (`audit/classification.md`).
  - There were 0 scorer or gold defects, 25 judge errors and 0 ambiguous questions.
  - The post-audit score therefore equals the pre-audit score.
  - The judge's main error source was an excerpt too small to show untagged valves a few parts away: 12 of the 25 rows.

### Gold spot-check (after the run, free, no model calls)

- **Sample.** Two questions per family, one at each scale: 24 families, 48 questions from the sealed B question files, seed 20261127.
- **Scope X gold.** The independent cross-check (`gold_crosscheck`) ran on all ten sealed plants. It checked 500 questions and found 0 disagreements.
- **Scope R gold.** A separate throw-away script recomputed the 38 scope R questions of the sample from the plant graph with its own walks. All 38 agree.
  - It agreed only after three corrections to the script itself, none of them to the gold:
    - path answers list only equipment and valves, so strainers and other parts are passed through;
    - VALVES_ON_PATH counts along item-level shortest routes;
    - a control signal can reach its valve through an off-page signal connector, which carries the loop tag.
- **One format case.** On OPEN_VALVES_TO_ISOLATE for EA-33701 (H1000g22p5B), B named all three gold valves but gave `next_to` H-33701 for the untagged one, where the gold says SB-337002. It is scored wrong. This is the same pattern as the borderline audit row (P-1701).

### Isolation definition analysis (after the run, descriptive, not registered)

**Question.** How much of the weak isolation score comes from the registered definition? The registered walk takes the first operated valve on every route, follows utility and network lines, and passes through other equipment.

**Method.**
- The four isolation families were re-scored on all ten sealed plants: 400 questions per arm.
- Each gold was recomputed on the flow graph under four readings:

  | Reading | What it changes |
  |---|---|
  | D0 | the registered definition, which reproduces the gold on 800 of 800 questions |
  | D1 | only process lines (`P`, `PG`) are walked |
  | D2 | other equipment is a boundary and is not walked through |
  | D3 | D1 and D2 together |

- An edge counts as a process edge if a line it runs on is `P` or `PG`, using the shared line of both ends where there is one. This is an approximation.
- The saved agent-tier answers were re-scored under each reading, using the exact-set rule with the descriptor resolution of the cross-check.

**Agent-tier accuracy, both scales.**

| Family | B: D0 / D1 / D2 / D3 | A2: D0 / D1 / D2 / D3 |
|---|---|---|
| UPSTREAM_ISOLATION_X | 0.28 / 0.11 / 0.28 / 0.13 | 0.16 / 0.10 / 0.15 / 0.12 |
| OPEN_VALVES_TO_ISOLATE | 0.26 / 0.11 / 0.32 / 0.15 | 0.14 / 0.12 / 0.15 / 0.14 |
| DOWNSTREAM_ISOLATION_X | 0.05 / 0.17 / 0.05 / 0.17 | 0.02 / 0.03 / 0.02 / 0.03 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 0.24 / 0.37 / 0.24 / 0.37 | 0.09 / 0.11 / 0.09 / 0.11 |
| All four | 0.207 / 0.190 / 0.223 / 0.205 | 0.102 / 0.090 / 0.102 / 0.100 |

**Findings.**
- **Lenient upper bound.** If an answer counts as right when it matches any of the four readings, B rises from 0.207 to 0.362 and A2 from 0.102 to 0.138. So the definition explains at most about 15 points for B and 4 for A2. B stays wrong under every reading on 64 % of the isolation questions.
- **How much the readings change the gold.** 27 % of the gold valves sit on non-process lines (both scales).
  - Upstream, these are steam (`LPS`), cooling water (`CWS`) and fuel gas (`FG`) valves.
  - Downstream, they are normally closed closed-drain valves (`CHD`, NC) and flare valves (`FL`).
- **The agent itself follows D0 upstream and D1 downstream.**
  - It lists the utility valves upstream: D1 lowers B's upstream score from 0.28 to 0.11.
  - It leaves out the closed drain valves downstream: D1 raises DOWNSTREAM_ISOLATION_X from 0.05 to 0.17.
  - DOWNSTREAM_ISOLATION_X asks for "valves that must be closed", yet its gold includes drains that are already closed. This is a real definitional point.
- **The main failure is incompleteness.** Under D0, B's answered isolation lists have a mean recall of 0.52 (S100) and 0.49 (S1000), against a mean precision of 0.79 and 0.77. The agent finds about half of the valves, and most of what it names is right.
- **Routing loss on the held-out wording.**
  - The downstream templates say "cut … off from all downstream equipment" and never use the word "isolate". The need rule `isolat…downstream` therefore misses them, and the "all downstream" rule sends them to the Cypher tier first.
  - On B this cost 10 OPEN_VALVES_TO_ISOLATE_DOWNSTREAM answers that the agent had right: the cascade scores 0.14 there, the agent alone 0.24, counted without the cutoff. It cost one more answer on DOWNSTREAM_ISOLATION_X.
  - A2 lost none.
  - The downstream families are the held-out ones, so this is a generalisation failure of the frozen router.

**Limits.**
- The analysis is post hoc and changes no registered claim.
- The edge-service rule is approximate.
- It reads agent-tier answers. For the downstream families the cascade's final answer sometimes came from the Cypher tier.

### Spend

- The runs cost $19.58 of the $26.87 runs ledger.
- The audit cost $3.51 of its $8.13 cap.
- The total is $23.09, under the $35 hard cap.

## Reading

- **The scale result replicates on harder plants.** The frozen cascade scores 0.899 at about 100 sheets and 0.913 at about 1,000 sheets. The difference is consistent with zero, as in EXP-0008 (0.914 / 0.908) and EXP-0007 R5.
  - The v2.2 plants cost the system 6–8 points of absolute accuracy against v2.1.
  - They do not make it scale-sensitive.
- **K1 fails again.** On these plants the cascade is about 3 points less accurate than the agent alone, saves about $0.00035 per question, and is not faster.
  - "Always agent" is the better operating point when accuracy is the goal. This matches the consultant's priority recorded on 10-27.
- **Valve positions are easy once they are in the data; isolation is not.**
  - B reads normal positions at 0.96, well above the majority and text-prior baselines.
  - But both systems answer isolation questions poorly. B scores 4–28 % per family, against 3–16 % for A2.
  - B's advantage there (+7.5 points) comes mostly from being able to name untagged valves at all.
  - This is the failed G1-B gate seen on the sealed plants. Isolation, which means walking the plant to the nearest closing valves and listing them in a fixed descriptor format, remains the open problem.
- **The model is not interchangeable at scale.** GLM matches Luna at 100 sheets, but is 5 points behind at 1,000 sheets on the one plant measured.

## Threats

- The plants are generated, not real drawings, and there are only five plants per scale. The bootstrap understates between-plant variance by about 4/5 (`analysis.md` notes).
- Every B result is exploratory. B ran sealed after its gate failed (`DEVIATION_B_EXPLORATORY.md`).
- Some scope X answers are wrong only in format. One audited B row named the right valve with the wrong `next_to` label (`audit/classification.md`, borderline row). The descriptor format is strict by registration.
- The isolation definition walks through heat exchangers and heaters and counts a fuel-gas branch as upstream (R-3701).
  - The post-hoc analysis above bounds its effect at about 15 points for B and 4 for A2.
  - It also shows that DOWNSTREAM_ISOLATION_X counts drains that are already closed.
- The frozen need rules route the held-out downstream wording ("cut … off") to the Cypher tier first. This cost B 11 answers that its agent had right.
- The GLM arm covers one plant per scale (235 questions each). It is descriptive.
- The latency results depend on the machine. The run was on mains power except during the pause.
- Every family scores without held-out split tables. The plants have no `splits.json` (`analysis.md` notes), so there is no held-out scope in this experiment.
