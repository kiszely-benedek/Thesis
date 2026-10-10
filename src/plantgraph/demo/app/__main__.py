"""Start the demo server: `python -m plantgraph.demo.app --config <demo_config.json>`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from plantgraph.demo.app.config import load_demo_config
from plantgraph.demo.app.server import HOST, create_app
from plantgraph.demo.app.state import build_app_state


def build_parser() -> argparse.ArgumentParser:
    """The command line: config path, port and the two paid-call options."""
    parser = argparse.ArgumentParser(description="Local web demo: ask questions about a plant.")
    parser.add_argument("--config", type=Path, required=True, help="the demo config JSON")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-paid-calls",
        action="store_true",
        help="let a confirmed question spend money (needs --session-cap-usd)",
    )
    parser.add_argument(
        "--session-cap-usd", type=float, help="hard cap on this session's spending (USD)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Build the app state, load the corpora in the background and serve on loopback."""
    args = build_parser().parse_args(argv)
    if args.allow_paid_calls and args.session_cap_usd is None:
        raise SystemExit("error: --allow-paid-calls needs --session-cap-usd (a hard spend cap)")
    state = build_app_state(
        load_demo_config(args.config),
        allow_paid_calls=args.allow_paid_calls,
        session_cap_usd=args.session_cap_usd,
    )
    state.start_loading()  # corpora load in the background; the PDFs are served meanwhile
    try:
        uvicorn.run(create_app(state), host=HOST, port=args.port)
    finally:
        state.close()


if __name__ == "__main__":
    main()
