"""The unchanged-path check, the seed check and the Neo4j target guard (no git history needed)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from plantgraph.ingest.headline_v2 import TEST_SEEDS_V2
from plantgraph.qa.exp0007 import hygiene, paths

QA = "src/plantgraph/qa/"


def test_a_changed_system_file_is_flagged_and_the_six_named_ones_are_not() -> None:
    changed = [*paths.NAMED_EXCEPTIONS, f"{QA}strategies/context_rag.py", f"{QA}serialize.py"]
    assert paths.unexpected_changes(changed) == [
        f"{QA}serialize.py",
        f"{QA}strategies/context_rag.py",
    ]


def test_data_side_and_gold_side_files_are_not_system_side() -> None:
    free = [
        f"{QA}harness/gold.py",
        f"{QA}harness/family_meta.py",
        f"{QA}harness/need_gold.py",
        f"{QA}corpus.py",
        f"{QA}questions/families.py",
        "src/plantgraph/benchmark/v2/config.py",
        f"{QA}exp0007/cli.py",
    ]
    assert paths.unexpected_changes(free) == []


def test_every_directory_and_module_of_the_list_is_system_side() -> None:
    for name in (
        "strategies/x.py",
        "agent/x.py",
        "plant_api/x.py",
        "prompts/x.txt",
        "cascade/x.py",
        "need/x.py",
        "harness/other.py",
    ):
        assert paths.is_system_side(f"{QA}{name}"), name
    assert paths.is_system_side("src/plantgraph/llm/client.py")
    assert paths.is_system_side("src/plantgraph/store/neo4j_plan.py")
    assert paths.is_system_side(f"{QA}scoring.py") and not paths.is_system_side(
        f"{QA}scoring_notes.py"
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_changed_since_sees_edits_and_new_files_in_a_real_repository(tmp_path: Path) -> None:
    system = tmp_path / QA
    system.mkdir(parents=True)
    (system / "serialize.py").write_text("a = 1\n")
    (system / "scoring.py").write_text("b = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "freeze")
    freeze = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    (system / "serialize.py").write_text("a = 2\n")
    (system / "class_vocabulary.py").write_text("c = 1\n")
    (system / "fit.py").write_text("d = 1\n")  # new and unexpected
    assert paths.changed_since(tmp_path, freeze) == [
        f"{QA}class_vocabulary.py",
        f"{QA}fit.py",
        f"{QA}serialize.py",
    ]
    assert paths.check_paths(tmp_path, freeze) == [f"{QA}fit.py", f"{QA}serialize.py"]


def test_git_failure_is_an_error_not_an_empty_answer(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="expected `git diff"):
        paths.changed_since(tmp_path, "deadbeef")


def test_the_registered_seed_table_equals_the_code() -> None:
    hygiene.assert_registered_seeds()
    assert hygiene.REGISTERED_TEST_SEEDS_V2 == TEST_SEEDS_V2


def _ingest(path: Path, seed: int | None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    generator = {} if seed is None else {"seed": seed}
    path.write_text(json.dumps({"config": {"generator": generator}}))
    return path


def test_a_test_seed_in_an_earlier_record_is_refused_but_the_runs_own_data_is_skipped(
    tmp_path: Path,
) -> None:
    own = tmp_path / "runs" / "exp0007"
    _ingest(own / "ladder" / "ingest.json", 5001)  # this run's own corpus: allowed
    _ingest(tmp_path / "old" / "ingest.json", 1)
    _ingest(tmp_path / "proteus" / "ingest.json", None)
    hygiene.require_no_leaked_seeds(tmp_path, own)
    _ingest(tmp_path / "leak" / "ingest.json", 5002)
    with pytest.raises(ValueError, match=r"seed 5002"):
        hygiene.require_no_leaked_seeds(tmp_path, own)


def test_the_plant_database_needs_an_explicit_flag() -> None:
    assert hygiene.require_database("e7tmp", False) == "e7tmp"
    assert hygiene.require_database("neo4j", True) == "neo4j"
    with pytest.raises(ValueError, match="refusing the user's plant database"):
        hygiene.require_database("neo4j", False)
    with pytest.raises(ValueError, match="E7_NEO4J_DATABASE"):
        hygiene.require_database(None, False)
    with pytest.raises(ValueError, match="plain database name"):
        hygiene.require_database("a b; DROP", False)


def _ingest_record(corpus_id: str, gate: bool, identity: dict[str, object]) -> dict[str, object]:
    return {"corpus_id": corpus_id, "gate_equal": gate, "resolution_score": {"identity": identity}}


def test_a_fresh_ingest_must_pass_g1_and_the_identity_score(tmp_path: Path) -> None:
    from plantgraph.qa.exp0007.freeze_checks import ingest_problems

    perfect = {
        "true_positives": 3,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": 1.0,
        "recall": 1.0,
    }
    no_pairs = {
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": None,
        "recall": None,
    }
    bad = {
        "true_positives": 3,
        "false_positives": 1,
        "false_negatives": 0,
        "precision": 0.75,
        "recall": 1.0,
    }
    path = tmp_path / "ingest.json"
    for record, expected in [
        (_ingest_record("H1g2", True, perfect), []),
        (_ingest_record("H1g2", True, no_pairs), []),  # a one-sheet corpus has no identity pairs
        (_ingest_record("H1g2", False, perfect), ["gate_equal"]),
        (_ingest_record("H1g2", True, bad), ["identity precision"]),
        (_ingest_record("D1g2", True, perfect), ["corpus_id"]),
    ]:
        path.write_text(json.dumps(record))
        found = ingest_problems(path, "H1g2")
        assert len(found) == len(expected) and all(
            e in f for e, f in zip(expected, found, strict=True)
        )
