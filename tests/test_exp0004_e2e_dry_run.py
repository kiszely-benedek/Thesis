"""The E2E dry run: miss counting, the sealed-cache guard, the fake-transport hook and the caps."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from plantgraph.exp0004 import e2e_caps, e2e_dry_run
from plantgraph.exp0004.e2e_dry_run import DryRunReport
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import CallRecord, ChatResponse
from plantgraph.qa.harness import cli as harness_cli


def _call(question_id: str | None, *, from_cache: bool, purpose: str = "answer") -> CallRecord:
    response = ChatResponse(
        text="x", prompt_tokens=1, completion_tokens=1, cost_usd=0.0, latency_s=0.1,
        provider_response_id=None, finish_reason="stop", from_cache=from_cache,
        created_at=datetime.now(UTC),
    )  # fmt: skip
    return CallRecord(
        run_id="r", question_id=question_id, strategy="s", purpose=purpose,
        cache_key="k", pin_hash="p", prompt_sha256="h", response=response,
    )  # fmt: skip


def test_a_question_counts_once_however_many_of_its_calls_miss() -> None:
    calls = [
        _call("q1", from_cache=True), _call("q2", from_cache=False), _call("q2", from_cache=False),
        _call("q3", from_cache=False, purpose="cypher"),
    ]  # fmt: skip

    report = e2e_dry_run.summarize_calls("run", 5, calls)

    assert (report.n_calls, report.n_cache_hits, report.n_miss_calls) == (4, 1, 3)
    assert report.questions_with_miss == ["q2", "q3"] and report.n_questions_with_miss == 2
    assert report.misses_by_purpose == {"answer": 2, "cypher": 1}


def test_a_run_without_calls_has_no_miss(tmp_path: Path) -> None:
    assert e2e_dry_run.read_calls(tmp_path / "missing.jsonl") == []
    assert e2e_dry_run.summarize_calls("run", 3, []).n_questions_with_miss == 0


def test_the_sealed_cache_itself_is_refused() -> None:
    with pytest.raises(ValueError, match="copy of the cache outside"):
        e2e_dry_run.refuse_sealed_cache(Path("data/runs/exp0007/sealed/cache_s7.sqlite"))
    e2e_dry_run.refuse_sealed_cache(Path("data/runs/exp0004/e2e/d0/dry/cache_copy.sqlite"))


def _fake_harness(seen: dict[str, Any], runs_root: Path) -> Any:
    """Stands for `run_harness`: records its arguments and writes the run directory's files."""

    def run_harness(**kwargs: Any) -> Any:
        seen.update(kwargs)
        run_dir = runs_root / "r1"
        run_dir.mkdir(parents=True)
        (run_dir / "answers.jsonl").write_text("{}\n{}\n")
        miss = _call("q9", from_cache=False).model_dump_json()
        (run_dir / "calls.jsonl").write_text(miss + "\n")
        return SimpleNamespace(model_dump_json=lambda **_: "{}", stopped_by_spend_cap=False)

    return run_harness


def test_the_dry_run_hands_the_harness_a_fake_transport_and_reports_the_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        harness_cli, e2e_dry_run.HARNESS_HOOK, _fake_harness(seen, tmp_path / "runs")
    )
    # the harness CLI must get to run_harness: stub the pieces that read real files
    monkeypatch.setattr(harness_cli, "_build_config", lambda *_: object())
    argv = [
        "--run-id", "r1", "--experiment", "E", "--corpus", "H1000g2V:test", "--strategy", "s",
        "--pin-json", "p.json", "--runs-root", str(tmp_path / "runs"),
        "--cache-path", str(tmp_path / "copy.sqlite"),
    ]  # fmt: skip

    report = e2e_dry_run.run_dry(argv, tmp_path / "misses.json")

    assert seen["http_client"] is not None  # no real transport can be built from here
    assert (report.n_questions, report.n_questions_with_miss) == (2, 1)
    saved = DryRunReport.model_validate_json((tmp_path / "misses.json").read_text())
    assert saved == report


def test_the_hook_is_removed_after_the_run(tmp_path: Path) -> None:
    hook = e2e_dry_run.HARNESS_HOOK
    before = getattr(harness_cli, hook)
    with e2e_dry_run._fake_transport_in_harness(FakeTransport()):
        assert getattr(harness_cli, hook) is not before
    assert getattr(harness_cli, hook) is before


def test_an_existing_report_or_run_directory_is_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / "runs" / "r1").mkdir(parents=True)
    argv = ["--run-id", "r1", "--runs-root", str(tmp_path / "runs"), "--cache-path", "c.sqlite"]

    with pytest.raises(FileExistsError, match="never overwritten"):
        e2e_dry_run.run_dry(argv, tmp_path / "misses.json")


# ---- caps (design section 10: misses x R5 cost per question x 1.5) -----------------------------


def _report(n_misses: int) -> DryRunReport:
    return DryRunReport(
        run_id="r", n_questions=560, n_calls=0, n_cache_hits=0, n_miss_calls=n_misses,
        n_questions_with_miss=n_misses, questions_with_miss=[], misses_by_purpose={},
    )  # fmt: skip


def test_the_caps_are_misses_times_r5_cost_times_one_and_a_half() -> None:
    caps = e2e_caps.compute_caps("d0", _report(100), _report(40))

    assert caps.cap_usd == {"cyp": 0.1125, "ag": 0.1134}  # 100*0.00075*1.5, 40*0.00189*1.5
    assert caps.total_cap_usd == 0.2259


def test_the_arm_cap_is_split_in_proportion_and_never_above_the_total() -> None:
    caps = e2e_caps.compute_caps("d0", _report(100), _report(40))

    split = e2e_caps.split_cap(caps, 0.1)
    assert split["cyp"] + split["ag"] == pytest.approx(0.1, abs=1e-5)
    with pytest.raises(ValueError, match="at most 0.2259"):
        e2e_caps.split_cap(caps, 0.23)
    with pytest.raises(ValueError, match="above 0"):
        e2e_caps.split_cap(caps, 0)


def test_no_miss_means_nothing_to_pay() -> None:
    caps = e2e_caps.compute_caps("d0", _report(0), _report(0))

    with pytest.raises(ValueError, match="nothing to pay"):
        e2e_caps.split_cap(caps, 0.01)
