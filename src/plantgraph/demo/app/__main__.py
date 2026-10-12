"""Start the demo server: `python -m plantgraph.demo.app --config <demo_config.json>`.

Sub-command: `python -m plantgraph.demo.app seed-cache --from A --from B --out C` merges caches.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from plantgraph.demo.app.config import load_demo_config
from plantgraph.demo.app.seed_cache import run_seed_cache
from plantgraph.demo.app.server import HOST, create_app
from plantgraph.demo.app.state import build_app_state


def build_parser() -> argparse.ArgumentParser:
    """The command line: config path, port, the session cap and the replay-only switch."""
    parser = argparse.ArgumentParser(description="Local web demo: ask questions about a plant.")
    parser.add_argument("--config", type=Path, required=True, help="the demo config JSON")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--replay-only",
        action="store_true",
        help="turn paid calls off: only cached answers are shown",
    )
    parser.add_argument(
        "--session-cap-usd",
        type=float,
        help="hard cap on this session's paid calls (USD); default: the config's value",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Build the app state, load the corpora in the background and serve on loopback."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["seed-cache"]:  # the one sub-command; plain `--config ...` still serves
        run_seed_cache(arguments[1:])
        return
    args = build_parser().parse_args(arguments)
    state = build_app_state(
        load_demo_config(args.config),
        allow_paid_calls=not args.replay_only,
        session_cap_usd=args.session_cap_usd,
    )
    state.start_loading()  # corpora load in the background; the PDFs are served meanwhile
    try:
        uvicorn.run(create_app(state), host=HOST, port=args.port)
    finally:
        state.close()


if __name__ == "__main__":
    main()
