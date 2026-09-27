"""Where a reference answer came from, and how many sheet boundaries it crosses.

A term this module leans on, beyond `qa/models.py`'s glossary:

- **cut**: the set of plant edges the splitter replaced with a pair of
  off-page connectors when it divided the ground-truth plant into sheets.
  Every question family reads a small slice of the plant graph to compute
  its reference answer — that slice is its **evidence** — and `k` is simply
  how much of the cut that evidence's edges overlap: the number of
  off-page connectors a strategy would have to piece back together to
  answer correctly (ADR-0013 point 4, `qa-system.md` §9).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph


@dataclass(frozen=True)
class Evidence:
    """The gold subgraph one reference function read to compute its answer.

    `nodes` and `edges` hold ground-truth `node_id`s — the unsplit plant's
    own ids, never a question's printed tags. `evidence_tags` (below) is the
    tag-keyed view a `Question` actually carries, since a strategy is shown
    tags, not internal ids (`qa-system.md` §9, "Answers are expressed in
    tags").
    """

    nodes: frozenset[str]
    edges: frozenset[tuple[str, str]]


def connector_cut(manifest: SplitManifest) -> frozenset[tuple[str, str]]:
    """Every ground-truth plant edge the splitter cut with an off-page connector.

    Only pairs with `original_edge` set count: that field is the splitter's
    own record of which unsplit-plant edge it replaced with a stub pair. An
    OPEN100-sourced pair has no such record — a real drawing's original edge
    was never known to begin with (`benchmark/models.py`) — so it plays no
    part in `k`, which is defined only for the synthetic ground truth.
    """
    return frozenset(
        pair.original_edge for pair in manifest.connector_pairs if pair.original_edge is not None
    )


def evidence_k(evidence: Evidence, cut: frozenset[tuple[str, str]]) -> int:
    """How many off-page connectors `evidence` crosses: `|evidence.edges ∩ cut|`."""
    return len(evidence.edges & cut)


def evidence_sheets(evidence: Evidence, sheets: Sequence[SheetGraph]) -> list[str]:
    """Every sheet that draws at least one evidence node, sorted for determinism."""
    return sorted(
        sheet.sheet_id for sheet in sheets if not evidence.nodes.isdisjoint(sheet.graph.nodes)
    )


def evidence_tags(evidence: Evidence, plant: nx.DiGraph[str]) -> list[str]:
    """The printed tag of every evidence node, sorted — never the gold `node_id`s themselves."""
    return sorted(str(plant.nodes[node_id]["tag"]) for node_id in evidence.nodes)
