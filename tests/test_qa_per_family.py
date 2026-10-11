"""The per-family sampler: n per family, spread over k-bins, deterministic bytes."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from plantgraph.qa.models import Question
from plantgraph.qa.questions import per_family
from plantgraph.qa.questions.availability import k_bin_of
from plantgraph.qa.questions.per_family import (
    filter_by_split,
    sample_family,
    sample_per_family,
)


def _question(question_id: str, family: str, k: int | None) -> Question:
    fields: dict[str, Any] = {
        "question_id": question_id,
        "corpus_id": "T",
        "family": family,
        "template_id": family,
        "template_version": "1",
        "text": "?",
        "answer_type": "BOOLEAN",
        "answerable": k is not None,
        "reference": "yes",
        "k": k,
        "generator_seed": 1,
    }
    return Question.model_validate(fields)


def _pool() -> list[Question]:
    """CONNECTED: 6 questions in 3 bins (k=0, 1, 3-4). FLOW_PATH: 3 questions, one bin."""
    connected = [("c0", 0), ("c1", 0), ("c2", 1), ("c3", 1), ("c4", 3), ("c5", 3)]
    flow = [("f0", 0), ("f1", 0), ("f2", 0)]
    return [_question(f"T:{i}", "CONNECTED", k) for i, k in connected] + [
        _question(f"T:{i}", "FLOW_PATH", k) for i, k in flow
    ]


def test_each_family_gets_n_questions_spread_over_its_bins() -> None:
    chosen = sample_per_family(_pool(), 3, seed=7)

    per_family_count = Counter(q.family.value for q in chosen)
    connected_bins = Counter(k_bin_of(q).value for q in chosen if q.family.value == "CONNECTED")
    assert per_family_count == {"CONNECTED": 3, "FLOW_PATH": 3}
    assert connected_bins == {"0": 1, "1": 1, "3-4": 1}  # round-robin: one per bin


def test_a_family_with_fewer_than_n_candidates_keeps_all_of_them() -> None:
    chosen = sample_per_family(_pool(), 5, seed=7)

    assert Counter(q.family.value for q in chosen) == {"CONNECTED": 5, "FLOW_PATH": 3}
    assert len(sample_family(_pool()[6:], 10, seed=7)) == 3


def test_same_seed_same_questions_and_a_new_seed_changes_the_draw() -> None:
    first = sample_per_family(_pool(), 2, seed=1)

    assert first == sample_per_family(_pool(), 2, seed=1)
    assert any(first != sample_per_family(_pool(), 2, seed=s) for s in range(2, 12))


def test_output_keeps_the_input_order() -> None:
    chosen = sample_per_family(_pool(), 2, seed=3)
    order = [q.question_id for q in _pool()]

    assert [q.question_id for q in chosen] == sorted(
        (q.question_id for q in chosen), key=order.index
    )


def test_another_family_does_not_change_a_familys_draw() -> None:
    alone = sample_family([q for q in _pool() if q.family.value == "CONNECTED"], 2, seed=5)
    together = [q for q in sample_per_family(_pool(), 2, seed=5) if q.family.value == "CONNECTED"]

    assert sorted(q.question_id for q in alone) == sorted(q.question_id for q in together)


def test_n_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive number"):
        sample_per_family(_pool(), 0, seed=1)


def test_filter_by_split_checks_coverage_and_names() -> None:
    splits = {
        q.question_id: ("held-out" if q.family.value == "FLOW_PATH" else "dev-old") for q in _pool()
    }

    kept = filter_by_split(_pool(), splits, ["held-out"])

    assert {q.family.value for q in kept} == {"FLOW_PATH"}
    with pytest.raises(ValueError, match="missing"):
        filter_by_split(_pool(), {"T:c0": "dev-old"}, ["dev-old"])
    with pytest.raises(ValueError, match="splits that occur"):
        filter_by_split(_pool(), splits, ["dev-new"])


def _write_candidates(path: Path) -> None:
    lines = "".join(q.model_dump_json() + "\n" for q in _pool())
    path.write_bytes(lines.encode("utf-8"))


def test_cli_writes_identical_bytes_twice_and_original_lines(tmp_path: Path) -> None:
    source = tmp_path / "candidates.jsonl"
    _write_candidates(source)
    arguments = ["--in", str(source), "--n", "2", "--seed", "20261031"]

    per_family.main([*arguments, "--out", str(tmp_path / "a")])
    per_family.main([*arguments, "--out", str(tmp_path / "b")])

    first = (tmp_path / "a" / "questions.jsonl").read_bytes()
    assert first == (tmp_path / "b" / "questions.jsonl").read_bytes()
    assert b"\r" not in first
    originals = set(source.read_text(encoding="utf-8").splitlines())
    assert set(first.decode("utf-8").splitlines()) <= originals


def test_cli_only_splits_draws_from_the_named_splits(tmp_path: Path) -> None:
    source = tmp_path / "candidates.jsonl"
    _write_candidates(source)
    splits = {
        q.question_id: ("held-out" if q.family.value == "FLOW_PATH" else "dev-old") for q in _pool()
    }
    splits_path = tmp_path / "splits.json"
    splits_path.write_text(json.dumps(splits), encoding="utf-8")

    per_family.main(
        [*("--in", str(source), "--n", "2", "--seed", "1", "--out", str(tmp_path / "o")),
         *("--splits", str(splits_path), "--only-splits", "held-out")]
    )  # fmt: skip

    written = (tmp_path / "o" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    assert {json.loads(line)["family"] for line in written} == {"FLOW_PATH"}
    assert len(written) == 2


def test_cli_only_splits_without_a_splits_file_is_an_error(tmp_path: Path) -> None:
    source = tmp_path / "candidates.jsonl"
    _write_candidates(source)

    with pytest.raises(SystemExit, match="--only-splits needs --splits"):
        per_family.main(
            [
                "--in",
                str(source),
                "--n",
                "2",
                "--seed",
                "1",
                "--out",
                str(tmp_path),
                "--only-splits",
                "x",
            ]
        )
