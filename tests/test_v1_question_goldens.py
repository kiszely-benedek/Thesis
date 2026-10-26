"""v1 question sets stay byte-identical after the v2 question-family fixes (design vocab 7.4).

Every candidate question of the 18 dev and 6 held-out families, drawn from the committed v1
corpus D100 (`data/runs/cv1/corpora/D100/ingest.json`, seed 1), is hashed per family. The
constants were recorded from the code *before* the v2 fixes (loop filter, absent-tag grammar,
path items, layer ranking); the same check also held on H100 and D1000 at that time. If one
fails, a change altered a v1 question: fix the change, never the constant.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.questions.families_heldout import heldout_candidates

D100_INGEST = Path(__file__).resolve().parent.parent / "data/runs/cv1/corpora/D100/ingest.json"

#: family -> (number of candidates, sha256 of their JSON lines)
_GOLDEN: dict[str, tuple[int, str]] = {
    "CONNECTED": (2789, "97557cf1bd8f514a8c9d6acd5bd40f4f40b7c3e93df4a85913598fd8c10bb372"),
    "COUNT_IN_UNIT": (464, "26e5d87229cae71373d5bde7eede7ab475976e83b2e16c2df07656902d1800f3"),
    "CROSS_UNIT": (27, "22729088ab943d421a29a4447e966140721a077fba74ae1ef9e9c2c3a4645c19"),
    "DOWNSTREAM_IN_UNIT": (766, "31c5f4f8e8c7a50406e931170c32ba2ca666b21113e050eac6bc8766f30c55b7"),
    "DOWNSTREAM_ISOLATION": (
        357,
        "fe08e31ecafe36a5fe4560de57c802ab8743df6da04490cc8435cb83cb854003",
    ),
    "FEEDING_UNITS": (51, "00102dd93d0cfc000f13979aa06eb1d9b2c32b55b98e792d4a5733528f98cf89"),
    "FIRST_MEETING_POINT": (
        325,
        "d8a7bd80024389d7c926c587026f3506ec46de037f0fae6ba47e7ae7c11cd284",
    ),
    "FLOW_PATH": (3475, "149d74f7bb4754ab1a44abfd0de80be6ebfcb1fd9d10937f6e1124f1d54a5ea1"),
    "INSTRUMENTS_OF_ITEM": (
        272,
        "320a4efe9a83252b60ffa849a8050a7dbfdb3a168a4ea934f41ff701b22515bb",
    ),
    "LOOKUP_TYPE": (3440, "970d794224c32a015b66a0996cd75c6495aaebe2d576b7e67d0f9d843957a686"),
    "LOOKUP_UNIT": (3440, "2ab9eab3444a97f4c9eb30f2c2b6aef16fe45f26574103de44f1eaa0815de73c"),
    "LOOPS_NEAR_ITEM": (374, "f993dd1ef96e40cac43ad6baba5a43b1ac663f0f80b047be4bf47c79487a3617"),
    "LOOP_ACTUATED_VALVE": (
        272,
        "61826b56545cd1f85cf4bfb4d46d4cc5959141403886360330685e067236a18b",
    ),
    "LOOP_MEASURED_EQUIPMENT": (
        272,
        "1d28c960b678c4fc353685a9954b33ee6ad118885d4ee60b5ab10ae70fa9835c",
    ),
    "NEIGHBOURS_DOWNSTREAM": (
        2225,
        "640af7a7e617d94aa1a114bd22723480d11e40a7424372cb2506d913eb365b4a",
    ),
    "NO_PATH": (4326, "b4c2b6587044c7b4c7a2b7ec71288acfc48f8f32c6935cc1e6a17c42e96296dd"),
    "ROUTE_AVOIDING": (1242, "a67929fb17b3e2774f1db3fb735c4001f9c54c4a1f42ba057699aa1d49a9bfc3"),
    "SAME_UNIT": (2886, "10e89591e38e43962d5dd07e4ebcfeeb18d6b6e60c81fb8f92054dc333539be4"),
    "SHEETS_OF_TAG": (124, "b88ecb549348420803c15d1b9bbe832e304168bd804e0d035975e227ec93fa99"),
    "UNANSWERABLE_TAG": (1875, "6f22728489edce9b526b3af308b24847041ba50ec1e94cc05fbce0722b0d56c8"),
    "UNITS_REACHED": (772, "5f3f4edaf4791fe6da728ee169be2109b2ab04c76909deeeef401364aff49177"),
    "UPSTREAM_ISOLATION": (
        1441,
        "4a1e381a2ce7e5c28993f3765c7aeb334df9e73db0e35277811cb4835c649d8d",
    ),
    "UPSTREAM_SOURCES": (1442, "5fcc52aba94b045a13fbac5c16ad7ffbb4d1c474f4571d38e24ed5c672749d10"),
    "VALVES_ON_PATH": (1347, "70b6861bb9033f6385702ee5fcbbb1c4b3fe2a36f24059115e72f5c67793e2cf"),
}


def test_every_v1_question_family_is_byte_identical_on_d100() -> None:
    gold = load_corpus_artifacts("D100", D100_INGEST).gold
    arguments = (gold.plant, gold.manifest, gold.sheets)
    drawn = {
        **all_candidates(*arguments, corpus_id="D100", seed=1),
        **heldout_candidates(*arguments, corpus_id="D100", seed=1),
    }
    found = {}
    for family, questions in drawn.items():
        blob = "".join(question.model_dump_json() + "\n" for question in questions)
        found[family.value] = (len(questions), hashlib.sha256(blob.encode()).hexdigest())
    assert found == _GOLDEN
