"""API-02 on a stored question file: the canonical programs against the question's own reference.

`api_expressiveness` draws its own questions from every family, held-out ones included. This
variant reads an existing question file (for example the dev set of a tuning plant), so a free
guard can be re-run on exactly the questions already in use. No model, no network, no Neo4j.

    uv run python -m plantgraph.qa.harness.api_check_questions --corpus-id D100g2 \
        --ingest-json <corpus>/ingest.json --questions <dir>/questions.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.api_expressiveness import evaluate_programs, render_table
from plantgraph.qa.models import Question
from plantgraph.qa.plant_api.item_graph import build_item_graph


def read_questions(path: Path) -> list[Question]:
    """One `Question` per non-empty line of a JSONL file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Question.model_validate_json(line) for line in lines if line.strip()]


def main(argv: list[str] | None = None) -> None:
    """Print the per-family table; exit 1 when any family's share is below `--min-share`."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.harness.api_check_questions")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--min-share", type=float, default=1.0)
    args = parser.parse_args(argv)

    artifacts = load_corpus_artifacts(args.corpus_id, args.ingest_json)
    view = NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)
    rows = evaluate_programs(read_questions(args.questions), build_item_graph(view))
    print(render_table(rows))
    below = sorted(r.family.value for r in rows.values() if r.share < args.min_share)
    if below:
        raise SystemExit(f"API-02: families below share {args.min_share}: {below}")


if __name__ == "__main__":
    main()
