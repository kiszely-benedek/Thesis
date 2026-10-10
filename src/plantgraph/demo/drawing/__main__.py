"""CLI: `python -m plantgraph.demo.drawing --corpus D100 --corpora-root ... --out ...`.

Rebuilds the corpus from its `ingest.json`, draws every sheet and prints the self-check.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from plantgraph.demo.drawing.export import PDF_NAME, export_drawings
from plantgraph.qa.corpus import load_corpus_artifacts

_DEFAULT_CORPORA_ROOT = Path("data/runs/cv1/corpora")
_DEFAULT_OUT = Path("data/runs/cv1/drawings")


def main(argv: list[str] | None = None) -> None:
    """Export one corpus and print the report."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.demo.drawing", description=__doc__)
    parser.add_argument("--corpus", required=True, help="corpus id, e.g. D100")
    parser.add_argument("--corpora-root", type=Path, default=_DEFAULT_CORPORA_ROOT)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    artifacts = load_corpus_artifacts(args.corpus, args.corpora_root / args.corpus / "ingest.json")
    load_s = time.perf_counter() - started
    index = export_drawings(args.corpus, artifacts.localized_sheets, artifacts.resolution, args.out)

    pdf_path = args.out / args.corpus / PDF_NAME
    print(f"corpus rebuild {load_s:.1f} s; total {time.perf_counter() - started:.1f} s")
    print(f"{pdf_path} ({pdf_path.stat().st_size / 1e6:.2f} MB)")
    print(index.report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
