"""F7: the run freeze also records hashes of the prompt-building code and of each `ingest.json`."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.harness import freeze
from plantgraph.qa.harness.freeze import (
    PROMPT_BUILDING_MODULES,
    PROMPT_BUILDING_MODULES_OUTSIDE_QA,
    changed_inputs,
    code_hashes,
    corpus_ingest_hashes,
    differing_fields,
)
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import RunConfig
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config

_REPO_ROOT = Path(__file__).resolve().parents[1]
#: A run stored long before the F7 fields existed.
_OLD_RUN_CONFIG = _REPO_ROOT / "data/runs/cv1/infra/runs/INF-AGL3-D100/run_config.json"


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("freeze-inputs-toy"))


@pytest.fixture
def fake_qa_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the code hashing at one small module in a temp folder, so a test can edit it."""
    module_dir = tmp_path / "qa"
    module_dir.mkdir()
    (module_dir / "builder.py").write_text("PROMPT = 'v1'\n", encoding="utf-8")
    monkeypatch.setattr(freeze, "_QA_DIR", module_dir)
    monkeypatch.setattr(freeze, "PROMPT_BUILDING_MODULES", ("builder.py",))
    monkeypatch.setattr(freeze, "PROMPT_BUILDING_MODULES_OUTSIDE_QA", ())
    return module_dir


def _run(toy: Toy, config: RunConfig, tmp_path: Path, fake: FakeTransport) -> None:
    run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
    )


def test_every_listed_prompt_building_module_exists() -> None:
    hashes = code_hashes()

    outside = [f"plantgraph/{name}" for name in PROMPT_BUILDING_MODULES_OUTSIDE_QA]
    assert sorted(hashes) == sorted([*PROMPT_BUILDING_MODULES, *outside])
    assert "plantgraph/graph/line_view.py" in hashes
    assert all(len(digest) == 64 for digest in hashes.values())


def test_a_missing_listed_module_is_refused_with_its_path(
    fake_qa_dir: Path,
) -> None:
    (fake_qa_dir / "builder.py").unlink()

    with pytest.raises(FileNotFoundError, match="builder.py"):
        code_hashes()


def test_an_old_run_config_still_loads_and_is_not_compared_on_the_new_fields() -> None:
    old = RunConfig.model_validate_json(_OLD_RUN_CONFIG.read_text(encoding="utf-8"))
    assert old.code_hashes == {} and old.corpus_ingest_sha256 == {}

    resumed_by_new_code = old.model_copy(
        update={"code_hashes": code_hashes(), "corpus_ingest_sha256": {"x": "0" * 64}}
    )

    assert differing_fields(old, resumed_by_new_code) == []
    assert changed_inputs(old, Path("nowhere")) == []


def test_a_changed_prompt_module_is_listed_as_changed(fake_qa_dir: Path) -> None:
    config = make_config_without_toy(code_hashes())
    assert changed_inputs(config, Path("unused")) == []

    (fake_qa_dir / "builder.py").write_text("PROMPT = 'v2'\n", encoding="utf-8")

    assert changed_inputs(config, Path("unused")) == ["code:builder.py"]


def test_a_changed_prompt_module_refuses_a_resume(
    toy: Toy, tmp_path: Path, fake_qa_dir: Path
) -> None:
    first = make_config(toy, allow_paid_calls=True, code_hashes=code_hashes())
    _run(toy, first, tmp_path, abstaining_transport())

    (fake_qa_dir / "builder.py").write_text("PROMPT = 'v2'\n", encoding="utf-8")

    # a resume that re-reads the code: the frozen record differs from the new hashes
    with pytest.raises(ValueError, match="already frozen.*code_hashes"):
        _run(
            toy,
            make_config(toy, allow_paid_calls=True, code_hashes=code_hashes()),
            tmp_path,
            abstaining_transport(),
        )
    # a resume that reuses the old config object: the disk differs from its hashes
    with pytest.raises(ValueError, match="code:builder.py"):
        _run(toy, first, tmp_path, abstaining_transport())


def test_a_changed_ingest_json_refuses_a_resume(toy: Toy, tmp_path: Path) -> None:
    root = toy.corpora_root
    recorded = corpus_ingest_hashes([CORPUS_ID], root)
    config = make_config(toy, allow_paid_calls=True, corpus_ingest_sha256=recorded)
    stale = config.model_copy(update={"corpus_ingest_sha256": {CORPUS_ID: "0" * 64}})

    assert changed_inputs(config, root) == []
    assert changed_inputs(stale, root) == [f"corpus:{CORPUS_ID}"]
    with pytest.raises(ValueError, match=f"corpus:{CORPUS_ID}"):
        _run(toy, stale, tmp_path, abstaining_transport())


def test_a_missing_ingest_json_is_refused_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="ghost"):
        corpus_ingest_hashes(["ghost"], tmp_path)


def make_config_without_toy(hashes: dict[str, str]) -> RunConfig:
    """The old on-disk config with `code_hashes` filled in: enough for `changed_inputs`."""
    old = RunConfig.model_validate_json(_OLD_RUN_CONFIG.read_text(encoding="utf-8"))
    return old.model_copy(update={"code_hashes": hashes})


def test_the_second_review_modules_are_in_the_prompt_building_list() -> None:
    # R1: the agent loop, the Cypher guard and the context-choosing modules shape prompt text
    for name in (
        "agent/loop.py",
        "agent/actions.py",
        "plant_api/tool_registry.py",
        "plant_api/primitives.py",
        "tag_check.py",
        "cypher.py",
        "cypher_guard.py",
        "need/context.py",
        "need/programs.py",
        "sheet_selection.py",
        "anchors.py",
        "plant_api/traversal.py",
        "plant_api/item_graph.py",
        "plant_api/line_graph.py",
    ):
        assert name in PROMPT_BUILDING_MODULES
