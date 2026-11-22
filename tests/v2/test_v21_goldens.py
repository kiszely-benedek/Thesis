"""Goldens that freeze the v2.1 generator while v2.2 is built (design generator-v2-2 section 9).

Every digest was recorded at HEAD `ea5c360`, before any v2.2 code existed. They cover: the pyDEXPI
JSON and the hidden generation record of seeds 1-5 at about 30 sheets; the same for the stored
EXP-0008 configs; the config JSON itself; and the H1g21 ladder question set. If one fails, a change
altered a v2.1 corpus: fix the change, never the constant.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydexpi.loaders.json_serializer import JsonSerializer

from plantgraph.benchmark.v2 import v21_pins
from plantgraph.benchmark.v2.class_decks import PURGE_METER_ROLE, role_deck_variants
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.patterns.variants import pattern_deck_variants
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.qa.questions import per_family, sealed_set

_EXP0008 = Path(__file__).resolve().parents[2] / "data" / "runs" / "exp0008"
_needs_exp0008 = pytest.mark.skipif(not _EXP0008.exists(), reason="data/runs/exp0008 is absent")

#: seed -> (n_units giving about 30 sheets with the headline preset, DEXPI JSON sha, record sha)
_GOLDEN_SEEDS = {
    1: (17, "dd4a6f2fd57f905fdad3ed267fec1da482208c429febbf2fa2c2c3eb48c3302a",
        "6d526c8d6ca8fa98302c980c1aa00c0924d549977783caeca61f94f869d2fa6c"),
    2: (16, "f8621ddd36077b395c575f3834cc545baedb80c91fabf787345ee832f705a753",
        "a31aaa29033a343586cf6e4e7aec6beaf2eaa02f57a2710e43d02c27ac08423a"),
    3: (19, "b8fba3ffb27320a1c8f6897859f6ece5a2323f57e2ce3261473b5f43641c9a82",
        "49e9ccdb26e7186484988cb084f72ad4eb1131cbd748711f8719b6fbdaba7c56"),
    4: (18, "c8a05b438e48975a3211f646909c688a8cd79451cdf8dc3605b916dd464a0685",
        "121dc89c46ccaa8c2237608569aa524e22a7140ffbba28e2dba028d9b55666b4"),
    5: (20, "71d339a47125064139afc7a09e089e255b8e01b25a5ca30d306434f8067b15d9",
        "29a4ba7c80b11e3a044190294950bfaa7fe81400deb4e808bd3aed91da262a03"),
}  # fmt: skip
#: stored EXP-0008 corpus -> (DEXPI JSON sha, record sha) of the plant its stored config builds
_GOLDEN_STORED = {
    "H1g21": ("df67d7b7a42c7cf966ad49ccd120d7d575e02eedaf810da04e0ce7fc3d16f881",
              "ff7f4cb05d5f25d5eb3ffd737278748b2986597cec1a645e9872e1f76a8d5a1b"),
    "H3g21": ("782a8c1019d120e931ffc4d089f8d21ffc62077472ba759320e89a1a457645b1",
              "95f80334c5011621a73e7d4f4fa28b528aa537d39182dff5f3cee204b70def15"),
    "H10g21": ("a73bad729a76656df867da8f6e416720b875c6e38ca04660b0f5e7d0764dddb5",
               "e43776631a35f9b077617c132b2e365d5e4ef952364a609bd001d0211d3dd5f6"),
    "D100g21": ("5d7c91ed446a2fdaa01934e027ffe34a7d6bd261d58a43263efb12f702c88a8d",
                "de3c4a9bbb670f5b3ed9b6481ce48fa80f73dcc8d31b98a344c7e85dc40d4c59"),
}  # fmt: skip
#: sha256 of `GeneratorConfigV2(seed=1, n_units=5).model_dump_json()`: v2.1 config JSON is frozen
_GOLDEN_CONFIG_JSON = "2e2ef501d6caa166e2e47942bf838d885b65ec8e03cf764c8ad31f12e1ef600a"
#: sha256 of the H1g21 ladder `questions.jsonl` (also recorded in exp0008/T9.sha256)
_GOLDEN_H1G21_QUESTIONS = "8d27807b96d335a4c30d8a0c9d525d061965635a679ef1dfadb5dd898dffcee8"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plant_digests(config: GeneratorConfigV2) -> tuple[str, str]:
    """sha256 of the pyDEXPI JSON bytes and of the hidden generation record of a generated plant."""
    plant = generate_plant_v2(config)
    dexpi_json = JsonSerializer().export_to_bytes(plant.model)
    return _sha256(dexpi_json), _sha256(plant.record.model_dump_json().encode())


def _stored_generator_block(corpus_id: str) -> dict[str, object]:
    path = _EXP0008 / "corpora" / corpus_id / "ingest.json"
    return json.loads(path.read_text(encoding="utf-8"))["config"]["generator"]


@pytest.mark.parametrize("seed", sorted(_GOLDEN_SEEDS))
def test_the_plant_of_a_headline_config_is_unchanged(seed: int) -> None:
    n_units, dexpi_digest, record_digest = _GOLDEN_SEEDS[seed]
    config = HeadlinePresetV2().generator_config(n_units, seed)
    assert _plant_digests(config) == (dexpi_digest, record_digest)


@_needs_exp0008
@pytest.mark.parametrize("corpus_id", sorted(_GOLDEN_STORED))
def test_the_plant_of_a_stored_exp0008_config_is_unchanged(corpus_id: str) -> None:
    config = GeneratorConfigV2.model_validate(_stored_generator_block(corpus_id))
    assert _plant_digests(config) == _GOLDEN_STORED[corpus_id]


@_needs_exp0008
@pytest.mark.parametrize("corpus_id", sorted(_GOLDEN_STORED))
def test_a_stored_exp0008_config_reads_back_to_the_same_json(corpus_id: str) -> None:
    """No `GeneratorConfigV2` field was added, dropped or reordered since the config was stored."""
    stored = _stored_generator_block(corpus_id)
    assert GeneratorConfigV2.model_validate(stored).model_dump(mode="json") == stored


def test_the_json_of_a_v21_config_is_unchanged() -> None:
    config_json = GeneratorConfigV2(seed=1, n_units=5).model_dump_json()
    assert _sha256(config_json.encode()) == _GOLDEN_CONFIG_JSON


@_needs_exp0008
def test_the_h1g21_ladder_question_set_is_unchanged(tmp_path: Path) -> None:
    """Rebuild the set with the ladder recipe of `stages/m4_test_plants.sh` and hash the bytes."""
    ingest_json = str(_EXP0008 / "corpora" / "H1g21" / "ingest.json")
    full, pool, picked = tmp_path / "full", tmp_path / "pool", tmp_path / "picked"
    sealed_set.main(
        ["--corpus-id", "H1g21", "--ingest-json", ingest_json, "--seed", "41",
         "--n-per-bin", "500", "--n-unanswerable", "100", "--n-per-family", "20",
         "--n-per-wording", "1", "--sample-seed", "20261101",
         "--out", str(full), "--pool-out", str(pool)]
    )  # fmt: skip
    per_family.main(
        ["--in", str(full / "questions.jsonl"), "--splits", str(full / "splits.json"),
         "--only-splits", "dev-old,dev-new,held-out", "--n", "4", "--seed", "20261101",
         "--out", str(picked)]
    )  # fmt: skip
    assert _sha256((picked / "questions.jsonl").read_bytes()) == _GOLDEN_H1G21_QUESTIONS


# ---- the V21_* pins ----------------------------------------------------------------------------


def _expand(cards: dict[str, int]) -> tuple[str, ...]:
    return tuple(card for card, copies in cards.items() for _ in range(copies))


def test_the_role_decks_are_dealt_from_the_pins() -> None:
    decks = role_deck_variants()
    for role, cards in v21_pins.V21_ROLE_CLASSES.items():
        assert decks[f"role:{role}"] == _expand(dict(cards)), role
    assert decks[f"role:{PURGE_METER_ROLE}"] == v21_pins.V21_PURGE_METER_DECK


def test_the_pattern_decks_are_dealt_from_the_pins() -> None:
    decks = pattern_deck_variants()
    for key, cards in v21_pins.V21_PATTERN_DECKS.items():
        assert decks[key] == _expand(dict(cards)), key


def test_the_pins_cannot_be_edited_in_place() -> None:
    with pytest.raises(TypeError):
        v21_pins.V21_ROLE_CLASSES["block_valve"]["GateValve"] = 3  # type: ignore[index]
    with pytest.raises(TypeError):
        v21_pins.V21_PATTERN_DECKS["new_axis"] = {}  # type: ignore[index]


def test_the_convention_pins_match_the_enums_and_weights_of_v21() -> None:
    from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming

    assert v21_pins.V21_ON_OFF_LETTERS == tuple(member.value for member in OnOffLetter)
    assert v21_pins.V21_SPARE_NAMINGS == tuple(member.value for member in SpareNaming)
    assert v21_pins.V21_ON_OFF_LETTER_WEIGHTS == (1, 1)
    assert v21_pins.V21_SPARE_NAMING_WEIGHTS == (3, 2)
