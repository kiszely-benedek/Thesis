"""Compare a cache-only replay with the run it replays (the first measurement's identity gate).

A replay differs from its run only in its id and in where each answer came from (the cache), so
those two are neutralised before comparing. A Cypher replay at 1,000 sheets may stop early when a
query near the 30 s limit lands on the other side of it (ADR-0062); such a replay passes as a
*prefix* if every row it did write equals the run's row, which is the rule
`exp0004/e8_identify.sh` applied by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: fields that differ between a run and its replay by construction
_VOLATILE = ("latency_s", "trace")


def _neutral(value: Any) -> Any:
    """The row with every `from_cache` flag set to true."""
    if isinstance(value, dict):
        return {k: (True if k == "from_cache" else _neutral(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_neutral(v) for v in value]
    return value


def _rows(path: Path, run_id: str) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = _neutral(json.loads(line))
            row["run_id"] = run_id
            rows.append(row)
    return rows


def _stable(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _VOLATILE}


def compare(replay_answers: Path, run_answers: Path, allow_prefix: bool) -> str:
    """`identical`, or (only if `allow_prefix`) `prefix_equal: n of m rows`.

    Raises:
        ValueError: the replay's rows differ from the run's, or are fewer without `allow_prefix`.
    """
    replayed, original = _rows(replay_answers, "r"), _rows(run_answers, "r")
    if replayed == original:
        return "identical"
    by_question = {row["question_id"]: _stable(row) for row in original}
    wrong = [r["question_id"] for r in replayed if by_question.get(r["question_id"]) != _stable(r)]
    if wrong:
        raise ValueError(
            f"expected every replayed row to equal the run's, found {len(wrong)} differ: "
            f"{wrong[:3]}"
        )
    if not allow_prefix:
        raise ValueError(
            f"expected {len(original)} identical rows, found {len(replayed)} "
            "(a replay must be complete)"
        )
    return f"prefix_equal: {len(replayed)} of {len(original)} rows"
