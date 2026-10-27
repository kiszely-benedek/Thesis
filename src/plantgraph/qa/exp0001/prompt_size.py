"""`python -m plantgraph.qa.exp0001 prompt-size`: ContextRAG's prompt size, with no model call.

ContextRAG pastes the whole serialized plant into one prompt. Whether that fits the model's window,
and where the price steps up, depends only on the number of characters, so it is computed from a
corpus's `ingest.json` alone (the R3 measurement of EXP-0007; no Neo4j, no network).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.serialize import serialize_occurrence_graph

#: Prompt characters the template adds around the serialized graph: the real EXP-0001 prompt chars
#: minus the serialized chars, 2,089 at H1 and 2,085 at H30 (PROMPT-04's 768 predates the primer).
PROMPT_FRAME_CHARS = 2087
#: tokens = SLOPE * prompt chars + INTERCEPT: least squares over the 348 EXP-0001 ContextRAG-high
#: calls (2.54 chars per token).
TOKENS_PER_CHAR = 0.39414
TOKEN_INTERCEPT = -185
#: Luna's price step and prompt window, from the listing read on 2026-10-27.
PRICE_STEP_TOKENS = 272_000
WINDOW_TOKENS = 922_000


class PromptSize(BaseModel):
    """The size of one corpus's ContextRAG prompt."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    sheets: int
    occurrence_nodes: int
    context_chars: int
    prompt_chars: int
    chars_per_sheet: int
    chars_per_node: float
    est_prompt_tokens: int
    above_price_step: bool
    fits_window: bool
    seconds: float


def estimate_tokens(prompt_chars: int) -> int:
    """Prompt tokens estimated from characters with the EXP-0001 fit."""
    return round(TOKENS_PER_CHAR * prompt_chars + TOKEN_INTERCEPT)


def size_from_counts(
    corpus_id: str, sheets: int, nodes: int, context_chars: int, seconds: float = 0.0
) -> PromptSize:
    """Pure part of the measurement: sizes and the two thresholds from counted characters."""
    if sheets < 1 or nodes < 1:
        raise ValueError(f"expected at least one sheet and one node, found {sheets}, {nodes}")
    prompt_chars = context_chars + PROMPT_FRAME_CHARS
    tokens = TOKENS_PER_CHAR * prompt_chars + TOKEN_INTERCEPT
    return PromptSize(
        corpus_id=corpus_id,
        sheets=sheets,
        occurrence_nodes=nodes,
        context_chars=context_chars,
        prompt_chars=prompt_chars,
        chars_per_sheet=round(prompt_chars / sheets),
        chars_per_node=round(context_chars / nodes, 1),
        est_prompt_tokens=round(tokens),
        above_price_step=tokens > PRICE_STEP_TOKENS,
        fits_window=tokens <= WINDOW_TOKENS,
        seconds=round(seconds, 1),
    )


def measure_corpus(corpus_id: str, ingest_json: Path) -> PromptSize:
    """Serialize the corpus exactly as ContextRAG does and size the resulting prompt."""
    started = time.perf_counter()
    artifacts = load_corpus_artifacts(corpus_id, ingest_json)
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    text = serialize_occurrence_graph(view).text
    sheets = artifacts.localized_sheets
    nodes = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    return size_from_counts(corpus_id, len(sheets), nodes, len(text), time.perf_counter() - started)


def parse_corpus_args(items: list[str]) -> list[tuple[str, Path]]:
    """`ID=path/to/ingest.json` items as (id, path) pairs.

    Raises:
        ValueError: an item has no `=` or an empty side.
    """
    pairs = []
    for item in items:
        corpus_id, separator, path = item.partition("=")
        if not separator or not corpus_id or not path:
            raise ValueError(f"expected ID=ingest.json items, found {item!r}")
        pairs.append((corpus_id, Path(path)))
    return pairs


def add_prompt_size_arguments(parser: argparse.ArgumentParser) -> None:
    """The `prompt-size` command's options."""
    parser.add_argument("corpora", nargs="+", metavar="ID=INGEST_JSON")
    parser.add_argument("--json", type=Path, help="also write the rows here, as a JSON list")


def prompt_size_command(args: argparse.Namespace) -> None:
    """Measure every corpus given, print one JSON row each, optionally write the list."""
    rows = [measure_corpus(i, path) for i, path in parse_corpus_args(args.corpora)]
    for row in rows:
        print(row.model_dump_json(), flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = [row.model_dump(mode="json") for row in rows]
        args.json.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
