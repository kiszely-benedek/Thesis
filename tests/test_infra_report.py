"""`build_infra_report` and its renderer on hand-made inputs."""

from __future__ import annotations

import pytest

from infra_report_builders import corpus, ingest, memory, run, startup, timing
from plantgraph.infra.report import build_infra_report
from plantgraph.infra.report_compute import compute_row, percentile
from plantgraph.infra.report_inputs import CorpusData, ReportInputs
from plantgraph.infra.report_models import ReferencePrice, SelfCheck
from plantgraph.infra.report_render import render_report


def _inputs(**changes: object) -> ReportInputs:
    parts: dict[str, object] = {
        "corpora": [corpus("D100", 1.0), corpus("D1000", 4.0, data_bytes=40_000_000, nodes=1000)],
        "runs": [
            run("cypher", "D100", [timing(0.1, db=0.08), timing(0.2, db=0.1)]),
            run("cypher", "D1000", [timing(0.4, db=0.3), timing(0.5, db=0.4)]),
        ],
        "price": None,
    }
    parts.update(changes)
    return ReportInputs.model_validate(parts)


def _check(checks: list[SelfCheck], prefix: str) -> SelfCheck:
    return next(c for c in checks if c.name.startswith(prefix))


def test_percentile_interpolates_linearly() -> None:
    assert percentile([0.0, 10.0], 0.9) == pytest.approx(9.0)
    assert percentile([5.0], 0.9) == 5.0


def test_startup_without_regeneration_is_total_minus_the_rebuild_stage() -> None:
    small = build_infra_report(_inputs()).footprints[0].quantities
    # rebuild 1.0 s plus 1 s + 1 s of other stages: 3 s in total, 2 s without the rebuild
    assert small["startup.total"].minimum == pytest.approx(3.0)
    assert small["startup.without_rebuild"].minimum == pytest.approx(2.0)


def test_store_bytes_are_primary_and_the_stale_metric_is_flagged() -> None:
    stale = CorpusData(
        corpus_id="D100",
        ingests=[ingest("D100", 1.0, data_bytes=29_000_000, metric=3_000_000)],
        startups=[startup("D100", 1.0)],
        memory=memory("D100"),
    )
    report = build_infra_report(_inputs(corpora=[stale], runs=[]))
    row = report.footprints[0]
    assert row.quantities["store.data_bytes"].median == 29_000_000
    assert row.quantities["store.metrics_bytes"].median == 3_000_000
    assert "lags" in row.notes[0]
    assert _check(report.checks, "M6").status == "flag"


def _repeats_with(metrics: list[int | None], page_cache: list[int | None]) -> CorpusData:
    """A corpus with one ingest and one startup per list entry (None = quantity missing)."""
    ingests = [ingest("D100", 1.0, metric=m) for m in metrics]
    startups = [
        startup("D100", 1.0).model_copy(update={"page_cache_used_bytes": c}) for c in page_cache
    ]
    return CorpusData(corpus_id="D100", ingests=ingests, startups=startups, memory=memory("D100"))


def test_a_metric_missing_in_some_repeats_is_reported_from_the_others_and_said_so() -> None:
    partial = _repeats_with([None, 4_000_000, None], [None, None, None])
    report = build_infra_report(_inputs(corpora=[partial], runs=[]))
    row = report.footprints[0]
    assert row.quantities["store.metrics_bytes"].n_repeats == 1
    assert any("present in 1 of 3 repeats" in note for note in row.notes)
    m6 = _check(report.checks, "M6")
    assert m6.status == "flag"
    assert "1 of 3" in m6.detail
    assert "present in 1 of 3 repeats only" in render_report(report)


def test_page_cache_in_use_missing_in_some_repeats_does_not_abort() -> None:
    partial = _repeats_with([None, None, None], [500, None, 700])
    row = build_infra_report(_inputs(corpora=[partial], runs=[])).footprints[0]
    cache = row.quantities["neo4j.page_cache_used_bytes"]
    assert (cache.minimum, cache.maximum, cache.n_repeats) == (500, 700, 2)
    assert any("page cache in use is present in 2 of 3" in note for note in row.notes)


def test_a_quantity_absent_everywhere_is_left_out_without_a_note() -> None:
    none_at_all = _repeats_with([None, None, None], [None, None, None])
    row = build_infra_report(_inputs(corpora=[none_at_all], runs=[])).footprints[0]
    assert "store.metrics_bytes" not in row.quantities
    assert row.notes == []


def test_page_cache_needed_is_the_disk_size_times_the_manual_factor() -> None:
    quantities = build_infra_report(_inputs()).footprints[0].quantities
    assert quantities["store.page_cache_needed_bytes"].median == pytest.approx(4_000_000 * 1.2)


def test_a_wide_repeat_spread_is_flagged_not_hidden() -> None:
    base = corpus("D100", 1.0)
    wide = base.model_copy(update={"ingests": [ingest("D100", 1.0), ingest("D100", 2.0)]})
    report = build_infra_report(_inputs(corpora=[wide], runs=[]))
    assert _check(report.checks, "M4").status == "flag"
    assert "ingest.generate" in _check(report.checks, "M4").detail


def test_growth_is_the_larger_corpus_over_the_smaller() -> None:
    by_name = {row.name: row for row in build_infra_report(_inputs()).growth}
    assert by_name["size.nodes"].ratio == pytest.approx(10.0)
    assert by_name["store.data_bytes"].ratio == pytest.approx(10.0)
    assert by_name["cypher.local_median_s"].ratio == pytest.approx(0.45 / 0.15)


def test_compute_row_splits_db_graph_api_and_other() -> None:
    row = compute_row(run("cypher", "D100", [timing(1.0, db=0.5, api=0.25)]))
    assert (row.db_client_sum_s, row.graph_api_sum_s, row.other_sum_s) == (0.5, 0.25, 0.25)
    assert row.needs_database and not row.needs_memory_graph
    assert row.local_share_of_latency == pytest.approx(1.0 / 11.0)
    assert row.token_usd_per_question == pytest.approx(0.01)


def test_parts_exceeding_the_whole_are_counted_as_violations() -> None:
    bad = run("cypher", "D100", [timing(0.1, db=0.2), timing(0.1)])
    check = _check(build_infra_report(_inputs(runs=[bad])).checks, "M3")
    assert check.status == "fail" and "1 rows" in check.detail


def test_a_replay_that_differs_is_left_out_and_fails_the_identity_check() -> None:
    different = run("cypher", "D100", [timing(0.1)], status="different")
    report = build_infra_report(_inputs(runs=[different]))
    assert report.compute == []
    assert _check(report.checks, "M1").status == "fail"


def test_a_coarse_clock_fails_the_clock_check() -> None:
    coarse = run("cypher", "D100", [timing(0.1, clock="monotonic")])
    assert _check(build_infra_report(_inputs(runs=[coarse])).checks, "M2").status == "fail"


def test_count_mismatch_between_database_and_plan_fails() -> None:
    wrong = CorpusData(
        corpus_id="D100",
        ingests=[ingest("D100", 1.0, nodes=100, db_nodes=99)],
        startups=[startup("D100", 1.0)],
        memory=None,
    )
    report = build_infra_report(_inputs(corpora=[wrong], runs=[]))
    assert _check(report.checks, "M5").status == "fail"


def test_paid_calls_fail_the_zero_spend_check() -> None:
    paid = run("cypher", "D100", [timing(0.1)], paid=True)
    assert _check(build_infra_report(_inputs(runs=[paid])).checks, "M7").status == "fail"


def test_old_run_rows_are_shown_with_a_notice_and_no_split() -> None:
    old = run("need", "D100", [timing(0.1, clock="monotonic")], status=None)
    report = build_infra_report(_inputs(runs=[old]))
    assert report.compute[0].other_sum_s is None
    assert _check(report.checks, "Old-run").status == "flag"
    assert _check(report.checks, "M2").status == "pass"  # old rows are not judged by the clock rule


def test_no_price_file_means_no_money_table() -> None:
    report = build_infra_report(_inputs())
    assert report.money == []
    assert "I4" not in render_report(report)


def test_a_price_adds_the_money_table_with_the_marginal_formula() -> None:
    price = ReferencePrice(
        provider="P",
        region="R",
        instance="I",
        vcpu=2,
        ram_gib=4,
        usd_per_hour=3.6,
        url="https://example.org/price",
        accessed="2026-10-10",
    )
    report = build_infra_report(_inputs(price=price))
    assert report.money[0].marginal_usd_per_question == pytest.approx(3.6 * 0.15 / 3600)
    assert "https://example.org/price" in render_report(report)


def test_a_price_without_source_is_refused() -> None:
    with pytest.raises(ValueError, match="price source"):
        ReferencePrice(
            provider="P",
            region="R",
            instance="I",
            vcpu=2,
            ram_gib=4,
            usd_per_hour=1.0,
            url=" ",
            accessed="2026-10-10",
        )


def test_the_markdown_has_all_tables_and_the_checks() -> None:
    text = render_report(build_infra_report(_inputs()))
    for heading in ("## Self-checks", "## I1", "## I2", "## I3"):
        assert heading in text
    assert "M1 replay answers byte-identical" in text
    assert "startup without rebuild" in text
