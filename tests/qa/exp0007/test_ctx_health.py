"""ContextRAG's health rule differs from the tiers': timeouts are results, parsing is tolerated."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from plantgraph.qa.exp0007.cli import main
from plantgraph.qa.exp0007.health import ctx_health_fault, health_fault


def test_parse_failures_stop_a_tier_but_not_contextrag_until_half() -> None:
    counts = Counter({"ANSWERED": 8, "PARSE_FAILURE": 2})  # 20 %

    assert health_fault(counts) is not None
    assert ctx_health_fault(counts) is None
    assert ctx_health_fault(Counter({"ANSWERED": 4, "PARSE_FAILURE": 6})) is not None


def test_provider_errors_stop_contextrag_at_ten_percent_and_timeouts_do_not() -> None:
    assert "PROVIDER_ERROR is 2 of 10" in str(
        ctx_health_fault(Counter({"A": 8, "PROVIDER_ERROR": 2}))
    )
    assert ctx_health_fault(Counter({"ANSWERED": 5, "TIMED_OUT": 3, "DID_NOT_FIT": 2})) is None
    assert ctx_health_fault(Counter()) == "expected at least one row, found none"


def test_the_health_command_takes_the_kind(tmp_path: Path) -> None:
    rows = [{"outcome": "ANSWERED"}] * 8 + [{"outcome": "PARSE_FAILURE"}] * 2
    (tmp_path / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    with pytest.raises(SystemExit) as tier:
        main(["health", "--run-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as ctx:
        main(["health", "--run-dir", str(tmp_path), "--kind", "ctx"])

    assert (tier.value.code, ctx.value.code) == (1, 0)
