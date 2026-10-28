"""Which final-answer template a strategy uses: F1's shared one, or the V2T one (ADR-0061).

F1's `prompts/final_answer.txt` stays byte-identical, so every v1 and F1 run still replays.
The two tuned V2T strategies read `prompts/final_answer_v2t.txt` instead: the same text plus
three rules about what an answer may list (design `qa-tuning-v2.md` section 4.4).
"""

from __future__ import annotations

from pathlib import Path

#: Strategy names that use the V2T template. These equal `GRAPH_AGENT_LINES_NAME` and
#: `cypher_rag.LINES_NAME`; they are spelled here because importing those modules would create
#: an import cycle through `strategies/base.py`. A test keeps the two sets equal.
V2T_STRATEGY_NAMES: frozenset[str] = frozenset({"cypher_rag_lines", "graph_agent_lines"})

V2T_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "final_answer_v2t.txt"


def template_path_for(strategy_name: str) -> Path | None:
    """The V2T template for a V2T strategy; `None` (F1's template) for every other one."""
    return V2T_TEMPLATE_PATH if strategy_name in V2T_STRATEGY_NAMES else None
