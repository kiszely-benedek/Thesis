"""The resolver's output: `ResolutionReport` and `Resolution` (design `kg-construction.md` §5.5)."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from pydantic import BaseModel

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup, UnresolvedConnector


class ResolutionReport(BaseModel):
    """A numeric summary of one `resolve()` run.

    This is bookkeeping, not a result (design §1: "the resolver gate is a
    correctness check, not a result") — measuring accuracy/coverage needs the
    `OccurrenceMap` and the `SplitManifest`, which this package never sees.
    """

    n_sheets: int
    n_occurrences: int
    n_connectors: int
    pairs_by_rule: dict[str, int]
    unresolved_by_reason: dict[str, int]
    n_identity_groups: int
    ambiguous_tag_keys: int
    edge_attribute_conflicts: int


@dataclass
class Resolution:
    """The full output of `resolve()`: merged graph, plus a trace of every intermediate decision.

    A plain dataclass, like `SheetGraph`: the graph topology is meant for
    networkx, not for serialization (splitter.md section 2).
    """

    plant: nx.DiGraph[str]
    connector_pairs: list[ConnectorPair]
    identity_groups: list[IdentityGroup]
    unresolved: list[UnresolvedConnector]
    report: ResolutionReport
