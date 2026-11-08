"""The harness with a fake transport, for `run_all.sh --smoke`: the whole chain, zero paid calls.

    python -m plantgraph.qa.exp0008.smoke_harness <the harness's own arguments>

Runs `plantgraph.qa.harness` exactly as the real stages do (frozen run config, resume, spend cap),
but every model call is answered by a canned reply from `llm/fake_transport.py`, so no request ever
leaves the machine. Each reply "costs" `E9_SMOKE_COST_USD` dollars (default 0.0002); the run records
that cost like a real one, so the ledger and the caps can be exercised. A large value forces a
step to hit its cap. The answers are meaningless: only the plumbing is under test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.harness import cli as harness_cli

COST_ENV = "E9_SMOKE_COST_USD"
DEFAULT_COST_USD = 0.0002
#: the name `harness/cli.py` calls to run; looked up by name because it is a module global
HARNESS_HOOK = "run_harness"


@contextmanager
def fake_transport_in_harness(transport: FakeTransport) -> Iterator[None]:
    """Make the harness CLI hand the fake transport to `run_harness` (its documented test hook)."""
    real = getattr(harness_cli, HARNESS_HOOK)

    def run_with_fake(**kwargs: Any) -> Any:
        return real(**kwargs, http_client=transport.as_httpx_client())

    setattr(harness_cli, HARNESS_HOOK, run_with_fake)
    try:
        yield
    finally:
        setattr(harness_cli, HARNESS_HOOK, real)


def main(argv: list[str] | None = None) -> None:
    """Run the harness on `argv` with the fake transport; exits with the harness's own code."""
    cost = float(os.environ.get(COST_ENV, DEFAULT_COST_USD))
    transport = FakeTransport(default_reply=ScriptedReply(text="{}", cost_usd=cost))
    with fake_transport_in_harness(transport):
        harness_cli.main(argv)


if __name__ == "__main__":
    main()
