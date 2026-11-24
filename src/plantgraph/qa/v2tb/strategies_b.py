"""The two B strategies: V2T-A2's `cypher_rag_lines` and `graph_agent_lines`, B-aware (§10 R6).

Each is a subclass of its frozen original and differs in one respect: the B primer replaces A's in
the prompt it writes, and the data it reads is the B corpus (positions in the store and in the
agent's items). Where the frozen class has no seam smaller than a method, that one method is copied
and its docstring names the original.

- `CypherRagLinesB` reads the B schema text through its `Neo4jGraphViewB` source; only the query
  prompt needs the B primer.
- `GraphAgentLinesB` walks an item graph built by `build_item_graph_b`, through `PlantApiB`
  (`plant_api_b.py`), so a valve's position and an untagged valve's line numbers are in what it
  reads, and its system prompt says how to read those two brackets.
"""

from __future__ import annotations

from plantgraph.llm.models import ModelPin
from plantgraph.qa.agent.loop import RemainingSeconds, run_agent_loop
from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.agent.prompts import first_user_message
from plantgraph.qa.agent.strategies import GraphAgentLines, _context, _trace
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.models import Outcome, RetrievalResult
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.primer import primer_block
from plantgraph.qa.strategies.cypher_rag import format_context
from plantgraph.qa.strategies.cypher_rag_lines import (
    _QUERY_TEMPLATE,
    CypherRagLines,
    _trace_of,
    render_repair_prompt,
)
from plantgraph.qa.v2tb.item_graph_b import shows_b_properties
from plantgraph.qa.v2tb.plant_api_b import PlantApiB
from plantgraph.qa.v2tb.primer_b import fill_primer_slot_b, primer_block_b

CYPHER_RAG_LINES_B_NAME = "cypher_rag_lines_b"
GRAPH_AGENT_LINES_B_NAME = "graph_agent_lines_b"


def render_query_prompt_b(*, schema_text: str, question_text: str, primer: bool = False) -> str:
    """`render_query_prompt` with the B primer: the query-writing prompt of a B corpus."""
    template = fill_primer_slot_b(_QUERY_TEMPLATE.read_text(encoding="utf-8"), primer=primer)
    return template.replace("<<SCHEMA>>", schema_text).replace("<<QUESTION>>", question_text)


class CypherRagLinesB(CypherRagLines):
    """`CypherRagLines` whose query-writing prompt carries the B primer."""

    name = CYPHER_RAG_LINES_B_NAME

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Copy of `CypherRagLines.retrieve`, writing the prompt with `render_query_prompt_b`."""
        tag_note, tag_trace = self._check_tags(question_text)
        prompt = render_query_prompt_b(
            schema_text=self._source.schema_text(),
            question_text=question_text,
            primer=self._primer,
        )
        attempts = [self._attempt(prompt)]
        if attempts[0].repairable:
            repair = render_repair_prompt(prompt, attempts[0], timeout_s=self._timeout_s)
            attempts.append(self._attempt(repair))
        trace = {**_trace_of(attempts), **tag_trace}
        last = attempts[-1]
        if last.result is None:
            return RetrievalResult(
                context=None,
                failure=Outcome.RETRIEVAL_ERROR,
                trace={**trace, "cypher_error": last.error},
            )
        body = format_context(last.query, last.result, self._row_cap, self._source.label_names())
        context = f"{tag_note}\n\n{body}" if tag_note else body
        trace.update(
            n_rows=len(last.result.rows),
            truncated=last.result.truncated,
            empty_result=not last.result.rows,
        )
        return RetrievalResult(context=context, failure=None, trace=trace)


class GraphAgentLinesB(GraphAgentLines):
    """`GraphAgentLines` over a B item graph, with the B primer and the B tool results."""

    name = GRAPH_AGENT_LINES_B_NAME

    def __init__(
        self,
        item_graph: ItemGraph,
        pin: ModelPin,
        send: SendChatRequest,
        *,
        params: AgentParams | None = None,
        primer: bool = False,
        remaining_s: RemainingSeconds | None = None,
    ) -> None:
        super().__init__(
            item_graph, pin, send, params=params, primer=primer, remaining_s=remaining_s
        )
        if primer:
            self._system_prompt = _with_b_primer(self._system_prompt)
        if shows_b_properties(item_graph):  # an empty positions map keeps the frozen prompt
            self._system_prompt = _with_b_reading(self._system_prompt)

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Copy of `GraphAgent.retrieve`, walking the plant through `PlantApiB`."""
        seed = self._seed(question_text)
        run = run_agent_loop(
            pin=self._pin,
            send=self._send,
            api=PlantApiB(self._graph, max_items=self.params.max_items_listed),
            system_prompt=self._system_prompt,
            first_user_message=first_user_message(
                self._summary, question_text, None if seed is None else seed.text
            ),
            params=self.params,
            remaining_s=self._remaining_s,
        )
        context = _context(seed, run)
        return RetrievalResult(context=context, failure=None, trace=_trace(run, seed, context))


def _with_b_primer(system_prompt: str) -> str:
    """Swap A's primer block in the agent's system prompt for the B block.

    Raises:
        ValueError: A's primer block is not in the prompt (the primer was off, or the frozen
            template changed), so the swap would silently do nothing.
    """
    block = primer_block()
    if block not in system_prompt:
        raise ValueError("expected the agent's system prompt to contain A's primer block")
    return system_prompt.replace(block, primer_block_b(), 1)


#: The frozen sentence of the agent prompt that describes an item line (the V2T system prompt).
_ITEM_LINE_SENTENCE = (
    "An item line reads TAG (Class, kind K, unit U, sheets S1,S2), then [no inflow] or "
    "[no outflow] where they apply."
)
#: What a B corpus adds to it. It is in the agent prompt and not in the primer because the primer
#: also goes into the Cypher query prompt, where no tool line ever appears.
_B_READING_SENTENCE = (
    "On this plant a valve's line may also end with [operating_position NC], its normal "
    "position, and an untagged valve's line with [line 6\"-P-1203-A1A], the line number of its "
    "pipe (two numbers where the line number changes at the valve). An untagged valve still "
    "counts as a valve and belongs in a list of valves. When you name one, its next_to is the "
    "first tagged item you meet walking from the valve itself along the flow on that side, which "
    "is often not the item the question is about."
)


def _with_b_reading(system_prompt: str) -> str:
    """Add the sentence that explains the two B brackets right after the item-line sentence.

    Raises:
        ValueError: the frozen item-line sentence is not in the prompt (the frozen template
            changed), so the addition would silently do nothing.
    """
    if _ITEM_LINE_SENTENCE not in system_prompt:
        raise ValueError(
            f"expected the agent's system prompt to contain {_ITEM_LINE_SENTENCE!r}, found none"
        )
    return system_prompt.replace(
        _ITEM_LINE_SENTENCE, f"{_ITEM_LINE_SENTENCE} {_B_READING_SENTENCE}", 1
    )
