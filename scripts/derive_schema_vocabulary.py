"""Write `graph/schema_vocabulary.py` from the pyDEXPI allowlist and ancestry rule (ADR-0058).

Usage: `uv run python scripts/derive_schema_vocabulary.py` to write the table, or with `--check`
to only compare it with what the rule produces now (exit status 1 on a difference).
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from plantgraph.adapters.pydexpi_vocabulary import derive_vocabulary
from plantgraph.adapters.vocabulary_table_writer import render_vocabulary_module

TABLE_PATH = Path(__file__).resolve().parent.parent / "src/plantgraph/graph/schema_vocabulary.py"


def main() -> int:
    """Write the table, or with `--check` report whether the checked-in one is current."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare only, write nothing")
    text = render_vocabulary_module(derive_vocabulary(), version("pydexpi"))
    if parser.parse_args().check:
        current = TABLE_PATH.read_text(encoding="utf-8")
        is_current = current == text
        print("schema_vocabulary.py is current" if is_current else "schema_vocabulary.py DRIFT")
        return 0 if is_current else 1
    TABLE_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TABLE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
