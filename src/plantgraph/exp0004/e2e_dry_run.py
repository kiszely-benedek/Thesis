"""Free dry run of an E2E tier: which questions would need a model call that the cache lacks?

python -m plantgraph.exp0004.e2e_dry_run --misses-out FILE <the harness's own arguments>

The plain harness replay stops at the first cache miss, so it cannot count them. This wrapper runs
the same harness, on a COPY of the sealed cache, with a fake transport (`llm/fake_transport.py`): a
miss is answered with a canned reply instead of a request, so the run goes on and every miss
shows up in `calls.jsonl` as a call that was not served from the cache. Nothing leaves the machine
and the answers are meaningless, so the run directory is scratch. The cache copy is written to
(with the canned replies): never pass the sealed cache.

Unit of the count: a question with at least one miss, which is what the cap formula multiplies.
After a question's first miss the canned reply sends it down a path the real run might not take, so
`n_miss_calls` (all misses) is only indicative.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import CallRecord
from plantgraph.qa.harness import cli as harness_cli

#: A cost of zero keeps the harness's spend guard (which needs *some* cap to run in this mode) idle.
_CANNED_REPLY = ScriptedReply(text="{}", cost_usd=0.0)
_NOMINAL_CAP_USD = (
    1.0  # required by the harness for its non-replay mode; the transport spends nothing
)
_SEALED_DIR_NAME = "sealed"
#: the name `harness/cli.py` calls to run; looked up by name because it is a module global
HARNESS_HOOK = "run_harness"


class DryRunReport(BaseModel):
    """What the dry run found for one tier."""

    run_id: str
    n_questions: int
    n_calls: int
    n_cache_hits: int
    n_miss_calls: int
    n_questions_with_miss: int
    questions_with_miss: list[str]
    misses_by_purpose: dict[str, int]


def summarize_calls(run_id: str, n_questions: int, calls: list[CallRecord]) -> DryRunReport:
    """Count hits and misses; a call with a response that was not `from_cache` is a miss."""
    answered = [c for c in calls if c.response is not None]
    misses = [c for c in answered if c.response is not None and not c.response.from_cache]
    by_purpose: dict[str, int] = {}
    for call in misses:
        by_purpose[call.purpose] = by_purpose.get(call.purpose, 0) + 1
    questions = sorted({c.question_id for c in misses if c.question_id is not None})
    return DryRunReport(
        run_id=run_id,
        n_questions=n_questions,
        n_calls=len(answered),
        n_cache_hits=len(answered) - len(misses),
        n_miss_calls=len(misses),
        n_questions_with_miss=len(questions),
        questions_with_miss=questions,
        misses_by_purpose=by_purpose,
    )


def read_calls(path: Path) -> list[CallRecord]:
    """The run's `calls.jsonl`; empty when the run made no call at all."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [CallRecord.model_validate_json(line) for line in lines if line.strip()]


def refuse_sealed_cache(cache_path: Path) -> None:
    """The dry run writes into its cache: it must be a copy, never a file under a `sealed` folder.

    Raises:
        ValueError: `cache_path` lies in a folder named `sealed`.
    """
    if _SEALED_DIR_NAME in cache_path.resolve().parts:
        raise ValueError(
            f"expected a copy of the cache outside any {_SEALED_DIR_NAME!r} folder, "
            f"found {cache_path}"
        )


@contextmanager
def _fake_transport_in_harness(transport: FakeTransport) -> Iterator[None]:
    """Make the harness CLI pass the fake transport to `run_harness` (its documented test hook)."""
    real_run_harness = getattr(harness_cli, HARNESS_HOOK)

    def run_with_fake(**kwargs: Any) -> Any:
        return real_run_harness(**kwargs, http_client=transport.as_httpx_client())

    setattr(harness_cli, HARNESS_HOOK, run_with_fake)
    try:
        yield
    finally:
        setattr(harness_cli, HARNESS_HOOK, real_run_harness)


def run_dry(argv: list[str], misses_out: Path) -> DryRunReport:
    """Run the harness on `argv` with the fake transport and write the report to `misses_out`."""
    known, _ = _harness_paths_parser().parse_known_args(argv)
    refuse_sealed_cache(known.cache_path)
    run_dir = known.runs_root / known.run_id
    for target in (misses_out, run_dir):
        if target.exists():
            raise FileExistsError(f"expected {target} not to exist (never overwritten), found it")
    transport = FakeTransport(default_reply=_CANNED_REPLY)
    paid_mode = ["--allow-paid-calls", "--max-spend-usd", str(_NOMINAL_CAP_USD)]
    with _fake_transport_in_harness(transport):
        harness_cli.main([*argv, *paid_mode])
    rows_path = run_dir / "answers.jsonl"
    n_rows = len(rows_path.read_text(encoding="utf-8").splitlines()) if rows_path.is_file() else 0
    report = summarize_calls(known.run_id, n_rows, read_calls(run_dir / "calls.jsonl"))
    misses_out.parent.mkdir(parents=True, exist_ok=True)
    with misses_out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report.model_dump(), indent=1) + "\n")
    return report


def _harness_paths_parser() -> argparse.ArgumentParser:
    """The few harness arguments this wrapper reads itself; the rest go to the harness untouched."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--cache-path", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Split off `--misses-out`, run the harness in dry mode, print the counts."""
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004.e2e_dry_run", description=__doc__)
    parser.add_argument("--misses-out", type=Path, required=True)
    args, harness_argv = parser.parse_known_args(argv)
    report = run_dry(harness_argv, args.misses_out)
    print(
        f"{report.run_id}: {report.n_questions_with_miss} of {report.n_questions} questions "
        f"need a model call ({report.n_miss_calls} calls not in the cache, "
        f"{report.n_cache_hits} served from it)"
    )


if __name__ == "__main__":
    main()
