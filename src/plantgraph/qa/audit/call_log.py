"""What the judge's own `calls.jsonl` says about attempts that were billed but discarded.

A judge call that gets an error reply is retried by the client. Each discarded attempt that
reported a cost is a line in `calls.jsonl` (`error_kind` provider_error, response present), but
only the final reply reaches the audit ledger, so those attempts must be read from the log.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.llm.models import CallRecord


def log_size(path: Path) -> int:
    """Bytes in the log now (0 if it does not exist yet): the mark to read "what came after"."""
    return path.stat().st_size if path.exists() else 0


def discarded_attempts_usd(path: Path, since: int) -> float:
    """Money billed by error attempts the client discarded after byte `since` of the log."""
    if not path.exists():
        return 0.0
    with path.open("rb") as handle:
        handle.seek(since)
        text = handle.read().decode("utf-8")
    total = 0.0
    for line in text.splitlines():
        if not line.strip():
            continue
        record = CallRecord.model_validate_json(line)
        if record.error_kind != "provider_error" or record.response is None:
            continue
        if not record.response.from_cache and record.response.cost_usd:
            total += record.response.cost_usd
    return total
