"""The `cypher_rag_plant` arm and the store-profile checks (ADR-0036, MP-T4); fully offline."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.cypher_setup import check_store_profile, required_cypher_profile
from plantgraph.qa.harness.registry import CypherDeps, build_strategy
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import QuestionResult
from plantgraph.qa.neo4j_view import _HIDDEN_PROPERTIES, StoreMismatch
from plantgraph.qa.primer import primer_text
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.qa.strategies.cypher_rag import CypherRag, render_cypher_request
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.plant_rows import StoreProfile
from qa_cypher_corpus import four_unit_corpus, load_plan_of
from qa_harness_toy import CORPUS_ID, Toy, build_toy, make_config, pin

_ANSWER = '{"answer": "Pump", "not_present": false}'
_PARAMS = {"timeout_s": 5, "row_cap": 3}

#: sha256 of the whole `cypher_rag` prompt (occurrence schema text of the 4-unit corpus, question
#: "Q?"), taken before the plant arm existed: the plain arm's prompt must not drift.
_OCCURRENCE_PROMPT_SHA256 = {
    False: "e0742ea70f3618eea4925b5047345564f35e651413f478f5ad739044139574fc",
    True: "3d12e704124dd6578cebc33eb11cd19f35ac1423fcd4d753dfa6be01fea0132a",
}


class _Source:
    def __init__(self, schema: str = "SCH") -> None:
        self._schema = schema
        self.closed = False

    def corpus_id(self) -> str:
        return "stub"

    def schema_text(self) -> str:
        return self._schema

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[{"tag": "X"}], truncated=False)

    def close(self) -> None:
        self.closed = True


def _never_called(request: ChatRequest) -> ChatResponse:
    raise AssertionError("no model call expected")


def _capturing_send(sent: list[ChatRequest]) -> SendChatRequest:
    def send(request: ChatRequest) -> ChatResponse:
        sent.append(request)
        return ChatResponse(
            text="MATCH (n) RETURN n",
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.0,
            latency_s=0.0,
            provider_response_id="x",
            finish_reason="stop",
            from_cache=False,
            created_at=datetime(2026, 10, 4),
        )

    return send


@pytest.mark.parametrize("primer", [False, True])
def test_the_occurrence_arm_prompt_is_byte_identical_to_before(primer: bool) -> None:
    text = build_schema_text(load_plan_of(four_unit_corpus(), "pytest-golden"))
    request = render_cypher_request(pin=pin(), schema_text=text, question_text="Q?", primer=primer)

    digest = hashlib.sha256(request.messages[0].content.encode()).hexdigest()
    assert digest == _OCCURRENCE_PROMPT_SHA256[primer]


def test_the_plant_arm_has_its_own_name_and_the_plain_arm_keeps_its_own() -> None:
    plant = CypherRag(_Source(), pin(), _never_called, timeout_s=1.0, row_cap=1, profile="plant")
    plain = CypherRag(_Source(), pin(), _never_called, timeout_s=1.0, row_cap=1)

    assert (plant.name, plant.profile) == ("cypher_rag_plant", "plant")
    assert (plain.name, plain.profile) == ("cypher_rag", "occurrence")
    assert CypherRag.name == "cypher_rag"


def test_the_registry_builds_the_plant_arm_and_names_it_in_its_errors() -> None:
    corpus = four_unit_corpus()
    view = NetworkxGraphView("c", corpus.localized_sheets, corpus.resolution)
    deps = CypherDeps(_Source(), pin(), _never_called)

    strategy = build_strategy("cypher_rag_plant", _PARAMS, view, deps)
    assert strategy.name == "cypher_rag_plant"
    with pytest.raises(ValueError, match="database connection for cypher_rag_plant"):
        build_strategy("cypher_rag_plant", _PARAMS, view, None)
    with pytest.raises(ValueError, match=r"cypher_rag_plant params to include \['row_cap'\]"):
        build_strategy("cypher_rag_plant", {"timeout_s": 5}, view, deps)


@pytest.mark.parametrize("primer", [True, False])
def test_the_plant_arm_sends_the_primer_only_when_asked(primer: bool) -> None:
    sent: list[ChatRequest] = []
    strategy = CypherRag(
        _Source("PLANT-SCHEMA"),
        pin(),
        _capturing_send(sent),
        timeout_s=5.0,
        row_cap=3,
        primer=primer,
        profile="plant",
    )
    strategy.retrieve("QTXT")

    prompt = sent[0].messages[0].content
    assert (primer_text() in prompt) is primer
    assert "PLANT-SCHEMA" in prompt and "QTXT" in prompt


# --- the store-profile checks --------------------------------------------------------------


def test_one_cypher_arm_per_run() -> None:
    assert required_cypher_profile(["context_rag"]) is None
    assert required_cypher_profile(["context_rag", "cypher_rag"]) == "occurrence"
    assert required_cypher_profile(["cypher_rag_plant"]) == "plant"
    with pytest.raises(ValueError, match="one Cypher arm per run.*--store-profile plant"):
        required_cypher_profile(["cypher_rag", "cypher_rag_plant"])


@pytest.mark.parametrize("stored", ["occurrence", "plant", "both"])
def test_the_store_profile_must_equal_the_one_the_arm_reads(stored: StoreProfile) -> None:
    plan = load_plan_of(four_unit_corpus(), "pytest-profile", profile=stored)

    for required in ("occurrence", "plant"):
        if stored == required:
            check_store_profile(plan, required)
            continue
        with pytest.raises(StoreMismatch, match=f"--store-profile {required}"):
            check_store_profile(plan, required)


def test_via_connector_uids_is_hidden_from_returned_properties() -> None:
    assert "via_connector_uids" in _HIDDEN_PROPERTIES


# --- through the harness -------------------------------------------------------------------


@pytest.fixture(scope="module")
def plant_toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("plant-toy"), store_profile="plant")


def _run(toy: Toy, tmp_path: Path, strategies: dict[str, dict[str, int]], factory: object) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text=_ANSWER))
    run_harness(
        config=make_config(toy, strategies=strategies, allow_paid_calls=True),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
        cypher_source_factory=factory,  # type: ignore[arg-type]
    )


def test_the_harness_runs_the_plant_arm_on_a_plant_store(plant_toy: Toy, tmp_path: Path) -> None:
    source = _Source()
    profiles: list[str] = []

    def factory(plan: LoadPlan) -> _Source:
        profiles.append(plan.profile)
        return source

    _run(plant_toy, tmp_path, {"cypher_rag_plant": _PARAMS}, factory)

    assert profiles == ["plant"] and source.closed
    path = tmp_path / "runs" / "toy" / "answers.jsonl"
    rows = [QuestionResult.model_validate_json(x) for x in path.read_text("utf-8").splitlines()]
    assert rows and all(row.strategy == "cypher_rag_plant" for row in rows)


def test_the_plain_arm_on_a_plant_store_is_refused_before_any_run(
    plant_toy: Toy, tmp_path: Path
) -> None:
    def never(plan: LoadPlan) -> _Source:
        raise AssertionError("the database must not be opened for a wrong profile")

    with pytest.raises(StoreMismatch, match="'occurrence' for cypher_rag, found 'plant'"):
        _run(plant_toy, tmp_path, {"cypher_rag": _PARAMS}, never)

    assert not (tmp_path / "runs" / "toy").exists()  # not even frozen


def test_naming_both_cypher_arms_is_refused_before_the_freeze(
    plant_toy: Toy, tmp_path: Path
) -> None:
    both = {"cypher_rag": _PARAMS, "cypher_rag_plant": _PARAMS}

    with pytest.raises(ValueError, match="one Cypher arm per run"):
        _run(plant_toy, tmp_path, both, lambda plan: _Source())

    assert not (tmp_path / "runs" / "toy").exists()
