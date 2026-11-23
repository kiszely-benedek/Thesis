"""The answer key of a v2.2 plant: the v2.1 record plus the hidden design state."""

from __future__ import annotations

from pydantic import Field

from plantgraph.benchmark.v2.documents import DocumentRecord
from plantgraph.benchmark.v2.hidden_state import HiddenDesignState
from plantgraph.benchmark.v2.plan_models import GenerationRecordV2


class GenerationRecordV22(GenerationRecordV2):
    """`GenerationRecordV2` plus `hidden_state` and the `documents`; gold, never in the graph."""

    #: the conventions of each document (design 5); empty when the handbook is off
    documents: tuple[DocumentRecord, ...] = ()
    hidden_state: HiddenDesignState = Field(default_factory=HiddenDesignState)
