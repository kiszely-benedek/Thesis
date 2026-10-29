"""Run health and the model listing: the two read-only checks every paid stage repeats.

*Health* looks only at how each question ended (outcome counts), never at correctness, so it is safe
to read while a test run is sealed. The *listing* is OpenRouter's public price and window data for
the model; if it changes between freeze and run day, the cost estimate is stale (stop rule 1).
"""

from __future__ import annotations

import json
import urllib.request
from collections import Counter
from pathlib import Path

LISTING_URL = "https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints"
#: The tiers' rule (sealed protocol): provider or parse failures above 10 %, or retrieval errors
#: above 60 %, mean a technical fault, not a result.
BROKEN_SHARE = 0.1
RETRIEVAL_ERROR_SHARE = 0.6


def outcome_counts(run_dir: Path) -> Counter[str]:
    """How many rows of `answers.jsonl` ended in each outcome.

    Raises:
        FileNotFoundError: the run has no `answers.jsonl`.
    """
    path = run_dir / "answers.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"expected {path}, found none")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return Counter(row["outcome"] for row in rows)


def health_fault(counts: Counter[str]) -> str | None:
    """A sentence naming the technical fault, or `None` when the tier run is healthy."""
    total = sum(counts.values())
    if total == 0:
        return "expected at least one row, found none"
    broken = counts.get("PROVIDER_ERROR", 0) + counts.get("PARSE_FAILURE", 0)
    if broken > BROKEN_SHARE * total:
        return f"PROVIDER_ERROR + PARSE_FAILURE is {broken} of {total} rows (limit 10 %)"
    if counts.get("RETRIEVAL_ERROR", 0) > RETRIEVAL_ERROR_SHARE * total:
        return f"RETRIEVAL_ERROR is {counts['RETRIEVAL_ERROR']} of {total} rows (limit 60 %)"
    return None


#: ContextRAG's rule (plan section 8, stop rule 5): provider errors above 10 % stop it, and so do
#: parse failures above 50 %; TIMED_OUT and DID_NOT_FIT are results, not faults.
CTX_PROVIDER_ERROR_SHARE = 0.1
CTX_PARSE_FAILURE_SHARE = 0.5


def ctx_health_fault(counts: Counter[str]) -> str | None:
    """Like `health_fault`, for ContextRAG (one big prompt: parse failures are tolerated more)."""
    total = sum(counts.values())
    if total == 0:
        return "expected at least one row, found none"
    if counts.get("PROVIDER_ERROR", 0) > CTX_PROVIDER_ERROR_SHARE * total:
        return f"PROVIDER_ERROR is {counts['PROVIDER_ERROR']} of {total} rows (limit 10 %)"
    if counts.get("PARSE_FAILURE", 0) > CTX_PARSE_FAILURE_SHARE * total:
        return f"PARSE_FAILURE is {counts['PARSE_FAILURE']} of {total} rows (limit 50 %)"
    return None


def fetch_listing() -> dict[str, object]:
    """Luna's `openai` endpoint, reduced to what price and fit depend on (a free HTTP read).

    Raises:
        ValueError: there is not exactly one endpoint tagged `openai`.
    """
    with urllib.request.urlopen(LISTING_URL, timeout=60) as response:  # noqa: S310 - fixed https URL
        endpoints = json.load(response)["data"]["endpoints"]
    chosen = [e for e in endpoints if e.get("tag") == "openai"]
    if len(chosen) != 1:
        raise ValueError(f"expected exactly one endpoint tagged 'openai', found {len(chosen)}")
    e = chosen[0]
    keys = ("min_prompt_tokens", "prompt", "completion")
    steps = [{k: o[k] for k in keys} for o in e["pricing"]["overrides"]]
    return {
        "tag": e["tag"],
        "context_length": e["context_length"],
        "max_prompt_tokens": e["max_prompt_tokens"],
        "pricing": {
            "prompt": e["pricing"]["prompt"],
            "completion": e["pricing"]["completion"],
            "overrides": steps,
        },
    }


def write_listing(path: Path, listing: dict[str, object]) -> None:
    """Write the listing the way EXP-0001 did (sorted keys, indent 1), so files compare equal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(listing, indent=1, sort_keys=True), encoding="utf-8")
