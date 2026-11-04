# E8 identification (2026-11-04), design 40-design/exp0004-v2.md §8, ADR-0063

E8 = `4dfad69` (`../E8.commit`), label V2T-A, 308 hashes in `../E8.sha256` (E7's list re-hashed). Zero paid calls.

| Point | Check | Result |
|---|---|---|
| 2 | no diff since E7 `fdad31f` on a frozen file outside the data-side list | holds: only tag_variants, resolution/identity_*, resolver.py, ingest/, qa/corpus.py, inputs/listing_E7.json |
| 4 | default ingest of H100g2 and H1000g2 equals the sealed ingest.json (timings, environment, store footprint left out) | identical on both (`golden_*.txt`) |
| 3 | cache-only replays of R5 at concurrency 1 | S7-AG-H100g2 identical; S7-AG-H1000g2 identical; S7-CYP-H100g2 identical (`warm_h100/replays/pass1`, 560/560); S7-CYP-H1000g2 stopped at row 536 of 560 on a cache miss, all 536 rows equal R5 (the timing stop §8 allows, ADR-0062) |
| 5 | E8.commit, E8.system, E8.sha256 | written; `sha256sum -c` passes |

Timing note. S7-CYP-H100g2 stopped at row 157 three times (INFRA-2 at `e91abb5`, before any EXP-0004 code; the first
pass here; `warm_h100/replays/pass2`) and ran through once (`pass1`), on the same code and the same loaded database.
The stopping question is `H100g2:CONNECTED:TK-5303|TK-5304`, whose one Cypher query took 24.3 s of local compute in R5
against the 30 s limit: when it passes 30 s the strategy asks for a repair query the cache does not hold. Every
replayed row in every pass equals R5's row (latency, trace and run id left out). S7-CYP-H1000g2 at R5 and in INFRA-2
stopped at row 231, here at row 536: the same effect on other near-limit queries.

The cache copy used for the replays was byte-identical to `exp0007/sealed/cache_s7.sqlite` afterwards and was removed.
Scripts: `../e8_identify.sh`, `../e8_warm_cypher_h100.sh`; logs under `logs/` and `warm_h100/logs/`.
