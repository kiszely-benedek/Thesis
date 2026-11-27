# GLM comparison arm (descriptive, no claim)

GLM 5.3 Flash on one pinned host against GPT-6 Luna, both under the frozen V2T-A2 system and the policy `cascade_v4_iso`, on the same scope R questions of one sealed plant per scale. Differences are in percentage points, with a 95 % paired bootstrap interval.

| plant | questions | Luna correct | GLM correct | GLM - Luna (points) | 95 % interval |
|---|---|---|---|---|---|
| H100g22p1 | 235 | 209 (0.889) | 206 (0.877) | -1.3 | [-5.1, +2.6] |
| H1000g22p1 | 235 | 217 (0.923) | 205 (0.872) | -5.1 | [-9.4, -1.3] |

| plant | system | tier | $ per question | median latency s | p90 latency s | outcomes |
|---|---|---|---|---|---|---|
| H100g22p1 | Luna | cyp | $0.00061 | 4.3 | 8.6 | ANSWERED 231, PARSE_FAILURE 2, RETRIEVAL_ERROR 2 |
| H100g22p1 | Luna | ag | $0.00116 | 6.4 | 16.7 | ANSWERED 235 |
| H100g22p1 | GLM | cyp | $0.00025 | 1.6 | 2.3 | ANSWERED 233, RETRIEVAL_ERROR 2 |
| H100g22p1 | GLM | ag | $0.00208 | 3.7 | 14.6 | ANSWERED 234, PARSE_FAILURE 1 |
| H1000g22p1 | Luna | cyp | $0.00063 | 4.3 | 8.4 | ANSWERED 228, RETRIEVAL_ERROR 7 |
| H1000g22p1 | Luna | ag | $0.00168 | 7.8 | 22.5 | ANSWERED 235 |
| H1000g22p1 | GLM | cyp | $0.00037 | 1.6 | 3.2 | ANSWERED 235 |
| H1000g22p1 | GLM | ag | $0.00203 | 3.8 | 14.1 | ANSWERED 235 |

| plant | system | $ per question, both tiers |
|---|---|---|
| H100g22p1 | Luna | $0.00177 |
| H100g22p1 | GLM | $0.00233 |
| H1000g22p1 | Luna | $0.00231 |
| H1000g22p1 | GLM | $0.00240 |
