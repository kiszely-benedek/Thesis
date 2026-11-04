# Why this replay stopped (ADR-0062)

- 172 of 560 rows replayed, in question order. All 172 equal the run's rows once latency, trace and run id are left
  out (checked 2026-10-31).
- It stopped at `H1000g2:UPSTREAM_SOURCES:P-34403`, at a cache miss for the answer step (`purpose='answer'`).
- In the run, that question's one Cypher query was terminated by the server's transaction timeout
  (`Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration`) after 30.9 s of client time, so the row is
  `RETRIEVAL_ERROR` and no answer step was ever called or cached.
- In the replay the same cached query evidently returned rows inside the limit, so the strategy asked for the answer
  step, which the cache does not hold. This is the mirror of `INF-S7-CYP-H1000g2` (there the query passed the limit
  only in the replay).
- Not re-checked on the database: while this note was written, the database held the corpus of the running agent
  arms, and reloading H1000g2 would have disturbed them. The query text was not read.
- So the stop comes from a query's run time near the limit, not from a change in the system or in the run's answers.
  The run's row (`RETRIEVAL_ERROR`, scored wrong) stands as recorded.
