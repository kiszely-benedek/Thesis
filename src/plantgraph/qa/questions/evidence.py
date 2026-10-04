"""Where a reference answer came from, and how many sheet boundaries it crosses.

A term this module leans on, beyond `qa/models.py`'s glossary:

- **cut**: the set of plant edges the splitter replaced with a pair of
  off-page connectors when it divided the ground-truth plant into sheets.
  Every question family reads a small slice of the plant graph to compute
  its reference answer — that slice is its **evidence** — and `k` is the
  number of its edges that join two different sheets: the cross-references
  a strategy would have to piece back together to answer correctly. Most
  are cut edges; the rest join an item drawn on several sheets
  (ADR-0013 point 4, ADR-0028).
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


@dataclass(frozen=True)
class Crossings:
    """How many boundaries one piece of evidence crosses (ADR-0028, ADR-0029).

    `k` is every evidence edge whose two ends have different home sheets;
    `k_connector` is the part of it a pair of off-page connectors resolves,
    `k_identity` the part resolved because the item is drawn on both sheets
    (`k == k_connector + k_identity`). `u` counts unit boundaries instead.
    """

    k: int
    k_connector: int
    k_identity: int
    u: int


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


class SheetIndex:
    """Which sheets draw each plant node, and on which sheet each node is at home.

    Built once per corpus. The question build asks "which sheets does this
    evidence touch?" for every candidate; scanning all sheets per question
    is O(sheets) each and did not finish at 1,000 sheets, whereas this map
    costs O(evidence nodes).

    A node's **home sheet** is the sheet the partition put it on. An item
    drawn on several sheets (an identity group) has one home occurrence and
    reference occurrences elsewhere; every other node has only one sheet.
    Home sheets come from the partition, which runs before duplication, so
    `k` does not change with the duplication rate (ADR-0028).
    """

    def __init__(
        self,
        sheets_of: dict[str, frozenset[str]],
        home: dict[str, str],
        cut: frozenset[tuple[str, str]],
    ) -> None:
        self.sheets_of = sheets_of
        self.home = home
        self.cut = cut

    @classmethod
    def from_sheets(cls, sheets: Sequence[SheetGraph], manifest: SplitManifest) -> SheetIndex:
        """Invert the sheets' node lists; the manifest names each multi-sheet node's home."""
        collected: dict[str, set[str]] = {}
        for sheet in sheets:
            for node_id in sheet.graph.nodes:
                collected.setdefault(str(node_id), set()).add(sheet.sheet_id)
        sheets_of = {node_id: frozenset(ids) for node_id, ids in collected.items()}
        home_keys = {group.home for group in manifest.identity_groups}
        home = {node_id: _home_sheet(node_id, ids, home_keys) for node_id, ids in sheets_of.items()}
        return cls(sheets_of, home, connector_cut(manifest))

    def crosses(self, source_id: str, target_id: str) -> bool:
        """Whether the edge's two ends have different home sheets."""
        return self._home_of(source_id) != self._home_of(target_id)

    def _home_of(self, node_id: str) -> str:
        if node_id not in self.home:
            raise ValueError(f"expected node {node_id!r} to be drawn on some sheet, found none")
        return self.home[node_id]


def _home_sheet(node_id: str, sheet_ids: frozenset[str], home_keys: set[str]) -> str:
    """The node's only sheet, or the one whose `sheet:node` key an identity group names as home."""
    if len(sheet_ids) == 1:
        return next(iter(sheet_ids))
    homes = [sheet_id for sheet_id in sorted(sheet_ids) if f"{sheet_id}:{node_id}" in home_keys]
    if len(homes) != 1:
        raise ValueError(
            f"expected exactly one home sheet for {node_id!r} among {sorted(sheet_ids)}, "
            f"found {homes}"
        )
    return homes[0]


def crossings(evidence: Evidence, index: SheetIndex, plant: nx.DiGraph[str]) -> Crossings:
    """Count the sheet and unit boundaries `evidence`'s edges cross.

    Raises:
        ValueError: more cut edges than home-sheet crossings, which would make
            `k_identity` negative — the manifest and the sheets disagree.
    """
    k = sum(index.crosses(source_id, target_id) for source_id, target_id in evidence.edges)
    k_connector = len(evidence.edges & index.cut)
    if k_connector > k:
        raise ValueError(
            f"expected cut edges to cross home sheets (k >= k_connector), got k={k}, "
            f"k_connector={k_connector}"
        )
    return Crossings(
        k=k, k_connector=k_connector, k_identity=k - k_connector, u=_units_crossed(evidence, plant)
    )


def _units_crossed(evidence: Evidence, plant: nx.DiGraph[str]) -> int:
    """Evidence edges whose endpoints both carry a `unit_id` and the ids differ.

    An endpoint with no `unit_id` is not a unit boundary, so it never counts.
    """
    crossed = 0
    for source_id, target_id in evidence.edges:
        source_unit = plant.nodes[source_id].get("unit_id")
        target_unit = plant.nodes[target_id].get("unit_id")
        if source_unit is not None and target_unit is not None and source_unit != target_unit:
            crossed += 1
    return crossed


def evidence_sheets(evidence: Evidence, index: SheetIndex) -> list[str]:
    """Every sheet that draws at least one evidence node, sorted for determinism."""
    drawn_on: set[str] = set()
    for node_id in evidence.nodes:
        drawn_on |= index.sheets_of.get(node_id, frozenset())
    return sorted(drawn_on)


def evidence_tags(evidence: Evidence, plant: nx.DiGraph[str]) -> list[str]:
    """The printed tag of every tagged evidence node, sorted — never the gold `node_id`s.

    A node with no tag (an actuator, `schema.UNTAGGED_CLASSES`) is skipped.
    """
    tags = (plant.nodes[node_id].get("tag") for node_id in evidence.nodes)
    return sorted(str(tag) for tag in tags if tag is not None)
