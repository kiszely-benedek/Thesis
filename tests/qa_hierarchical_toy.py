"""Toy corpora for the Hierarchical tests, built on `qa_routing_toy.ToyCorpus`."""

from __future__ import annotations

from typing import Any

from plantgraph.qa.strategies.hierarchical import Hierarchical
from plantgraph.qa.unit_router import UnitRouter
from qa_routing_toy import ToyCorpus

#: Big enough that no test ever hits the limit unless it sets its own.
UNLIMITED = 10**9


def chain_toy(*, junk_per_sheet: int = 3) -> ToyCorpus:
    """Flow `TA`(S1) -> `m2`(S2) -> `m3`(S3) -> `m4`(S4) -> `TE`(S5), each hop one cut.

    Every sheet also holds unconnected junk items, so a through-line (only the
    path) is clearly smaller than the whole sheet. S9 is an island holding `TZ`.
    """
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    for sheet, node in (("S2", "m2"), ("S3", "m3"), ("S4", "m4")):
        toy.item(sheet, node, f"T{node.upper()}")
    toy.item("S5", "e", "TE")
    toy.cut("S1", "a", "S2", "m2", "c1")
    toy.cut("S2", "m2", "S3", "m3", "c2")
    toy.cut("S3", "m3", "S4", "m4", "c3")
    toy.cut("S4", "m4", "S5", "e", "c4")
    _add_junk(toy, ("S1", "S2", "S3", "S4", "S5"), junk_per_sheet)
    toy.item("S9", "z", "TZ")
    return toy


def tail_toy() -> ToyCorpus:
    """`TA`(S1) -> S2 -> S3 -> S4: successive rings around the single anchor `TA`."""
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    for sheet in ("S2", "S3", "S4"):
        toy.item(sheet, f"x{sheet}", f"TX{sheet[1:]}")
    toy.cut("S1", "a", "S2", "xS2", "c1")
    toy.cut("S2", "xS2", "S3", "xS3", "c2")
    toy.cut("S3", "xS3", "S4", "xS4", "c3")
    _add_junk(toy, ("S1", "S2", "S3", "S4"), 3)
    return toy


def _add_junk(toy: ToyCorpus, sheets: tuple[str, ...], per_sheet: int) -> None:
    for sheet in sheets:
        for index in range(per_sheet):
            toy.item(sheet, f"j{sheet}_{index}", f"J-{sheet}-{index}")


def strategy(
    toy: ToyCorpus,
    *,
    route_mode: str = "flow_path",
    budget_mode: str = "drop_rings",
    sheet_hops: int = 0,
    max_context_chars: int = UNLIMITED,
    unit_router: UnitRouter | None = None,
) -> Hierarchical:
    """A Hierarchical over `toy`; the modes are plain strings so tests can parametrize them."""
    params: dict[str, Any] = {"route_mode": route_mode, "budget_mode": budget_mode}
    return Hierarchical(
        toy.view(),
        sheet_hops=sheet_hops,
        max_context_chars=max_context_chars,
        unit_router=unit_router,
        **params,
    )
