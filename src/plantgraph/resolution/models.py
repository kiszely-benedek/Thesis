"""A resolver kimenete: `ResolutionReport` és `Resolution` (design `kg-construction.md` §5.5)."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from pydantic import BaseModel

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup, UnresolvedConnector


class ResolutionReport(BaseModel):
    """A `resolve()` futásának számszerű összegzése.

    Ez könyvelés, nem eredmény (design §1: "a resolver gate egy helyesség-
    kapu, nem eredmény") — a pontosság/fedettség méréséhez az `OccurrenceMap`
    és a `SplitManifest` kell, amit ez a csomag sosem lát.
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
    """A `resolve()` teljes kimenete: az egyesített gráf, plusz minden köztes döntés nyoma.

    Sima dataclass, mint a `SheetGraph`: a gráf topológiáját networkx-nek
    szánjuk, nem szerializáljuk (splitter.md 2. fejezet).
    """

    plant: nx.DiGraph[str]
    connector_pairs: list[ConnectorPair]
    identity_groups: list[IdentityGroup]
    unresolved: list[UnresolvedConnector]
    report: ResolutionReport
