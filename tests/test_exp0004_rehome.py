"""`exp0004.rehome`: the sealed questions copied onto the variant corpus, nothing else changed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from plantgraph.exp0004 import rehome
from plantgraph.exp0004.rehome import CorpusIdentity, RehomeProof

SEALED, VARIANT = "H1000g2", "H1000g2V"
SAME_PLANT = CorpusIdentity(source_graph_hash="h1", manifest_digest="m1", n_variant_references=0)
VARIANT_OF_IT = CorpusIdentity(source_graph_hash="h1", manifest_digest="m1", n_variant_references=7)


def _question(name: str, answers: list[str]) -> dict[str, Any]:
    return {
        "question_id": f"{SEALED}:LOOKUP_TYPE:{name}", "corpus_id": SEALED, "family": "LOOKUP_TYPE",
        "template_id": "LOOKUP_TYPE", "template_version": "1", "text": f"What is {name}?",
        "answer_type": "TAG_SET", "answerable": True, "reference": answers, "evidence_tags": [name],
        "evidence_sheets": ["3"], "k": 0, "k_connector": 0, "k_identity": 1, "u": 0,
        "anchors": [name], "generator_seed": 31,
    }  # fmt: skip


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "sealed" / "questions.jsonl"
    path.parent.mkdir()
    rows = [_question("P-101", ["A"]), _question("V-7", ["B", "C"])]
    path.write_bytes(rehome._to_jsonl(rows))
    return path


def _run(
    source: Path, tmp_path: Path, sealed: CorpusIdentity = SAME_PLANT,
    variant: CorpusIdentity = VARIANT_OF_IT,
) -> RehomeProof:  # fmt: skip
    return rehome.rehome_questions(
        source, tmp_path / "out" / "questions.jsonl", tmp_path / "proof.json", SEALED, VARIANT,
        sealed, variant,
    )  # fmt: skip


def test_the_copy_equals_the_source_except_corpus_id(source: Path, tmp_path: Path) -> None:
    before = source.read_bytes()
    proof = _run(source, tmp_path)

    original = [json.loads(line) for line in source.read_text().splitlines()]
    copy = [
        json.loads(line) for line in (tmp_path / "out" / "questions.jsonl").read_text().splitlines()
    ]
    assert len(copy) == proof.n_questions == 2
    for old, new in zip(original, copy, strict=True):
        assert new["corpus_id"] == VARIANT and old["corpus_id"] == SEALED
        assert {k: v for k, v in new.items() if k != "corpus_id"} == {
            k: v for k, v in old.items() if k != "corpus_id"
        }
    assert source.read_bytes() == before  # the sealed file is never written


def test_the_proof_records_hashes_and_the_three_equalities(source: Path, tmp_path: Path) -> None:
    proof = _run(source, tmp_path)

    on_disk = RehomeProof.model_validate_json((tmp_path / "proof.json").read_text())
    assert on_disk == proof
    assert proof.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    out = (tmp_path / "out" / "questions.jsonl").read_bytes()
    assert proof.output_sha256 == hashlib.sha256(out).hexdigest()
    assert proof.other_fields_equal and proof.source_graph_hash_equal
    assert proof.manifest_equal_modulo_reference_tags and proof.n_variant_references_variant == 7


def test_a_different_source_graph_hash_is_refused_and_nothing_is_written(
    source: Path, tmp_path: Path
) -> None:
    other_plant = VARIANT_OF_IT.model_copy(update={"source_graph_hash": "h2"})

    with pytest.raises(ValueError, match="source_graph_hash h1.*found h2"):
        _run(source, tmp_path, variant=other_plant)
    assert not (tmp_path / "out").exists() and not (tmp_path / "proof.json").exists()


def test_a_manifest_that_differs_beyond_reference_tags_is_refused(
    source: Path, tmp_path: Path
) -> None:
    changed = VARIANT_OF_IT.model_copy(update={"manifest_digest": "m2"})

    with pytest.raises(ValueError, match="modulo reference tags"):
        _run(source, tmp_path, variant=changed)


def test_a_sealed_corpus_with_rewritten_tags_is_refused(source: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exact tags in the sealed corpus"):
        _run(source, tmp_path, sealed=VARIANT_OF_IT)


@pytest.mark.parametrize("which", ["out", "proof"])
def test_an_existing_output_is_never_overwritten(source: Path, tmp_path: Path, which: str) -> None:
    existing = tmp_path / ("out/questions.jsonl" if which == "out" else "proof.json")
    existing.parent.mkdir(exist_ok=True)
    existing.write_text("keep me")

    with pytest.raises(FileExistsError, match="never overwritten"):
        _run(source, tmp_path)
    assert existing.read_text() == "keep me"
    assert not (tmp_path / "proof.json").exists() or which == "proof"


def test_a_question_of_another_corpus_is_refused(tmp_path: Path) -> None:
    foreign = tmp_path / "q.jsonl"
    foreign.write_bytes(rehome._to_jsonl([{**_question("P-1", ["A"]), "corpus_id": "other"}]))

    with pytest.raises(ValueError, match=f"only {SEALED!r} questions"):
        _run(foreign, tmp_path)


def test_the_variant_must_have_another_corpus_id(source: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="other than"):
        rehome.rehome_questions(
            source, tmp_path / "o.jsonl", tmp_path / "p.json", SEALED, SEALED, SAME_PLANT,
            VARIANT_OF_IT,
        )  # fmt: skip


def test_main_reads_both_identities_from_the_ingest_files(source: Path, tmp_path: Path) -> None:
    asked: list[tuple[str, Path]] = []

    def fake_identity(corpus_id: str, ingest_json: Path) -> CorpusIdentity:
        asked.append((corpus_id, ingest_json))
        return SAME_PLANT if corpus_id == SEALED else VARIANT_OF_IT

    rehome.main(
        [
            "--source", str(source), "--variant-corpus-id", VARIANT,
            "--out", str(tmp_path / "o.jsonl"), "--proof", str(tmp_path / "p.json"),
            "--sealed-ingest", "s.json", "--variant-ingest", "v.json",
        ],
        load_identity=fake_identity,
    )  # fmt: skip

    assert asked == [(SEALED, Path("s.json")), (VARIANT, Path("v.json"))]
    assert (tmp_path / "o.jsonl").is_file() and (tmp_path / "p.json").is_file()
