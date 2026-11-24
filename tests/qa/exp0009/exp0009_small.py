"""A tiny v2.2 plant built through the EXP-0009 build step, shared by the tests (not a test)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import httpx2

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.qa.exp0009.build import CorpusBRecord, build_plant
from plantgraph.qa.exp0009.draw import real_document_flags
from plantgraph.qa.exp0009.plan import PlantSpec22, Role
from plantgraph.qa.models import Question

N_UNITS, SEED = 4, 1


def small_spec(plant_id: str = "D100g22", untagged: bool | None = None) -> PlantSpec22:
    """A 4-unit dev plant; `untagged` forces its documents, else they keep their own draw."""
    config = HeadlinePresetV22().generator_config(N_UNITS, SEED)
    flags = real_document_flags(N_UNITS, SEED)
    if untagged is not None:
        flags = (untagged,) * len(flags)
    return PlantSpec22(
        plant_id=plant_id, role=Role.DEV, scale=100, seed=SEED, target_sheets=100,
        n_units=N_UNITS, predicted_sheets=plan_plant(config).sheet_count,
        document_untagged=flags,
    )  # fmt: skip


@cache
def built_small() -> tuple[PlantSpec22, Path, CorpusBRecord]:
    """The small plant built once per test session: spec, corpora root, its B record."""
    root = Path(mkdtemp(prefix="exp0009-small-")) / "corpora"
    spec = small_spec()
    return spec, root, build_plant(spec, root, None)


def reply(text: str) -> httpx2.Response:
    """A chat reply with usage, cost and the `provider` field a real OpenRouter reply carries."""
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}
    choice = {"index": 0, "message": {"role": "assistant", "content": text}}
    choice["finish_reason"] = "stop"
    body = {"id": "gen-2", "object": "chat.completion", "created": 0, "model": "m"}
    body["provider"] = "Fake"
    return httpx2.Response(200, json={**body, "choices": [choice], "usage": usage})


def gold_transport(questions: list[Question]) -> httpx2.Client:
    """The model: an agent step says done; a final prompt gets the gold answer of its question."""
    reference_of = {q.text: q.reference for q in questions}

    def handle(request: httpx2.Request) -> httpx2.Response:
        messages = json.loads(request.content)["messages"]
        if messages[0]["role"] == "system":
            return reply('{"done": true}')
        prompt = messages[0]["content"]
        found = next(ref for text, ref in reference_of.items() if text in prompt)
        return reply(json.dumps({"answer": found, "not_present": False}))

    return httpx2.Client(transport=httpx2.MockTransport(handle))
