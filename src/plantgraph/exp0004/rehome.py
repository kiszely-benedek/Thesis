"""Copy the sealed question set onto the variant corpus, changing nothing but `corpus_id`.

python -m plantgraph.exp0004.rehome --source Q.jsonl --variant-corpus-id H1000g2V \
    --out NEW.jsonl --proof PROOF.json --sealed-ingest S/ingest.json --variant-ingest V/ingest.json

Why a copy: the harness refuses questions whose `corpus_id` is not the corpus it runs
(`qa/harness/question_set.py`), and the sealed file must stay as R5 asked it. The proof file shows
the copy is the same questions on the same plant: every other field equal, `source_graph_hash` (a
hash of the generated plant, before any drawing is split off) equal, and the split manifest (the
answer key that says which sheets hold which equipment) equal once the re-written reference tags
are set aside.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.models import Question

DEFAULT_SEALED_CORPUS_ID = "H1000g2"


class CorpusIdentity(BaseModel):
    """What makes two corpora the same plant: the plant hash and the manifest without ref. tags."""

    source_graph_hash: str
    manifest_digest: str
    #: how many references carry a re-written tag (0 for an exact-tag corpus)
    n_variant_references: int


class RehomeProof(BaseModel):
    """The evidence written beside the copy (design section 7.2, point 3)."""

    source_path: str
    source_sha256: str
    output_path: str
    output_sha256: str
    sealed_corpus_id: str
    variant_corpus_id: str
    n_questions: int
    other_fields_equal: bool
    source_graph_hash: str
    source_graph_hash_equal: bool
    manifest_digest: str
    manifest_equal_modulo_reference_tags: bool
    n_variant_references_sealed: int
    n_variant_references_variant: int


IdentityLoader = Callable[[str, Path], CorpusIdentity]


def corpus_identity(corpus_id: str, ingest_json: Path) -> CorpusIdentity:
    """Rebuild a corpus from its `ingest.json` and read its identity (slow: one plant generation).

    Raises:
        ValueError: the corpus has no answer key (a real import, not a synthetic plant).
    """
    gold = load_corpus_artifacts(corpus_id, ingest_json).gold
    if gold.manifest is None or gold.manifest.source_graph_hash is None:
        raise ValueError(f"expected {corpus_id!r} to carry a split manifest with a plant hash")
    manifest = gold.manifest.model_dump(mode="json")
    manifest.pop("created_at")  # the wall-clock time of the build, different on every rebuild
    variants = 0
    for group in manifest["identity_groups"]:
        variants += len(group.pop("tag_variants"))  # the one field EXP-0004 re-writes
    return CorpusIdentity(
        source_graph_hash=gold.manifest.source_graph_hash,
        manifest_digest=_digest(manifest),
        n_variant_references=variants,
    )


def check_same_plant(sealed: CorpusIdentity, variant: CorpusIdentity) -> None:
    """Refuse a variant corpus that is not the sealed plant with re-written reference tags.

    Raises:
        ValueError: the plant hash or the manifest (modulo reference tags) differs, or the
            sealed corpus already has re-written tags.
    """
    if sealed.source_graph_hash != variant.source_graph_hash:
        raise ValueError(
            f"expected the variant corpus to have source_graph_hash {sealed.source_graph_hash}, "
            f"found {variant.source_graph_hash}: it is another plant"
        )
    if sealed.manifest_digest != variant.manifest_digest:
        raise ValueError(
            "expected the variant manifest to equal the sealed one modulo reference tags, "
            "found a difference outside tag_variants"
        )
    if sealed.n_variant_references != 0:
        raise ValueError(
            f"expected exact tags in the sealed corpus, found {sealed.n_variant_references} "
            "re-written references"
        )


def rehome_questions(
    source: Path,
    out: Path,
    proof_path: Path,
    sealed_corpus_id: str,
    variant_corpus_id: str,
    sealed: CorpusIdentity,
    variant: CorpusIdentity,
) -> RehomeProof:
    """Write the re-homed copy and its proof; never overwrite, never touch `source`.

    Raises:
        ValueError: the two corpora are not the same plant, an id is unchanged, or a source question
            belongs to another corpus.
        FileExistsError: `out` or `proof_path` exists.
    """
    if variant_corpus_id == sealed_corpus_id:
        raise ValueError(f"expected a variant corpus id other than {sealed_corpus_id!r}")
    for target in (out, proof_path):
        if target.exists():
            raise FileExistsError(
                f"expected {target} not to exist (a measurement is never overwritten), found it"
            )
    check_same_plant(sealed, variant)
    source_bytes = source.read_bytes()
    originals = _read_rows(source_bytes, sealed_corpus_id, source)
    copies = [{**row, "corpus_id": variant_corpus_id} for row in originals]
    _check_only_corpus_id_changed(originals, copies)
    out_bytes = _to_jsonl(copies)
    proof = RehomeProof(
        source_path=source.as_posix(),
        source_sha256=_sha256(source_bytes),
        output_path=out.as_posix(),
        output_sha256=_sha256(out_bytes),
        sealed_corpus_id=sealed_corpus_id,
        variant_corpus_id=variant_corpus_id,
        n_questions=len(copies),
        other_fields_equal=True,  # _check_only_corpus_id_changed raised otherwise
        source_graph_hash=variant.source_graph_hash,
        source_graph_hash_equal=True,  # check_same_plant raised otherwise
        manifest_digest=variant.manifest_digest,
        manifest_equal_modulo_reference_tags=True,
        n_variant_references_sealed=sealed.n_variant_references,
        n_variant_references_variant=variant.n_variant_references,
    )
    _write_new(out, out_bytes)
    _write_new(proof_path, (proof.model_dump_json(indent=1) + "\n").encode("utf-8"))
    return proof


def _read_rows(data: bytes, sealed_corpus_id: str, source: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    wrong = [r.get("question_id") for r in rows if r.get("corpus_id") != sealed_corpus_id]
    if wrong:
        raise ValueError(
            f"expected only {sealed_corpus_id!r} questions in {source}, found {wrong[:3]}"
        )
    return rows


def _check_only_corpus_id_changed(
    originals: list[dict[str, Any]], copies: list[dict[str, Any]]
) -> None:
    """Compare question by question, and check the harness's own model still accepts each copy."""
    for original, copy in zip(originals, copies, strict=True):
        changed = sorted(k for k in original if k != "corpus_id" and original[k] != copy[k])
        if changed:
            raise ValueError(f"expected only corpus_id to change, found {changed}")
        Question.model_validate(copy)


def _to_jsonl(rows: list[dict[str, Any]]) -> bytes:
    """One compact JSON object per line, LF endings (the same shape as `qa.questions` writes)."""
    lines = [json.dumps(row, separators=(",", ":"), ensure_ascii=False) for row in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    """Create `path` and write bytes (no newline translation); mode `xb` fails if it exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def main(argv: list[str] | None = None, load_identity: IdentityLoader = corpus_identity) -> None:
    """Rebuild both corpora to read their identity, then write the copy and its proof."""
    args = _parser().parse_args(argv)
    sealed = load_identity(args.sealed_corpus_id, args.sealed_ingest)
    variant = load_identity(args.variant_corpus_id, args.variant_ingest)
    proof = rehome_questions(
        args.source, args.out, args.proof, args.sealed_corpus_id, args.variant_corpus_id,
        sealed, variant,
    )  # fmt: skip
    print(
        f"rehomed {proof.n_questions} questions: {proof.output_path} sha256 {proof.output_sha256}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004.rehome", description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="the sealed questions.jsonl")
    parser.add_argument("--variant-corpus-id", required=True)
    parser.add_argument("--sealed-corpus-id", default=DEFAULT_SEALED_CORPUS_ID)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--sealed-ingest", type=Path, required=True, help="the sealed ingest.json")
    parser.add_argument(
        "--variant-ingest", type=Path, required=True, help="the variant ingest.json"
    )
    return parser


if __name__ == "__main__":
    main()
