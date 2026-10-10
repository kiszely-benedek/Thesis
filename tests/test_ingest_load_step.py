"""`load_step.load_if_requested` and the new ingest flags, with every Neo4j call faked."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from plantgraph.ingest import __main__ as ingest_cli
from plantgraph.ingest import load_step
from plantgraph.ingest.load_step import NO_MEASUREMENT, StoreMeasurement, load_if_requested
from plantgraph.store.neo4j_loader import LoadReport
from plantgraph.store.neo4j_settings import Neo4jSettings

_NO_PLAN: Any = None  # the faked load never reads the plan


def _report() -> LoadReport:
    return LoadReport(
        corpus_id="c",
        nodes_written=1,
        relationships_written=0,
        batch_size=1,
        wipe_s=1.0,
        schema_s=2.0,
        nodes_s=3.0,
        relationships_s=4.0,
        verify_s=5.0,
        total_s=15.0,
        neo4j_version="Neo4j Kernel 2026.09.0 (enterprise)",
    )


def _settings() -> Neo4jSettings:
    return Neo4jSettings(uri="bolt://x", username="u", password=SecretStr("p"))


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace every Neo4j-touching step of `load_step` with a recorder."""
    log: list[str] = []

    def fake_recreate(settings: Neo4jSettings) -> None:
        log.append("recreate")

    def fake_load(settings: Neo4jSettings, plan: Any) -> LoadReport:
        log.append("load")
        return _report()

    def fake_measure(settings: Neo4jSettings, home: Path, *, fresh_database: bool) -> str:
        log.append(f"measure fresh={fresh_database}")
        return "footprint"

    monkeypatch.setattr(load_step, "recreate_database", fake_recreate)
    monkeypatch.setattr(load_step, "load_corpus", fake_load)
    monkeypatch.setattr(load_step, "measure_store", fake_measure)
    monkeypatch.setattr(load_step, "read_memory_settings", lambda settings: {"k": "v"})
    monkeypatch.setattr(load_step, "collect_run_environment", lambda *a, **k: "environment")
    return log


def test_plain_load_records_neither_environment_nor_footprint(calls: list[str]) -> None:
    stages: dict[str, float] = {}
    outcome = load_if_requested(_settings(), _NO_PLAN, stages, NO_MEASUREMENT)
    assert calls == ["load"]
    assert outcome.environment is None and outcome.footprint is None
    assert stages["load_total"] == 15.0


def test_fresh_database_recreates_before_loading_and_times_it(calls: list[str]) -> None:
    stages: dict[str, float] = {}
    outcome = load_if_requested(
        _settings(), _NO_PLAN, stages, StoreMeasurement(fresh_database=True)
    )
    assert calls == ["recreate", "load"]
    assert "load_recreate" in stages
    assert str(outcome.environment) == "environment"
    assert outcome.footprint is None  # no --neo4j-home, so no disk measurement


def test_neo4j_home_measures_after_the_load(calls: list[str], tmp_path: Path) -> None:
    measurement = StoreMeasurement(fresh_database=True, neo4j_home=tmp_path)
    outcome = load_if_requested(_settings(), _NO_PLAN, {}, measurement)
    assert calls == ["recreate", "load", "measure fresh=True"]
    assert str(outcome.footprint) == "footprint"


def test_a_measurement_without_settings_is_an_error(calls: list[str]) -> None:
    with pytest.raises(ValueError, match="expected Neo4j settings"):
        load_if_requested(None, _NO_PLAN, {}, StoreMeasurement(fresh_database=True))
    assert calls == []


def test_no_settings_and_no_measurement_is_a_quiet_skip(calls: list[str]) -> None:
    outcome = load_if_requested(None, _NO_PLAN, {}, NO_MEASUREMENT)
    assert outcome.report is None and calls == []


def test_flags_parse_and_default_off() -> None:
    args = ingest_cli._parse_args(["synthetic", "--n-units", "1"])
    assert args.fresh_database is False and args.neo4j_home is None
    args = ingest_cli._parse_args(
        ["proteus", "x.xml", "--fresh-database", "--neo4j-home", "/srv/neo4j"]
    )
    assert args.fresh_database is True and args.neo4j_home == Path("/srv/neo4j")


def test_flags_refuse_no_neo4j() -> None:
    argv = ["synthetic", "--n-units", "1", "--no-neo4j", "--fresh-database"]
    args = ingest_cli._parse_args(argv)
    with pytest.raises(SystemExit, match="drop --no-neo4j"):
        ingest_cli._measurement_from_flags(args)
