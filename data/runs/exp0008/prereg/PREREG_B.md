# EXP-0008 pre-registration, part B (written by the launcher at M3)

Code commit (HEAD when the freeze was written): `5d31cbb94620645ee018771735edae37f49e7ef8`

## Gate G1 (re-validation of V2T-A2)

Result: **PASS**. VAL100g21: v4_iso 152 vs v3 147 of 163; VAL1000g21: v4_iso 156 vs v3 140 of 163.

## Identity thresholds (EXP-0004 M2, exact scores)

tau1 = 1.0, tau2 = 0.8571428571428571.

## Judge pilot (gate G2) and the audit's size

- Pilot rows judged: 44.
- Known defects judged correct or ambiguous: 23/24; controls judged correct:
  19/20.
- Measured mean cost per call: $0.02577.
- Spent by the pilot: $1.6234 (pilot cap $2.50).
- Sizing cost per call (mean x safety factor): $0.03221.
- Audit capacity under the $10 hard cap: 260 calls, in the registered order
  (every wrong row, then the random right sample of at least 2 per family per scale, then ContextRAG
  wrong rows, then more right samples); the runner stops at the cap.
- Judge prompt sha256: `b56c89d5fba7111f4270d47ef4d8cd53796eee5c499fc3cc5e1ce3d9d2312eaa`; judge pin sha256: `e4794d07b865bf29c276f58309ccf35f205f3a71fabf9257260863cf2a0ea6aa`.

## Step caps (USD, ceilings; each run's own cap comes from its free dry run and the ledger)

| step | cap |
|---|---|
| M1 | 2.00 |
| M2 | 0.05 |
| M5 | 4.90 |
| M6a | 10.00 |
| M6b | 6.27 |
| M6c | 1.44 |
| M8a | 0.80 |
| M8b | 7.28 |
| M9 | 0.25 |

## E9 freeze

`E9.sha256` lists 515 files; its own sha256 is `9dfbaa07366c3aee7b3f6b100cf0a713dc3160e7971fae4a512859a438a7a203`.
`PREREG.sha256` covers part A, part B, the seeds, `E9.commit`, `E9.sha256` and the judge prompt.
