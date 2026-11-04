"""EXP-0004, the free path: do tag variants break identity resolution, and does a decider fix it?

A variant corpus rewrites some drawn tags (`P-1203A` becomes `P1203A`); a decider judges candidate
pairs of occurrences ("are these two the same item?"); the scorer compares its answers with the
gold identity groups. Nothing here calls a model or a database. Design: `exp0004-v2.md`.

- `corpus`    : build one variant corpus and its candidate pairs (deterministic from a spec)
- `pairs`     : the candidate pairs as plain records, labelled with gold truth, family and operator
- `deciders`  : run D0-D2 over a corpus, group the accepted links, record who said what
- `tuning`    : choose the thresholds of D1 and D2 (dev corpus only)
- `bootstrap` : cluster bootstrap over blocks, paired across deciders
- `scoring`   : pair-level and group-level scores with confidence intervals
- `report`    : the scores as a Markdown report
- `__main__`  : the command line (`build`, `decide`, `tune`, `score`, `links`, `report`)
"""
