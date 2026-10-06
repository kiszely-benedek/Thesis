"""`GraphAgent` and `HierAgent`: the two strategies built on the agent loop (design §5, §6.1).

Both explore the merged plant (`ItemGraph`) with the six plant-API primitives and hand what
they gathered to the shared final-answer step. `HierAgent` differs in one thing: its first
message carries a free, rule-made seed map (`seed.py`), so the model can stop at once when the
seed already holds the evidence.

A strategy sees only the question text. Every model call goes through the sender the harness
gives it, so the call counts towards the question's cost and the run's spend cap.
"""

from __future__ import annotations

from typing import Any

from plantgraph.llm.models import ModelPin
from plantgraph.qa.agent.loop import run_agent_loop
from plantgraph.qa.agent.models import AgentParams, AgentRun
from plantgraph.qa.agent.prompts import first_user_message, plant_summary, render_system_prompt
from plantgraph.qa.agent.seed import Seed, build_seed
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import RetrievalResult
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import sheet_of_key
from plantgraph.qa.plant_api.primitives import PlantApi

GRAPH_AGENT_NAME = "graph_agent"
HIER_AGENT_NAME = "hier_agent"

_CONTEXT_HEADING = "Tool results gathered for this question:"


class GraphAgent:
    """A model composes the plant primitives, one call at a time, to gather the evidence."""

    name = GRAPH_AGENT_NAME
    _seeded = False

    def __init__(
        self,
        item_graph: ItemGraph,
        pin: ModelPin,
        send: SendChatRequest,
        *,
        params: AgentParams | None = None,
        primer: bool = False,
    ) -> None:
        """`send` is the harness's metered sender; `primer` adds the P&ID reading primer."""
        self._graph = item_graph
        self._pin = pin
        self._send = send
        self.params = params or AgentParams()
        self._system_prompt = render_system_prompt(self.params, primer=primer, seeded=self._seeded)
        self._summary = plant_summary(item_graph)

    @property
    def system_prompt(self) -> str:
        """The system prompt every question of this strategy starts with."""
        return self._system_prompt

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Run the loop; whatever stopped it, what was gathered becomes the context."""
        seed = self._seed(question_text)
        run = run_agent_loop(
            pin=self._pin,
            send=self._send,
            api=PlantApi(self._graph, max_items=self.params.max_items_listed),
            system_prompt=self._system_prompt,
            first_user_message=first_user_message(
                self._summary, question_text, None if seed is None else seed.text
            ),
            params=self.params,
        )
        context = _context(seed, run)
        trace = _trace(run, seed, context)
        return RetrievalResult(context=context, failure=None, trace=trace)

    def _seed(self, question_text: str) -> Seed | None:
        return None


class HierAgent(GraphAgent):
    """`GraphAgent` that starts from a rule-made seed map (the user's hierarchical hypothesis)."""

    name = HIER_AGENT_NAME
    _seeded = True

    def __init__(
        self,
        view: GraphView,
        item_graph: ItemGraph,
        pin: ModelPin,
        send: SendChatRequest,
        *,
        params: AgentParams | None = None,
        primer: bool = False,
    ) -> None:
        """`view` finds the anchors in the question; `item_graph` is the plant the tools walk."""
        super().__init__(item_graph, pin, send, params=params, primer=primer)
        self._view = view

    def _seed(self, question_text: str) -> Seed | None:
        return build_seed(question_text, self._view, self._graph, self.params.seed_chars)


def _context(seed: Seed | None, run: AgentRun) -> str:
    """The seed (if any), then each successful call and its result, in order."""
    parts = [] if seed is None else [seed.text]
    parts.append(_CONTEXT_HEADING)
    if not run.gathered:
        parts.append("(no tool calls were made)")
    parts += [f"Call: {result.call_text}\n{result.observation}" for result in run.gathered]
    return "\n\n".join(parts)


def _trace(run: AgentRun, seed: Seed | None, context: str) -> dict[str, Any]:
    """The keys every report reads (`routed_sheets`, `serialized_keys`) plus the agent's own."""
    keys = sorted({*run.touched_keys, *(() if seed is None else seed.touched_keys)})
    trace: dict[str, Any] = {
        "representation": "plant",
        "agent_steps": [step.model_dump(mode="json") for step in run.steps],
        "stop_reason": run.stop_reason,
        "n_steps": len(run.steps),
        "tool_errors": run.tool_errors,
        "invalid_actions": run.invalid_actions,
        "routed_sheets": sorted({sheet_of_key(key) for key in keys}),
        "serialized_keys": keys,
        "context_chars": len(context),
    }
    if seed is not None:
        trace.update(
            seed_label=seed.label,
            seed_chars=len(seed.text),
            seed_items=seed.n_items_shown,
            seed_program=list(seed.program),
            seed_program_skipped=seed.program_skipped,
        )
    return trace
