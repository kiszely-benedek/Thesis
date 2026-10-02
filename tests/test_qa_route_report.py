"""The free routing report (H-T4): aggregation by hand-built rows, measurement on the toy corpus."""

from __future__ import annotations

import ast
import itertools
import json
from pathlib import Path

import pytest

from plantgraph.qa import route_report
from plantgraph.qa.harness.cli import main as harness_cli_main
from plantgraph.qa.models import RunConfig
from plantgraph.qa.route_report import load_view_and_gold, measure_corpus, write_report
from plantgraph.qa.route_report_tables import (
    QuestionMeasure,
    build_report_rows,
    render_csv,
    render_markdown,
)
from qa_harness_toy import CORPUS_ID, Toy, build_toy, pin


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("route-report-toy"))


def _measure(question_id: str, **fields: object) -> QuestionMeasure:
    base: dict[str, object] = {
        "corpus_id": "c",
        "max_context_chars": 1000,
        "route_mode": "sheet_graph",
        "budget_mode": "drop_rings",
        "question_id": question_id,
        "family": "FLOW_PATH",
        "k_bin": "1",
        "u": 0,
        "strict_hit": True,
        "relaxed_hit": True,
        "node_recall": 1.0,
        "retrieval_failed": False,
        "context_chars": 100,
        "over_budget": False,
        "route_fallback": False,
        "retrieval_ms": 2.0,
    }
    return QuestionMeasure.model_validate({**base, **fields})


def test_rows_report_rates_median_and_p90_over_the_rows_that_have_the_value() -> None:
    measures = [
        _measure("a", context_chars=10, strict_hit=True, relaxed_hit=True, node_recall=1.0),
        _measure("b", context_chars=20, strict_hit=False, relaxed_hit=True, node_recall=0.5),
        _measure("c", context_chars=30, strict_hit=None, relaxed_hit=None, node_recall=None),
        _measure(
            "d",
            context_chars=None,
            retrieval_failed=True,
            strict_hit=None,
            over_budget=None,
            node_recall=None,
        ),
    ]
    overall = next(row for row in build_report_rows(measures) if row.dimension == "all")
    assert (overall.n_questions, overall.n_with_evidence) == (4, 2)
    assert overall.strict_hit == 0.5
    assert overall.relaxed_hit == 1.0
    assert overall.node_recall == 0.75
    assert overall.context_chars_median == 20.0
    assert overall.context_chars_p90 == 30.0  # nearest rank of three values
    assert overall.over_budget_rate == 0.0  # the failed row does not report it
    assert overall.retrieval_failure_rate == 0.25


def test_every_dimension_is_reported_and_unanswerable_questions_have_no_u_group() -> None:
    measures = [
        _measure("a", k_bin="3-4", u=2, family="UPSTREAM_ISOLATION"),
        _measure("b", k_bin="unanswerable", u=None, family="NO_PATH"),
    ]
    groups = {(row.dimension, row.group) for row in build_report_rows(measures)}
    assert groups == {
        ("all", "all"),
        ("k_bin", "3-4"),
        ("k_bin", "unanswerable"),
        ("u", "2"),
        ("family", "UPSTREAM_ISOLATION"),
        ("family", "NO_PATH"),
    }


def test_rows_come_in_a_fixed_order_whatever_the_input_order() -> None:
    cells = itertools.product(["5-8", "0", "17-32"], [10, 2], ["flow_path", "sheet_graph"])
    measures = [_measure(f"{k}{u}{r}", k_bin=k, u=u, route_mode=r) for k, u, r in cells]
    rows = build_report_rows(measures)
    assert rows == build_report_rows(list(reversed(measures)))
    one_combination = [row for row in rows if row.route_mode == "sheet_graph"]
    k_groups = [row.group for row in one_combination if row.dimension == "k_bin"]
    u_groups = [row.group for row in one_combination if row.dimension == "u"]
    assert k_groups == ["0", "5-8", "17-32"]  # natural bin order, not alphabetical
    assert u_groups == ["2", "10"]  # numeric, not alphabetical


def test_csv_leaves_a_missing_value_empty_and_markdown_shows_a_dash() -> None:
    rows = build_report_rows([_measure("a", strict_hit=None, relaxed_hit=None, node_recall=None)])
    header, first = render_csv(rows).splitlines()[:2]
    assert header.startswith("corpus_id,max_context_chars,route_mode")
    assert ",,," in first
    assert "| - | - | - |" in render_markdown(rows)


def test_measuring_the_toy_corpus_covers_every_combination_and_budget(toy: Toy) -> None:
    view, gold = load_view_and_gold(CORPUS_ID, toy.corpora_root)
    measures = measure_corpus(
        CORPUS_ID,
        view,
        gold,
        toy.questions,
        max_context_chars_values=[50_000, 400_000],
        sheet_hops=1,
        clock=lambda: 0.0,
    )
    assert len(measures) == 2 * 4 * len(toy.questions)
    assert len({(m.max_context_chars, m.route_mode, m.budget_mode) for m in measures}) == 8
    for measure in measures:
        if measure.strict_hit is not None:
            assert measure.relaxed_hit or not measure.strict_hit  # relaxed only adds hits
            assert measure.node_recall is not None


def test_the_report_files_are_identical_for_identical_inputs(toy: Toy, tmp_path: Path) -> None:
    view, gold = load_view_and_gold(CORPUS_ID, toy.corpora_root)

    def render(out: Path) -> tuple[str, str]:
        measures = measure_corpus(
            CORPUS_ID,
            view,
            gold,
            toy.questions,
            max_context_chars_values=[100_000],
            sheet_hops=1,
            clock=lambda: 0.0,
        )
        csv_path, markdown_path = write_report(measures, out)
        return csv_path.read_text("utf-8"), markdown_path.read_text("utf-8")

    assert render(tmp_path / "one") == render(tmp_path / "two")


def test_the_cli_writes_both_files(toy: Toy, tmp_path: Path) -> None:
    argv = ["--corpus", CORPUS_ID, "--max-context-chars", "100000", "--sheet-hops", "1"]
    argv += ["--corpora-root", str(toy.corpora_root), "--questions-root", str(toy.questions_root)]
    route_report.main([*argv, "--out", str(tmp_path)])
    assert (tmp_path / "route_report.csv").read_text("utf-8").count("\n") > 1
    assert f"## {CORPUS_ID}" in (tmp_path / "route_report.md").read_text("utf-8")


def test_route_report_imports_no_model_client() -> None:
    """No model call by construction: neither module can reach a chat client or sender."""
    imported: set[str] = set()
    for name in ("route_report.py", "route_report_tables.py"):
        tree = ast.parse((Path(route_report.__file__).parent / name).read_text("utf-8"))
        imported |= {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
    forbidden = [m for m in imported if m.startswith("plantgraph.llm") or "harness.runner" in m]
    assert forbidden == []
    assert "plantgraph.qa.unit_router" not in imported


def _harness_argv(toy: Toy, tmp_path: Path, params_path: Path) -> list[str]:
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(pin().model_dump_json(), encoding="utf-8")
    argv = ["--run-id", "params", "--experiment", "TOOLING", "--corpus", f"{CORPUS_ID}:dev"]
    argv += ["--strategy", "hierarchical", "--pin-json", str(pin_path)]
    argv += ["--corpora-root", str(toy.corpora_root), "--questions-root", str(toy.questions_root)]
    argv += ["--runs-root", str(tmp_path / "runs"), "--cache-path", str(tmp_path / "cache.sqlite")]
    return [*argv, "--strategy-params-json", str(params_path)]


def _write_params(path: Path, max_context_chars: int) -> Path:
    params = {
        "route_mode": "flow_path",
        "budget_mode": "drop_rings",
        "sheet_hops": 1,
        "max_context_chars": max_context_chars,
    }
    path.write_text(json.dumps({"hierarchical": params}), encoding="utf-8")
    return path


def test_harness_cli_freezes_strategy_params_and_refuses_changed_ones_on_resume(
    toy: Toy, tmp_path: Path
) -> None:
    first = _write_params(tmp_path / "first.json", 100_000)
    with pytest.raises(SystemExit):  # replay mode: stops at the first cache miss, as it should
        harness_cli_main(_harness_argv(toy, tmp_path, first))
    frozen = (tmp_path / "runs" / "params" / "run_config.json").read_text("utf-8")
    params = RunConfig.model_validate_json(frozen).strategies["hierarchical"]
    assert params["max_context_chars"] == 100_000

    changed = _write_params(tmp_path / "changed.json", 200_000)
    with pytest.raises(ValueError, match="strategies"):
        harness_cli_main(_harness_argv(toy, tmp_path, changed))


def test_harness_cli_rejects_params_for_a_strategy_that_was_not_asked_for(
    toy: Toy, tmp_path: Path
) -> None:
    params_path = tmp_path / "params.json"
    params_path.write_text('{"typo_rag": {}}', encoding="utf-8")
    with pytest.raises(SystemExit, match="typo_rag"):
        harness_cli_main(_harness_argv(toy, tmp_path, params_path))
