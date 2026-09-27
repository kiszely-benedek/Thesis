"""`probe_connectivity` — a bounded-time reachability check, no live database needed.

Points the probe at a closed local port (bound then immediately released, so
nothing is listening there) rather than a real Neo4j server: this stands in
for "the database is stopped" without needing Neo4j installed just to run
the test suite. Regression test for the bug where live Neo4j tests hung for
minutes against a stopped database instead of skipping.
"""

from __future__ import annotations

import socket
import time

from pydantic import SecretStr

from plantgraph.store.neo4j_probe import probe_connectivity
from plantgraph.store.neo4j_settings import Neo4jSettings


def _closed_local_port() -> int:
    """A TCP port on localhost guaranteed to refuse connections.

    Binding and immediately closing claims a free port from the OS without
    ever listening on it, so any later connection attempt is refused rather
    than accepted or left hanging.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_probe_reports_not_reachable_quickly_when_nothing_is_listening() -> None:
    settings = Neo4jSettings(
        uri=f"neo4j://127.0.0.1:{_closed_local_port()}",
        username="neo4j",
        password=SecretStr("irrelevant"),
    )

    start = time.perf_counter()
    result = probe_connectivity(settings, connection_timeout_s=3.0)
    elapsed_s = time.perf_counter() - start

    assert result.reachable is False
    assert result.detail, "a failed probe should say why"
    assert "irrelevant" not in result.detail, "the password must never appear in the result"
    # Generous bound: a closed port refuses almost instantly, well under both
    # the 3s connection_timeout_s given here and the driver's 30s default —
    # this is exactly what used to make the live test suite hang.
    assert elapsed_s < 10.0, f"probe took {elapsed_s:.1f}s against a closed port"
