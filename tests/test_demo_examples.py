"""Tests for the demo's examples: the `examples` command, the ask rule and the topic table."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from plantgraph.demo.app.answering import UnknownBenchmarkQuestion, asked_question
from plantgraph.demo.app.api_models import AskRequest
from plantgraph.demo.app.corpus_runtime import LoadedCorpus
from plantgraph.demo.app.examples import (
    read_questions,
    run_examples,
    select_per_family,
    select_variant,
    select_wordings,
)
from plantgraph.demo.app.topics import TOPIC_ORDER, topic_of
from plantgraph.qa.cascade.live_models import FreeTextQuestion
from plantgraph.qa.models import AnswerType, Question, QuestionFamily


def _question(question_id: str, family: QuestionFamily, text: str = "") -> Question:
    return Question(
        question_id=question_id, corpus_id="T", family=family, template_id="t",
        template_version="1", text=text or f"text of {question_id}",
        answer_type=AnswerType.BOOLEAN, answerable=True, reference="yes",
        evidence_tags=["P-1"], evidence_sheets=["3"], k=2, generator_seed=1,
    )  # fmt: skip


def _bank() -> list[Question]:
    """Three questions in each of two families, ids `F:0`..`F:2`."""
    families = (QuestionFamily.CONNECTED, QuestionFamily.LOOKUP_TYPE)
    return [_question(f"{f.value}:{i}", f) for f in families for i in range(3)]


def _write(path: Path, questions: list[Question]) -> Path:
    path.write_text("\n".join(q.model_dump_json() for q in questions) + "\n", encoding="utf-8")
    return path


# --- selection ---------------------------------------------------------------------------------


def test_per_family_keeps_n_of_each_family_in_file_order() -> None:
    chosen = select_per_family(_bank(), per_family=2, seed=7)

    assert len(chosen) == 4
    ids = [q.question_id for q in _bank()]
    assert [q.question_id for q in chosen] == sorted((q.question_id for q in chosen), key=ids.index)
    assert sorted(q.family.value for q in chosen) == ["CONNECTED"] * 2 + ["LOOKUP_TYPE"] * 2


def test_per_family_is_deterministic_and_depends_on_the_seed() -> None:
    same = [select_per_family(_bank(), 1, seed=5) for _ in range(2)]
    other_seeds = {
        tuple(q.question_id for q in select_per_family(_bank(), 1, s)) for s in range(20)
    }

    assert same[0] == same[1]
    assert len(other_seeds) > 1


def test_per_family_with_too_few_questions_is_an_error() -> None:
    with pytest.raises(ValueError, match="expected 4 questions of CONNECTED, found 3"):
        select_per_family(_bank(), per_family=4, seed=0)


def test_variant_keeps_only_the_suffixed_rows_and_their_gold() -> None:
    rows = [
        _question(f"Q{i}#{v}", QuestionFamily.CONNECTED) for i in range(2) for v in ("en1", "hu1")
    ]

    chosen = select_variant(rows, "hu1")

    assert [q.question_id for q in chosen] == ["Q0#hu1", "Q1#hu1"]
    assert chosen[0].reference == "yes" and chosen[0].evidence_sheets == ["3"]


def test_variant_with_no_match_is_an_error() -> None:
    with pytest.raises(ValueError, match="'#hu9'"):
        select_variant(_bank(), "hu9")


def test_wordings_replace_the_text_and_keep_the_gold() -> None:
    chosen = select_wordings(_bank(), {"LOOKUP_TYPE:1": " Milyen típusú a P-1? "})

    (only,) = chosen
    assert only.text == "Milyen típusú a P-1?"
    assert only.reference == "yes" and only.k == 2 and only.evidence_tags == ["P-1"]


def test_wordings_for_an_unknown_id_or_with_blank_text_are_errors() -> None:
    with pytest.raises(ValueError, match="known question ids"):
        select_wordings(_bank(), {"nope": "x"})
    with pytest.raises(ValueError, match="non-blank"):
        select_wordings(_bank(), {"CONNECTED:0": "  "})


def test_a_question_of_another_corpus_is_an_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "q.jsonl", _bank())

    with pytest.raises(ValueError, match="expected only corpus OTHER"):
        read_questions(path, "OTHER")


# --- the command -------------------------------------------------------------------------------


def test_the_command_writes_the_file_and_provenance_and_is_repeatable(tmp_path: Path) -> None:
    source = _write(tmp_path / "q.jsonl", _bank())
    outputs = []
    for name in ("a.jsonl", "b.jsonl"):
        out = tmp_path / name
        run_examples(["--from", str(source), "--corpus", "T", "--out", str(out),
                      "--per-family", "2", "--seed", "11"])  # fmt: skip
        outputs.append(out.read_bytes())

    assert outputs[0] == outputs[1]
    written = read_questions(tmp_path / "a.jsonl", "T")
    assert len(written) == 4 and all(q.reference == "yes" for q in written)
    provenance = json.loads((tmp_path / "a.jsonl.provenance.json").read_text(encoding="utf-8"))
    assert provenance["n_questions"] == 4 and provenance["rule"] == "per-family 2, seed 11"
    assert len(provenance["source_sha256"]) == 64


def test_the_command_refuses_to_overwrite(tmp_path: Path) -> None:
    source = _write(tmp_path / "q.jsonl", _bank())
    out = tmp_path / "out.jsonl"
    out.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_examples(["--from", str(source), "--corpus", "T", "--out", str(out),
                      "--per-family", "1"])  # fmt: skip
    assert out.read_text(encoding="utf-8") == "keep"


def test_the_command_takes_wordings_from_a_file(tmp_path: Path) -> None:
    source = _write(tmp_path / "q.jsonl", _bank())
    wordings = tmp_path / "w.json"
    wordings.write_text(json.dumps({"CONNECTED:2": "Összeköttetésben áll?"}), encoding="utf-8")
    out = tmp_path / "out.jsonl"

    run_examples(["--from", str(source), "--corpus", "T", "--out", str(out),
                  "--wordings", str(wordings)])  # fmt: skip

    (written,) = read_questions(out, "T")
    assert written.question_id == "CONNECTED:2" and written.text == "Összeköttetésben áll?"


# --- the ask rule ------------------------------------------------------------------------------


def _corpus(*questions: Question) -> LoadedCorpus:
    fake = SimpleNamespace(
        questions={q.question_id: q for q in questions},
        config=SimpleNamespace(corpus_id="T"),
    )
    return cast(LoadedCorpus, fake)


def _request(**fields: object) -> AskRequest:
    return AskRequest.model_validate({"corpus_id": "T", **fields})


def test_an_unchanged_example_runs_as_itself_with_its_stored_type() -> None:
    example = _question("E1", QuestionFamily.CONNECTED, "Is A connected to B?")

    asked = asked_question(
        _corpus(example), _request(example_id="E1", text=" Is A connected to B? ")
    )

    assert asked is example and example.answer_type is AnswerType.BOOLEAN


def test_an_edited_example_becomes_free_text() -> None:
    example = _question("E1", QuestionFamily.CONNECTED, "Is A connected to B?")

    asked = asked_question(_corpus(example), _request(example_id="E1", text="Is A joined to B?"))

    assert isinstance(asked, FreeTextQuestion)
    assert asked.answer_type is AnswerType.FREE_TEXT and asked.text == "Is A joined to B?"


def test_typed_text_and_an_unknown_id_with_text_are_free_text() -> None:
    corpus = _corpus(_question("E1", QuestionFamily.CONNECTED))

    typed = asked_question(corpus, _request(text="anything"))
    unknown = asked_question(corpus, _request(example_id="nope", text="anything"))

    assert isinstance(typed, FreeTextQuestion) and isinstance(unknown, FreeTextQuestion)
    assert typed.answer_type is AnswerType.FREE_TEXT


def test_the_old_page_shape_still_works() -> None:
    example = _question("E1", QuestionFamily.CONNECTED)
    request = _request(benchmark_question_id="E1")  # no text, old field name

    assert asked_question(_corpus(example), request) is example
    with pytest.raises(UnknownBenchmarkQuestion):
        asked_question(_corpus(example), _request(benchmark_question_id="nope"))


def test_a_request_with_neither_text_nor_example_is_rejected() -> None:
    with pytest.raises(ValueError, match="neither"):
        _request(text="  ")


def test_the_request_no_longer_has_an_answer_type() -> None:
    assert "answer_type" not in AskRequest.model_fields
    assert _request(text="x", answer_type="BOOLEAN").text == "x"  # old page's extra key is ignored


# --- topics ------------------------------------------------------------------------------------


def test_every_family_has_one_of_the_four_topics() -> None:
    for family in QuestionFamily:
        assert topic_of(family) in TOPIC_ORDER
