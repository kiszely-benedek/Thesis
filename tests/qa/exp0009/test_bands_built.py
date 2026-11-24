"""The sealed band report describes the plants as built (T13c, B4), whatever their seeds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.seed_plan import load_seed_plan, require_drawn_test_seed
from plantgraph.qa.exp0009 import bands_built
from plantgraph.qa.exp0009.build import build_plant
from plantgraph.qa.exp0009.draw import real_document_flags
from plantgraph.qa.exp0009.plan import PlantSpec22, Role, plant_id

N_UNITS = 3
EXP0009_SEEDS = Path("data/runs/exp0009/prereg/seeds.json")  # the drawn plan, which holds 5669


def _sealed_spec(index: int, seed: int, untagged: bool) -> PlantSpec22:
    config = HeadlinePresetV22().generator_config(N_UNITS, seed)
    flags = (untagged,) * len(real_document_flags(N_UNITS, seed))
    return PlantSpec22(
        plant_id=plant_id(Role.SEALED, 100, index), role=Role.SEALED, scale=100, seed=seed,
        target_sheets=97, n_units=N_UNITS, predicted_sheets=plan_plant(config).sheet_count,
        document_untagged=flags,
    )  # fmt: skip


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[PlantSpec22]]:
    """Two small sealed plants on drawn seeds of EXP-0009 (5669 is p1; 5474 is p2)."""
    corpora = tmp_path_factory.mktemp("bands") / "corpora"
    specs = [_sealed_spec(1, 5669, untagged=False), _sealed_spec(2, 5474, untagged=True)]
    for spec in specs:
        build_plant(spec, corpora, load_seed_plan(EXP0009_SEEDS))
    return corpora, specs


def test_the_frozen_command_refuses_these_seeds_which_is_why_it_is_not_used() -> None:
    for seed in (5669, 5791):
        with pytest.raises(ValueError, match="drawn seed plan"):
            require_drawn_test_seed(seed, load_seed_plan())


def test_each_built_plant_is_planned_from_its_own_recorded_seed_size_and_tagging(
    built: tuple[Path, list[PlantSpec22]],
) -> None:
    corpora, specs = built
    for spec in specs:
        recorded = bands_built.recorded_config(corpora / spec.plant_id / "ingest.json")
        assert recorded == spec.generator_config()  # seed, n_units and document_untagged
        report = bands_built.built_report(corpora, spec.plant_id)
        assert (report.seed, report.n_units) == (spec.seed, N_UNITS)
        assert report.n_sheets == spec.predicted_sheets and report.corpus_id == spec.plant_id


def test_the_pooled_report_covers_every_plant_and_is_written_as_json(
    built: tuple[Path, list[PlantSpec22]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpora, specs = built
    out = tmp_path / "composition_sealed100.json"
    argv = ["--root", str(corpora.parent), "--plants", *(s.plant_id for s in specs)]
    code = bands_built.main([*argv, "--json", str(out)])
    document = json.loads(out.read_text(encoding="utf-8"))
    assert [p["seed"] for p in document["plants"]] == [5669, 5474]
    assert code in (0, 1)  # tiny plants may miss a band; the point is a report, not a crash
    assert "pooled over 2 plants" in capsys.readouterr().out


def test_a_plant_without_a_recorded_generator_config_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ingest.json"
    path.write_text(json.dumps({"config": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="config.generator"):
        bands_built.recorded_config(path)
