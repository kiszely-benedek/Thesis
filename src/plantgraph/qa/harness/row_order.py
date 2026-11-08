"""Put `answers.jsonl` and `timings.jsonl` back in the run's canonical row order.

The canonical order is corpus, strategy, question, repeat. A row that was retried after a
provider error is written late, and a resume writes the rows it was missing after the
others, so the files can end up in a different order than a clean run. Sorting them at the
end of an invocation makes the order depend on the inputs, not on what failed on the way.
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

from plantgraph.qa.harness.run_dir import RowKey, RunDir
from plantgraph.qa.models import Question, RunConfig


def canonical_positions(config: RunConfig, questions: list[Question]) -> dict[RowKey, int]:
    """Row key -> its place in a clean run: corpus, then strategy, then question, then repeat."""
    positions: dict[RowKey, int] = {}
    for corpus_id in config.corpora:
        question_ids = [q.question_id for q in questions if q.corpus_id == corpus_id]
        repeats = range(config.repeats)
        for strategy, question_id, repeat in product(config.strategies, question_ids, repeats):
            positions.setdefault((question_id, strategy, repeat), len(positions))
    return positions


def restore_row_order(run_dir: RunDir, config: RunConfig, questions: list[Question]) -> None:
    """Sort both row files into canonical order; lines are moved, never re-serialized."""
    positions = canonical_positions(config, questions)
    _sort_file(run_dir.answers_path, positions)
    _sort_file(run_dir.timings_path, positions)


def _sort_file(path: Path, positions: dict[RowKey, int]) -> None:
    if not path.exists():
        return
    lines = path.read_bytes().splitlines(keepends=True)
    ordered = sorted(lines, key=lambda line: _position_of(line, positions))
    if ordered == lines:
        return
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_bytes(b"".join(ordered))
    temporary.replace(path)


def _position_of(line: bytes, positions: dict[RowKey, int]) -> int:
    row = json.loads(line)
    key = (row["question_id"], row["strategy"], row["repeat"])
    return positions.get(key, len(positions))  # a row of an unknown key sorts last
