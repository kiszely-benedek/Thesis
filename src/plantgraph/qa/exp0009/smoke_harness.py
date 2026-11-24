"""Both arms' harness with a fake transport, for `run_all.sh --smoke`: the whole chain, zero calls.

    python -m plantgraph.qa.exp0009.smoke_harness a2 <the harness's own arguments>
    python -m plantgraph.qa.exp0009.smoke_harness b  <the arguments of `v2tb run`, without `run`>

Both run the real harness (frozen run config, resume, spend cap), but every model call is answered
by a canned reply, so no request leaves the machine. Each reply "costs" `E10_SMOKE_COST_USD`
dollars (default 0.00005) and names a provider, so the record check of §19.11 passes on a smoke
run exactly as on a real one. A large cost makes a step hit its cap. The answers are meaningless:
only the plumbing is under test.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.harness import cli as harness_cli
from plantgraph.qa.v2tb import __main__ as b_cli
from plantgraph.qa.v2tb.runner_b import run_harness_b

COST_ENV = "E10_SMOKE_COST_USD"
DEFAULT_COST_USD = 0.00005
_USAGE = "usage: python -m plantgraph.qa.exp0009.smoke_harness a2|b <arguments>"


def _transport() -> FakeTransport:
    cost = float(os.environ.get(COST_ENV, DEFAULT_COST_USD))
    return FakeTransport(default_reply=ScriptedReply(text="{}", cost_usd=cost, provider="smoke"))


@contextmanager
def _hook(module: Any, name: str, transport: FakeTransport) -> Iterator[None]:
    """Make `module.name(**kwargs)` pass the fake transport as its `http_client`."""
    real = getattr(module, name)

    def with_fake(**kwargs: Any) -> Any:
        return real(**kwargs, http_client=transport.as_httpx_client())

    setattr(module, name, with_fake)
    try:
        yield
    finally:
        setattr(module, name, real)


def main(argv: list[str] | None = None) -> None:
    """Run the arm named by the first argument with the fake transport."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in ("a2", "b"):
        raise SystemExit(_USAGE)
    arm, rest = arguments[0], arguments[1:]
    transport = _transport()
    if arm == "a2":
        with _hook(harness_cli, "run_harness", transport):
            harness_cli.main(rest)
        return
    with _hook(b_cli, run_harness_b.__name__, transport):
        b_cli.main(["run", *rest])


if __name__ == "__main__":
    main()
