"""The agent's two prompts: the system prompt (rules and tools) and the first user message."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.agent.tool_text import compact_tool_reference
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.primer import fill_primer_slot

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SEED_RULE_SLOT = "<<SEED_RULE>>"
_TOOLS_SLOT = "<<TOOLS>>"
_MAX_STEPS_SLOT = "<<MAX_STEPS>>"


@cache
def _prompt_file(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def render_system_prompt(params: AgentParams, *, primer: bool, seeded: bool) -> str:
    """The system prompt: tool reference from the registry, step limit, primer and seed rule.

    Args:
        params: its `max_steps` is told to the model.
        primer: add the P&ID reading primer (`primer.py`); off leaves no trace of it.
        seeded: add the paragraph about the seed map (`hier_agent`).
    """
    template = fill_primer_slot(_prompt_file("agent_graph_system.txt"), primer=primer)
    seed_rule = _prompt_file("agent_seed_rule.txt").strip() if seeded else ""
    text = (
        template.replace(_SEED_RULE_SLOT, seed_rule)
        .replace(_TOOLS_SLOT, compact_tool_reference())
        .replace(_MAX_STEPS_SLOT, str(params.max_steps))
    )
    return text.rstrip() + "\n"


def plant_summary(graph: ItemGraph) -> str:
    """One paragraph on the plant's size and vocabulary, so the model's filters use real names."""
    records = [graph.item(item_id) for item_id in graph.all_ids()]
    labels = sorted({label for record in records for label in record.labels})
    units = sorted({record.unit_id for record in records if record.unit_id is not None})
    sheets = graph.sheets
    if not sheets:
        raise ValueError("expected a plant with at least one sheet, found none")
    unit_part = f' and {len(units)} units (for example "{units[0]}")' if units else ""
    return (
        f'The plant has {len(sheets)} sheets (for example "{sheets[0]}"){unit_part}. '
        f"Item labels: {', '.join(labels)}. "
        "Relations: flow (send_to), signal (send_signal_to, control, measured_by)."
    )


def first_user_message(summary: str, question_text: str, seed_text: str | None) -> str:
    """The plant summary, the question and, for `hier_agent`, the seed map."""
    parts = [summary, f"Question:\n{question_text}"]
    if seed_text is not None:
        parts.append(seed_text)
    return "\n\n".join(parts)
