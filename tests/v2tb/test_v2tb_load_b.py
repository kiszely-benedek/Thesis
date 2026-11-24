"""T14d R19: the B Neo4j loader sends the patched plan and refuses a database that lacks positions.

The two database calls are stubs: no Neo4j is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.load_step import LoadOutcome, StoreMeasurement
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.v2tb import __main__ as b_cli
from plantgraph.qa.v2tb.load_b import LOAD_RECORD_FILE_NAME, expected_counts, load_b_corpus
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME, read_positions_file
from plantgraph.qa.v2tb.store_b import count_positioned_rows, ingest_positions
from plantgraph.store.neo4j_loader import LoadReport
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings

CORPUS_ID = "LoadB"
_CONFIG = GeneratorConfigV22(seed=1, n_units=8)
_SETTINGS = Neo4jSettings(uri="bolt://nowhere", username="u", password="p")  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def corpora_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("load-b") / "corpora"
    result = run_synthetic(
        corpus_id=CORPUS_ID,
        generator_config=_CONFIG,
        split_config=HeadlinePresetV22().split_config(1),
        check=False,
        settings=None,
        store_profile="plant_lines",
    )
    (root / CORPUS_ID).mkdir(parents=True)
    (root / CORPUS_ID / "ingest.json").write_text(result.model_dump_json(), encoding="utf-8")
    ingest_positions(_CONFIG, root / CORPUS_ID)
    return root


class _Loader:
    """Stands in for the frozen loader: records the plan and the measurement it was given."""

    def __init__(self) -> None:
        self.plans: list[LoadPlan] = []
        self.measurements: list[StoreMeasurement] = []

    def __call__(
        self,
        settings: Neo4jSettings,
        plan: LoadPlan,
        stage_seconds: dict[str, float],
        measurement: StoreMeasurement,
    ) -> LoadOutcome:
        self.plans.append(plan)
        self.measurements.append(measurement)
        report = LoadReport(
            corpus_id=plan.corpus_id,
            nodes_written=7,
            relationships_written=3,
            batch_size=1,
            wipe_s=0,
            schema_s=0,
            nodes_s=0,
            relationships_s=0,
            verify_s=0,
            total_s=0,
            neo4j_version=None,
        )
        return LoadOutcome(report=report)


def _file_counts(root: Path) -> dict[str, int]:
    positions, _sha = read_positions_file(root / CORPUS_ID / POSITIONS_FILE_NAME)
    return {code: list(positions.values()).count(code) for code in set(positions.values())}


def test_the_patched_plan_is_the_one_sent_and_the_record_is_written(corpora_root: Path) -> None:
    loader = _Loader()
    counts = _file_counts(corpora_root)

    record = load_b_corpus(
        CORPUS_ID,
        corpora_root,
        _SETTINGS,
        fresh_database=True,
        loader=loader,
        counter=lambda _settings: counts,
    )

    assert count_positioned_rows(loader.plans[0]) == sum(counts.values()) > 0
    assert loader.measurements == [StoreMeasurement(fresh_database=True)]
    assert record.expected_per_code == record.database_per_code == counts
    line = (corpora_root / CORPUS_ID / LOAD_RECORD_FILE_NAME).read_text(encoding="utf-8")
    assert json.loads(line.splitlines()[-1])["positions_sha256"] == record.positions_sha256


def test_a_database_whose_counts_differ_from_the_file_is_refused(corpora_root: Path) -> None:
    short = {code: n - 1 for code, n in _file_counts(corpora_root).items()}

    with pytest.raises(ValueError, match="expected the database to hold operating_position"):
        load_b_corpus(
            CORPUS_ID,
            corpora_root,
            _SETTINGS,
            fresh_database=False,
            loader=_Loader(),
            counter=lambda _settings: short,
        )


def test_an_id_without_the_b_suffix_is_refused_before_any_file_is_read(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected a B corpus id"):
        load_b_corpus("H1000g22p1", tmp_path, _SETTINGS, fresh_database=False)


def test_a_both_profile_store_keeps_each_valve_twice(corpora_root: Path) -> None:
    loader = _Loader()
    counts = _file_counts(corpora_root)
    load_b_corpus(
        CORPUS_ID,
        corpora_root,
        _SETTINGS,
        fresh_database=False,
        loader=loader,
        counter=lambda _settings: counts,
    )
    both = loader.plans[0].model_copy(update={"profile": "both"})
    positions, _sha = read_positions_file(corpora_root / CORPUS_ID / POSITIONS_FILE_NAME)

    assert expected_counts(positions, both) == {code: 2 * n for code, n in counts.items()}


def test_the_load_command_refuses_an_id_without_b(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(b_cli, "from_env", lambda: _SETTINGS)

    with pytest.raises(SystemExit, match="expected a B corpus id"):
        b_cli.main(["load", "--corpus-id", "H1000g22p1", "--corpora-root", str(tmp_path)])


def test_a_params_file_naming_both_x_and_x_b_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "params.json"
    path.write_text(json.dumps({"graph_agent_lines": {}, "graph_agent_lines_b": {}}))

    with pytest.raises(SystemExit, match="under both names"):
        b_cli.b_strategy_params(path, ["graph_agent_lines_b"])
    path.write_text(json.dumps({"graph_agent_lines": {"max_steps": 3}}))
    assert b_cli.b_strategy_params(path, ["graph_agent_lines_b"]) == {
        "graph_agent_lines_b": {"max_steps": 3}
    }
