"""The answer key of a v2.2 plant: the v2.1 record plus the hidden design state."""

from __future__ import annotations

from pydantic import Field

from plantgraph.benchmark.v2.hidden_state import HiddenDesignState
from plantgraph.benchmark.v2.plan_models import GenerationRecordV2


class GenerationRecordV22(GenerationRecordV2):
    """`GenerationRecordV2` plus `hidden_state`; gold, never stored in the graph under retrieval."""

    hidden_state: HiddenDesignState = Field(default_factory=HiddenDesignState)
