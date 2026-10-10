"""The P&ID reading primer: the file, the template slot, the off-is-unchanged golden, the legends.

All offline: prompts are rendered and compared as strings, no model is called.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.qa.context_render import legend_text
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.final_answer import render_final_answer_request
from plantgraph.qa.harness.freeze import prompt_hashes
from plantgraph.qa.models import AnswerType, RunConfig
from plantgraph.qa.primer import fill_primer_slot, primer_block, primer_text
from plantgraph.qa.strategies.cypher_rag import CypherRag, render_cypher_request
from qa_harness_toy import pin

_PROMPTS_DIR = Path(__file__).parents[1] / "src" / "plantgraph" / "qa" / "prompts"

# What the two templates rendered before the `<<PRIMER>>` slot existed, for fixed inputs.
_GOLDEN_FINAL_ANSWER = (
    "You are answering a question about one plant's piping and instrumentation diagram (P&ID) "
    "— the engineering drawing that shows a plant's pipes, equipment and instruments, and "
    "how they connect. Below is a machine-readable description of that diagram, not a picture "
    "of it.\n\n"
    "Answer using only that description. If it does not contain the answer, do not guess "
    "— say so instead of inventing one.\n\n"
    "Context:\nCTX\n\nQuestion:\nQTXT\n\nAnswer with a single integer.\n\n"
    "Reply with exactly one JSON object of this shape, and nothing else — no explanation, "
    "no markdown fence, no extra keys:\n"
    '{"answer": <your answer, or null if not_present is true>, "not_present": <true if the '
    "description does not contain the answer, otherwise false>}\n"
)
_GOLDEN_CYPHER_QUERY = (
    "You are writing a database query about one plant's piping and instrumentation diagram "
    "(P&ID) — the engineering drawing that shows a plant's pipes, equipment and "
    "instruments, and how they connect. The diagram is stored as a graph in a Neo4j "
    "database.\n\n"
    "Database schema:\nSCH\n\n"
    "Domain note: a control loop is identified by its controller (loop) tag, for example "
    "TIC-49-1. The control valve it actuates is a separate item with its own tag, for example "
    "TV-49-1. Answer a question about loops with loop tags and a question about valves with "
    "valve tags; do not return both unless the question asks for both.\n\n"
    "Question:\nQTXT\n\n"
    "Write exactly one read-only Cypher query whose result rows contain what is needed to "
    "answer the question. Return tags (the tag property), not internal identifiers. Do not "
    "use CREATE, MERGE, DELETE, SET, REMOVE or DROP.\n\n"
    "Reply with the Cypher query only — no explanation and no markdown fence.\n"
)


def _final_answer_prompt(*, primer: bool) -> str:
    request = render_final_answer_request(
        pin=pin(), context="CTX", question_text="QTXT", answer_type=AnswerType.COUNT, primer=primer
    )
    return request.messages[0].content


def _cypher_prompt(*, primer: bool) -> str:
    request = render_cypher_request(
        pin=pin(), schema_text="SCH", question_text="QTXT", primer=primer
    )
    return request.messages[0].content


# --- the primer file ---------------------------------------------------------------------------


def test_primer_file_is_ascii_twelve_lines_and_1195_characters() -> None:
    raw = (_PROMPTS_DIR / "primer_pid_v1.txt").read_bytes().decode("ascii")

    assert len(raw.rstrip("\n")) == 1195
    assert len(primer_text().splitlines()) == 12
    assert primer_text() == raw.strip()


def test_prompt_hashes_cover_the_primer_file() -> None:
    assert "primer_pid_v1.txt" in prompt_hashes()


# --- off is byte-identical to the old rendering ------------------------------------------------


def test_primer_off_renders_the_final_answer_prompt_exactly_as_before() -> None:
    assert _final_answer_prompt(primer=False) == _GOLDEN_FINAL_ANSWER


def test_primer_off_renders_the_cypher_prompt_exactly_as_before() -> None:
    assert _cypher_prompt(primer=False) == _GOLDEN_CYPHER_QUERY


def test_primer_is_off_by_default_in_the_renderers() -> None:
    request = render_final_answer_request(
        pin=pin(), context="CTX", question_text="QTXT", answer_type=AnswerType.COUNT
    )
    assert request.messages[0].content == _GOLDEN_FINAL_ANSWER


# --- on: the block sits right after the first paragraph ----------------------------------------


def test_primer_on_inserts_the_block_after_the_first_paragraph_in_both_templates() -> None:
    for off, on in (
        (_GOLDEN_FINAL_ANSWER, _final_answer_prompt(primer=True)),
        (_GOLDEN_CYPHER_QUERY, _cypher_prompt(primer=True)),
    ):
        first_paragraph, rest = off.split("\n\n", 1)
        assert on == f"{first_paragraph}\n\n{primer_block()}\n\n{rest}"


def test_primer_block_is_labelled_as_background_knowledge() -> None:
    assert primer_block().startswith("General P&ID reading conventions (background knowledge")
    assert len(primer_block()) == len(primer_text()) + len(primer_block().split("\n", 1)[0]) + 1


def test_a_template_without_the_slot_is_an_error() -> None:
    with pytest.raises(ValueError, match="<<PRIMER>>"):
        fill_primer_slot("no slot here", primer=False)


# --- CypherRAG honours the setting -------------------------------------------------------------


class _EmptySource:
    def corpus_id(self) -> str:
        return "stub"

    def schema_text(self) -> str:
        return "SCH"

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[], truncated=False)

    def close(self) -> None:
        pass


@pytest.mark.parametrize("primer", [True, False])
def test_cypher_rag_sends_the_primer_only_when_asked(primer: bool) -> None:
    sent: list[ChatRequest] = []

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

    strategy = CypherRag(_EmptySource(), pin(), send, timeout_s=5.0, row_cap=3, primer=primer)
    strategy.retrieve("QTXT")

    assert (primer_text() in sent[0].messages[0].content) is primer


# --- the run config ----------------------------------------------------------------------------


def test_a_stored_config_without_the_field_loads_with_the_primer_off() -> None:
    stored = {
        "run_id": "old",
        "experiment": "TOOLING",
        "reported": False,
        "corpora": ["c"],
        "strategies": {"context_rag": {}},
        "answer_pin": pin().model_dump(mode="json"),
        "question_set_sha256": "0" * 64,
        "git_commit": "0" * 40,
        "git_dirty": False,
        "created_at": "2026-10-02T00:00:00",
    }

    assert RunConfig.model_validate(stored).primer is False


# --- the legends -------------------------------------------------------------------------------


@pytest.mark.parametrize("representation", ["plant", "occurrence"])
def test_both_legends_state_the_reading_direction_of_instrument_edges(
    representation: str,
) -> None:
    text = legend_text(representation)  # type: ignore[arg-type]

    assert "Each edge reads source, relation, target" in text
    assert "-measured_by-> transmitter -send_signal_to-> controller" in text
    assert text.count("Each edge reads source, relation, target") == 1
