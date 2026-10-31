# Why this replay stopped (ADR-0062)

- 231 of 560 rows replayed, in question order. All 231 equal the run's rows once latency and trace are left out.
- It stopped at `H1000g2:FEEDING_UNITS:111`. The first query of that question took 22.6 s in the run, inside the 30 s
  limit. In the replay it passed the limit, so the strategy asked for a repair query, which the run never needed and
  the cache does not hold.
- Checked on the same database on 2026-10-31: the same query timed out at 30 s, then finished in 64.2 s with the same
  502 rows when the limit was raised to 90 s.
- So the stop comes from a query's run time near the limit, not from a change in the system or in the run's answers.
