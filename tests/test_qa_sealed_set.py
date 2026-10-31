"""The sealed question set: pool opt-in, held-out wordings, per-family draw, splits, CLI."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import qa_toy_plant_dev2
import qa_toy_plant_heldout
from plantgraph.ingest.headline_v2 import TEST_SEEDS_V2, headline_corpus_id_v2
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions import sealed_set
from plantgraph.qa.questions.availability import AvailabilityReport, BinTargets, KBin
from plantgraph.qa.questions.families import FAMILY_CANDIDATE_GENERATORS, all_candidates
from plantgraph.qa.questions.families_heldout import HELDOUT_GENERATORS
from plantgraph.qa.questions.sealed_set import (
    WORDING_SPLIT,
    build_availability,
    build_pool_from_plant,
    find_dropped_families,
    require_test_corpus,
    sample_sealed_set,
    write_sealed_set,
)
from plantgraph.qa.questions.wordings_heldout import WORDING_FAMILIES, reword

F = QuestionFamily
_PLANT = qa_toy_plant_heldout.build_plant()
_MANIFEST = qa_toy_plant_heldout.build_manifest()
_SHEETS = qa_toy_plant_heldout.build_sheets(_PLANT)
_TARGETS = BinTargets(per_bin=50, unanswerable=5)


def _pool() -> tuple[list[Question], AvailabilityReport]:
    return build_pool_from_plant(_PLANT, _MANIFEST, _SHEETS, _TARGETS, corpus_id="H0", seed=31)


# --- the opt-in ------------------------------------------------------------------------------


def test_the_default_registry_has_no_heldout_family() -> None:
    assert set(FAMILY_CANDIDATE_GENERATORS).isdisjoint(HELDOUT_GENERATORS)
    plant = qa_toy_plant_dev2.build_plant()
    default = all_candidates(
        plant,
        qa_toy_plant_dev2.build_manifest(),
        qa_toy_plant_dev2.build_sheets(plant),
        corpus_id="t",
        seed=0,
    )
    assert set(default) == set(FAMILY_CANDIDATE_GENERATORS)


def test_the_pool_holds_every_heldout_family() -> None:
    pool, report = _pool()

    assert {q.family for q in pool} >= set(HELDOUT_GENERATORS)
    for family in HELDOUT_GENERATORS:  # every k-bin is listed, zeros included
        assert set(report.candidates[family]) == set(KBin)


@pytest.mark.parametrize(
    "corpus_id",
    [
        "H100",
        "H1000",
        "H1g2",
        "H3g2",
        "H10g2",
        "H30g2",
        "H100g2",
        "H100g2d0",
        "H100g2d50",
        "H1000g2",
    ],
)
def test_a_test_corpus_is_accepted(corpus_id: str) -> None:
    require_test_corpus(corpus_id)


def test_every_registered_v2_test_corpus_id_is_accepted() -> None:
    """The ids `headline_corpus_id_v2` gives the registered test seeds all pass the check."""
    for sheets, seed in TEST_SEEDS_V2.items():
        require_test_corpus(headline_corpus_id_v2(sheets, seed))
    for rate in (0.0, 0.5):
        require_test_corpus(headline_corpus_id_v2(100, TEST_SEEDS_V2[100], rate))


@pytest.mark.parametrize(
    "corpus_id",
    [
        "D100",
        "D1000",
        "toy",
        "H",
        "XH100",
        "D100g2",
        "X100g2s2",
        "H100g2s2",
        "Hg2",
        "H100g2d",
        "H100d50",
    ],
)
def test_anything_but_a_test_corpus_is_refused(corpus_id: str) -> None:
    with pytest.raises(ValueError, match="test corpus"):
        require_test_corpus(corpus_id)


# --- held-out wordings -----------------------------------------------------------------------


def _hand_made_sheets_of_tag() -> Question:
    return Question(
        question_id="H0:SHEETS_OF_TAG:P-7",
        corpus_id="H0",
        family=F.SHEETS_OF_TAG,
        template_id="SHEETS_OF_TAG",
        template_version="1",
        text="On which sheets is P-7 drawn?",
        answer_type=AnswerType.SHEET_SET,
        answerable=True,
        reference=["S1", "S2"],
        k=1,
        anchors=["P-7"],
        generator_seed=0,
    )


def _wording_sources() -> dict[QuestionFamily, Question]:
    plant = qa_toy_plant_dev2.build_plant()
    candidates = all_candidates(
        plant,
        qa_toy_plant_dev2.build_manifest(),
        qa_toy_plant_dev2.build_sheets(plant),
        corpus_id="H0",
        seed=0,
    )
    sources = {f: candidates[f][0] for f in WORDING_FAMILIES if candidates[f]}
    sources[F.SHEETS_OF_TAG] = _hand_made_sheets_of_tag()  # needs a duplicated drawing
    return sources


def test_every_wording_keeps_its_source_and_carries_its_template_id() -> None:
    sources = _wording_sources()
    assert set(sources) == set(WORDING_FAMILIES) and len(WORDING_FAMILIES) == 10

    for family, source in sources.items():
        wording = reword(source)
        anchors = "|".join(source.anchors)
        assert wording.template_id == source.template_id + "_P1", family
        assert wording.question_id == f"H0:{family.value}:{wording.template_id}:{anchors}"
        assert wording.question_id != source.question_id
        assert wording.text != source.text
        unchanged = {"text", "template_id", "question_id"}
        assert wording.model_dump(exclude=unchanged) == source.model_dump(exclude=unchanged)


def test_wordings_read_as_the_design_table_says() -> None:
    sources = _wording_sources()
    text = {f: reword(q).text for f, q in sources.items()}
    tag = sources[F.LOOKUP_TYPE].anchors[0]
    loop_tag = sources[F.LOOP_ACTUATED_VALVE].anchors[0]
    unit = sources[F.CROSS_UNIT].anchors[0]

    assert text[F.LOOKUP_TYPE] == f"{tag}: what kind of equipment or component is it?"
    assert text[F.LOOKUP_UNIT] == f"{tag} belongs to which plant section?"
    assert text[F.NEIGHBOURS_DOWNSTREAM].startswith("Name every item that is fed directly by ")
    assert text[F.LOOP_ACTUATED_VALVE] == f"Control loop {loop_tag} drives which valve?"
    assert text[F.LOOP_MEASURED_EQUIPMENT].startswith("The sensor of loop ")
    assert text[F.FLOW_PATH].startswith("List, in flow order, the equipment and valves")
    assert text[F.UPSTREAM_ISOLATION].startswith("Before maintenance on ")
    assert text[F.SHEETS_OF_TAG] == "P-7 appears on which drawing sheets?"
    # unit anchors keep the literal word "unit" in front of the id
    assert text[F.CROSS_UNIT] == f"Unit {unit} passes material straight on to which other units?"
    assert text[F.COUNT_IN_UNIT].startswith("What is the number of ")
    assert " belonging to unit " in text[F.COUNT_IN_UNIT]


def test_a_family_without_a_wording_is_refused() -> None:
    other = _hand_made_sheets_of_tag().model_copy(update={"family": F.CONNECTED})

    with pytest.raises(ValueError, match="held-out wording"):
        reword(other)


# --- the draw --------------------------------------------------------------------------------


def test_each_question_is_in_exactly_one_split_and_ids_are_unique() -> None:
    pool, _ = _pool()

    sealed = sample_sealed_set(pool, 3, 2, sample_seed=7)

    ids = [q.question_id for q in sealed.questions]
    assert len(set(ids)) == len(ids)
    assert list(sealed.splits) == ids  # same ids, same order, nothing missing or extra
    assert set(sealed.splits.values()) <= {"dev-old", "dev-new", "held-out", WORDING_SPLIT}
    for family in HELDOUT_GENERATORS:
        drawn = [
            q
            for q in sealed.questions
            if q.family is family and sealed.splits[q.question_id] == "held-out"
        ]
        assert 0 < len(drawn) <= 3, family


def test_wordings_are_marked_and_are_the_same_items_as_the_dev_draw() -> None:
    pool, _ = _pool()

    sealed = sample_sealed_set(pool, 4, 2, sample_seed=7)

    is_wording = {
        q.question_id: sealed.splits[q.question_id] == WORDING_SPLIT for q in sealed.questions
    }
    wordings = [q for q in sealed.questions if is_wording[q.question_id]]
    dev_ids = {q_id for q_id, flag in is_wording.items() if not flag}
    assert wordings and all(q.template_id.endswith("_P1") for q in wordings)
    for wording in wordings:
        assert wording.question_id.replace(f":{wording.template_id}", "") in dev_ids


def test_families_without_candidates_are_dropped_with_a_reason() -> None:
    pool, _ = _pool()

    dropped = find_dropped_families(pool)

    assert F.LOOP_ACTUATED_VALVE in dropped  # the heldout toy has no control loops
    assert "no candidate" in dropped[F.LOOP_ACTUATED_VALVE]
    assert not set(dropped) & set(HELDOUT_GENERATORS)


def test_v2_drops_first_meeting_point_with_the_pre_registered_reason() -> None:
    pool, _ = _pool()
    pool = [q for q in pool if q.family is not F.FIRST_MEETING_POINT]  # a v2 pool never holds it

    on_v2 = find_dropped_families(pool, v2=True)
    on_v1 = find_dropped_families(pool)

    assert on_v2[F.FIRST_MEETING_POINT] == "excluded on v2 by pre-registration"
    assert "no candidate" in on_v1[F.FIRST_MEETING_POINT]


def test_a_heldout_reference_that_does_not_score_drops_its_family() -> None:
    pool, _ = _pool()
    broken = next(q for q in pool if q.family is F.UNITS_REACHED).model_copy(
        update={"reference": "not a number"}
    )
    pool = [broken, *(q for q in pool if q.family is not F.UNITS_REACHED)]

    dropped = find_dropped_families(pool)

    assert "does not score" in dropped[F.UNITS_REACHED]


def test_a_non_positive_count_is_refused() -> None:
    pool, _ = _pool()

    with pytest.raises(ValueError, match="positive"):
        sample_sealed_set(pool, 0, 2, sample_seed=1)
    with pytest.raises(ValueError, match="positive"):
        sample_sealed_set(pool, 2, 0, sample_seed=1)


# --- files and the command line --------------------------------------------------------------


def _write(out: Path) -> dict[str, bytes]:
    pool, report = _pool()
    sealed = sample_sealed_set(pool, 3, 2, sample_seed=7)
    availability = build_availability(
        sealed, report, n_per_family=3, n_per_wording=2, sample_seed=7
    )
    write_sealed_set(out, sealed, availability)
    return {p.name: p.read_bytes() for p in sorted(out.iterdir())}


def test_the_same_seeds_give_byte_identical_files(tmp_path: Path) -> None:
    first, second = _write(tmp_path / "a"), _write(tmp_path / "b")

    assert set(first) == {"questions.jsonl", "splits.json", "availability.json"}
    assert first == second
    assert b"\r" not in first["questions.jsonl"]


def test_availability_counts_what_was_drawn() -> None:
    pool, report = _pool()
    sealed = sample_sealed_set(pool, 3, 2, sample_seed=7)

    availability = build_availability(
        sealed, report, n_per_family=3, n_per_wording=2, sample_seed=7
    )

    assert sum(availability.drawn_per_split.values()) == len(sealed.questions)
    assert (
        sum(availability.drawn_per_wording.values()) == availability.drawn_per_split[WORDING_SPLIT]
    )
    assert set(availability.drawn_per_family) >= set(HELDOUT_GENERATORS)
    assert set(availability.dropped) == set(sealed.dropped)


def test_the_command_writes_pool_and_set_and_refuses_a_dev_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gold = SimpleNamespace(plant=_PLANT, manifest=_MANIFEST, sheets=_SHEETS)
    monkeypatch.setattr(
        sealed_set,
        "load_corpus_artifacts",
        lambda corpus_id, _path: SimpleNamespace(
            corpus_id=corpus_id, gold=gold, generator_config=None
        ),
    )
    out, pool_out = str(tmp_path / "set"), str(tmp_path / "pool")
    args = ["--ingest-json", "unused.json", "--seed", "31", "--n-per-bin", "50"]
    args += ["--n-unanswerable", "5", "--n-per-family", "3", "--n-per-wording", "2"]
    args += ["--sample-seed", "7", "--out", out, "--pool-out", pool_out]

    sealed_set.main(["--corpus-id", "H0", *args])

    splits = json.loads((tmp_path / "set" / "splits.json").read_text(encoding="utf-8"))
    lines = (tmp_path / "set" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(splits) == sorted(json.loads(line)["question_id"] for line in lines)
    assert (tmp_path / "pool" / "questions.jsonl").exists()
    with pytest.raises(ValueError, match="test corpus"):
        sealed_set.main(["--corpus-id", "D100", *args])
