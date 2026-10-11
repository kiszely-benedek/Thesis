"""The five EX01 arms (design `exp0001-single-sheet.md` §4): strategy, pin and deadline of each.

A pin names the model and its settings (GPT-6 Luna at low or high reasoning effort, or ChatP&ID's
GPT-5-mini). The pin and parameter files are data under `data/runs/exp0001/inputs/`, copied byte
for byte from the sealed run, so the arms are the EXP-0002 tiers unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.exp0001.ex01_models import Ex01ArmRecord
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.harness.attempt import active_remaining_s
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps, build_strategy
from plantgraph.qa.strategies.base import Strategy

#: ContextRAG's one call is its whole work, so it gets a longer budget than the tiers (design §4).
CONTEXT_DEADLINE_S = 300.0
TIER_DEADLINE_S = 120.0


@dataclass(frozen=True)
class ArmDefinition:
    """The files and limits that define one arm."""

    strategy: str
    pin_file: str
    #: Parameter file holding `{"<strategy>": {...}}`; `None` for a strategy without parameters.
    params_file: str | None
    deadline_s: float


ARM_DEFINITIONS: dict[str, ArmDefinition] = {
    "ctx-high": ArmDefinition(
        "context_rag", "pin_agent_luna_final_high.json", None, CONTEXT_DEADLINE_S
    ),
    "ctx-low": ArmDefinition("context_rag", "pin_cypher_luna_low.json", None, CONTEXT_DEADLINE_S),
    "ctx-gpt5mini": ArmDefinition("context_rag", "pin_ctx_gpt5mini.json", None, CONTEXT_DEADLINE_S),
    "cyp": ArmDefinition(
        "cypher_rag_plant",
        "pin_cypher_luna_low.json",
        "params_cypher_plant.json",
        TIER_DEADLINE_S,
    ),
    "ag": ArmDefinition(
        "graph_agent_low_steps",
        "pin_agent_luna_final_high.json",
        "params_agent_low.json",
        TIER_DEADLINE_S,
    ),
}

#: The policy's strategy name -> the arm whose rows feed that tier of cascade_v3.
ARM_OF_STRATEGY = {"cypher_rag_plant": "cyp", "graph_agent_low_steps": "ag"}


def load_arm_record(name: str, inputs_dir: Path) -> Ex01ArmRecord:
    """Read an arm's pin and parameters from `inputs_dir`.

    Raises:
        ValueError: `name` is not an arm.
        FileNotFoundError: a pin or parameter file is missing.
    """
    definition = ARM_DEFINITIONS.get(name)
    if definition is None:
        raise ValueError(f"expected an arm in {sorted(ARM_DEFINITIONS)}, found {name!r}")
    pin = ModelPin.model_validate_json(_read(inputs_dir / definition.pin_file))
    return Ex01ArmRecord(
        strategy=definition.strategy,
        params=_read_params(definition, inputs_dir),
        pin=pin,
        pin_sha256=pin.pin_hash(),
        deadline_s=definition.deadline_s,
    )


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"expected the arm input file {path}, found nothing")
    return path.read_text(encoding="utf-8")


def _read_params(definition: ArmDefinition, inputs_dir: Path) -> dict[str, Any]:
    if definition.params_file is None:
        return {}
    by_strategy = json.loads(_read(inputs_dir / definition.params_file))
    if definition.strategy not in by_strategy:
        raise ValueError(
            f"expected {definition.params_file} to hold parameters for {definition.strategy!r}, "
            f"found {sorted(by_strategy)}"
        )
    params: dict[str, Any] = by_strategy[definition.strategy]
    return params


def build_arm_strategy(
    record: Ex01ArmRecord,
    view: GraphView,
    send: SendChatRequest,
    cypher_source: CypherSource | None,
    primer: bool,
) -> Strategy:
    """The arm's strategy over `view`, built by the harness registry exactly as a harness run does.

    `cypher_source` is the checked database for the Cypher arm; `None` for every other arm.
    """
    cypher = (
        CypherDeps(cypher_source, record.pin, send, primer) if cypher_source is not None else None
    )
    llm = LlmDeps(record.pin, send, primer, active_remaining_s)
    return build_strategy(record.strategy, record.params, view, cypher, llm)
