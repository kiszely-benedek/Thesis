"""The LLM client, its cache and run log (design `qa-system.md` §6).

An LLM answers questions about a plant graph in the Q&A experiments; this
package is everything that talks to it. A **model pin** freezes which model,
with which parameters, a run used (ADR-0014), so a reported number can be
reproduced later. Every call goes through a SQLite **cache** keyed by that
pin plus the exact prompt, so a run can be **replayed** — scored again from
the cache — without ever contacting a provider or spending money again.

`models.py` holds the pin, request/response and run-log data (no I/O);
`cache.py` holds the SQLite-backed cache built on top of them.
"""

from __future__ import annotations
