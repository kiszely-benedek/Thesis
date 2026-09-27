"""Whether a Neo4j database is actually reachable, without waiting long to find out.

The `neo4j` driver's own default `connection_timeout` is 30 seconds; against a
stopped database that turns "run the test suite" into "wait several minutes",
because every live test that opens its own driver pays that timeout again.
`probe_connectivity` gives every caller — the test suite here, and
`neo4j_loader.py`'s own driver — one short, shared answer instead: reachable
or not, and why, but never the password (see `neo4j_settings.py`).
"""

from __future__ import annotations

from neo4j import GraphDatabase
from pydantic import BaseModel, ConfigDict

from plantgraph.store.neo4j_settings import Neo4jSettings

#: Seconds allowed to establish the TCP connection before giving up. Five
#: seconds is generous for any server that is actually listening, local or
#: remote, while keeping a stopped one from stalling a test run for anywhere
#: near the driver's own 30s default.
DEFAULT_CONNECTION_TIMEOUT_S = 5.0


class Neo4jProbeResult(BaseModel):
    """Outcome of one reachability check; `detail` never contains the password."""

    model_config = ConfigDict(frozen=True)

    reachable: bool
    detail: str


def probe_connectivity(
    settings: Neo4jSettings, connection_timeout_s: float = DEFAULT_CONNECTION_TIMEOUT_S
) -> Neo4jProbeResult:
    """Try to reach `settings.uri` within `connection_timeout_s` seconds.

    Never raises: every failure (connection refused, timed out, wrong
    credentials, wrong database) comes back as `reachable=False` with
    `detail` naming the exception, so a caller can report why without a
    try/except of its own.
    """
    driver = GraphDatabase.driver(
        settings.uri,
        auth=(settings.username, settings.password.get_secret_value()),
        connection_timeout=connection_timeout_s,
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:
        # Broad on purpose: refused, timed out, wrong credentials, wrong
        # database and DNS failures all raise different `neo4j` exception
        # types, and every one of them means the same thing to a caller —
        # "not reachable", with the exception itself as the reason.
        return Neo4jProbeResult(reachable=False, detail=f"{type(exc).__name__}: {exc}")
    finally:
        driver.close()
    return Neo4jProbeResult(reachable=True, detail="connected")
