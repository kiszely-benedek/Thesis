| group | query | time s | rows | cut | @20s | @30s | @40s | @60s | @120s | error |
|---|---|---|---|---|---|---|---|---|---|---|
| recorded | D100g2:UPSTREAM_ISOLATION:P-4501C | 120.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:P-3701 | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:V-4801 | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:P-2001A | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:P-1201 | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:CONNECTED:P-3301B|P-3302A | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:EA-4401 | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:P-4101 | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:EA-1701 | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_ISOLATION:E-3902 | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:CONNECTED:F-1401|E-1701 | 0.2 | 0 |  | memory | memory | memory | memory | memory | Neo.TransientError.General.MemoryPoolOutOfMemoryError: The a |
| recorded | D100g2:FLOW_PATH:PSV-42006|P-4301A | 121.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:FLOW_PATH:BFV-27007|T-3301 | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:UPSTREAM_SOURCES:F-1402 | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:NO_PATH:FLOW_PATH:P-4201B|E-3902 | 120.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| recorded | D100g2:NO_PATH:FLOW_PATH:P-1001|EJ-402B | 121.6 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | upstream_distinct:P-4501C | 0.2 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | downstream_distinct:P-4501C | 0.1 | 660 |  | ok | ok | ok | ok | ok |  |
| shape | upstream_qpp:P-4501C | 0.5 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | upstream_bound_path_unwind:P-4501C | 121.2 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | upstream_distinct:P-3701 | 0.3 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | downstream_distinct:P-3701 | 0.2 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | upstream_qpp:P-3701 | 0.1 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | upstream_bound_path_unwind:P-3701 | 121.4 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | upstream_distinct:E-403 | 0.2 | 96 |  | ok | ok | ok | ok | ok |  |
| shape | downstream_distinct:E-403 | 0.1 | 10 |  | ok | ok | ok | ok | ok |  |
| shape | upstream_qpp:E-403 | 0.1 | 96 |  | ok | ok | ok | ok | ok |  |
| shape | upstream_bound_path_unwind:E-403 | 0.2 | 173 |  | ok | ok | ok | ok | ok |  |
| shape | upstream_distinct:F-1402 | 0.1 | 339 |  | ok | ok | ok | ok | ok |  |
| shape | downstream_distinct:F-1402 | 0.1 | 1000 | yes | ok | ok | ok | ok | ok |  |
| shape | upstream_qpp:F-1402 | 0.1 | 339 |  | ok | ok | ok | ok | ok |  |
| shape | upstream_bound_path_unwind:F-1402 | 121.2 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | reach_exists:BFV-27007->T-3301 | 0.3 | 1 |  | ok | ok | ok | ok | ok |  |
| shape | route_shortestpath:BFV-27007->T-3301 | 0.3 | 1 |  | ok | ok | ok | ok | ok |  |
| shape | route_shortest_1:BFV-27007->T-3301 | 18.9 | 1 |  | ok | ok | ok | ok | ok |  |
| shape | route_all_paths_count:BFV-27007->T-3301 | 120.5 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | reach_exists:CHV-12001->XV-54011 | 0.0 | 1 |  | ok | ok | ok | ok | ok |  |
| shape | route_shortestpath:CHV-12001->XV-54011 | 0.0 | 1 |  | ok | ok | ok | ok | ok |  |
| shape | route_shortest_1:CHV-12001->XV-54011 | 124.8 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
| shape | route_all_paths_count:CHV-12001->XV-54011 | 120.0 | 0 |  | timeout | timeout | timeout | timeout | timeout | Neo.ClientError.Transaction.TransactionTimedOutClientConfigu |
