"""What each off-page connector of a sheet connects to: process, network, utility or signal.

An **off-page connector** is an arrow on a P&ID sheet that says "this line continues elsewhere".
`sheet_stats` counts them as **stubs** (pipes) and signal cuts (instrument signals). Toghraei's
chapter 20 sheets (`10-literature/toghraei-2019-ch20-sheet-counts.md`) sort the connectors by what
is on the other side, so the report does the same, with the same four codes.

The generator knows a pipe's **service** (`fluid_code`), not what the far end "is", so the code
follows from the service alone (`SERVICE_CODE`); a signal cut is always `S`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.composition_kinds import is_process_sheet
from plantgraph.benchmark.v2.network_models import INTERAREA
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.sheet_stats import (
    SheetStats,
    fed_start_ends,
    open_end_stubs,
    wired_out_ends,
)
from plantgraph.benchmark.v2.symbols import plan_node_classes


class ConnectorCode(str, Enum):
    """The target kind of a connector, with the letters of the ch.20 note."""

    PROCESS = "P"  # another equipment item or process sheet
    NETWORK = "N"  # a relief, flare or drain system
    UTILITY = "U"  # a utility supply or return
    SIGNAL = "S"  # an instrument signal continued on another sheet


class SheetKind(str, Enum):
    """The three kinds of sheet the generator draws."""

    PROCESS = "process"
    NETWORK = "network"  # a header sheet
    INTERAREA = "interarea"


#: Every pipe service of the generator and the code of its connectors (a documented judgement):
#: - P: `P` process liquid and `PG` process gas lead to other equipment;
#: - N: `FL` flare and `CHD` closed drain are the relief and drain systems;
#: - U: cooling water (`CWS`, `CWR`), steam (`LPS`, `MPS`), condensate return (`CD`), fuel gas
#:   (`FG`), instrument air (`IA`) and nitrogen (`N`) are utilities that serve the item.
#: A distribution or collection header named as a header is N in the note, but the generator
#: has no "named header" notion apart from these services, so cooling water into a header is U.
SERVICE_CODE: dict[str, ConnectorCode] = {
    "P": ConnectorCode.PROCESS,
    "PG": ConnectorCode.PROCESS,
    "FL": ConnectorCode.NETWORK,
    "CHD": ConnectorCode.NETWORK,
    "CWS": ConnectorCode.UTILITY,
    "CWR": ConnectorCode.UTILITY,
    "LPS": ConnectorCode.UTILITY,
    "MPS": ConnectorCode.UTILITY,
    "CD": ConnectorCode.UTILITY,
    "FG": ConnectorCode.UTILITY,
    "IA": ConnectorCode.UTILITY,
    "N": ConnectorCode.UTILITY,
}


class SheetConnectors(BaseModel):
    """One sheet: its kind, its equipment and its connectors by code."""

    model_config = ConfigDict(frozen=True)

    sheet_group: str
    kind: SheetKind
    equipment: int
    process: int  # P
    network: int  # N
    utility: int  # U
    signal: int  # S

    @property
    def connectors(self) -> int:
        """All off-page connectors of the sheet: stubs plus signal cuts."""
        return self.process + self.network + self.utility + self.signal


def code_of_service(service: str) -> ConnectorCode:
    """The connector code of a pipe service.

    Raises:
        ValueError: for a service missing from `SERVICE_CODE`.
    """
    if service not in SERVICE_CODE:
        raise ValueError(f"expected a service in {sorted(SERVICE_CODE)}, got {service!r}")
    return SERVICE_CODE[service]


def sheet_kind(plan: PlantPlanV2, sheet_group: str) -> SheetKind:
    """Process, network or interarea, from the unit the sheet belongs to."""
    if is_process_sheet(sheet_group):
        return SheetKind.PROCESS
    unit_no = int(sheet_group.partition(":")[0])
    owner = next(n for n in plan.network_units if n.unit_no == unit_no)
    return SheetKind.INTERAREA if owner.service == INTERAREA else SheetKind.NETWORK


def sheet_connectors(plan: PlantPlanV2, stats: list[SheetStats]) -> list[SheetConnectors]:
    """The connectors of every sheet, split by code; `stats` is `sheet_stats(plan)`.

    Raises:
        ValueError: if the split does not add up to the stubs `sheet_stats` counted.
    """
    sheet_of = plan.sheet_of
    classes: dict[str, str] = {}
    for unit_plan in plan.unit_plans:
        classes.update(plan_node_classes(unit_plan))
    wired, fed = wired_out_ends(plan), fed_start_ends(plan)
    counts: Counter[tuple[str, ConnectorCode]] = Counter()
    for unit_plan in plan.unit_plans:
        for line in unit_plan.lines:
            code = code_of_service(line.fluid_code)
            for sheet in _stub_sheets(line, sheet_of, classes, wired, fed):
                counts[(sheet, code)] += 1
    return [_sheet_row(plan, s, counts) for s in stats]


def _stub_sheets(
    line: LineSpec,
    sheet_of: Mapping[str, str],
    classes: Mapping[str, str],
    wired: frozenset[str],
    fed: frozenset[str],
) -> list[str]:
    """The sheet of every stub of one line: its open ends, then both sides of each crossing."""
    sheets = open_end_stubs(line, sheet_of, classes, wired, fed)
    chain = [n for n in (line.src_id, *(i.node_id for i in line.items), line.dst_id) if n]
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        if sheet_of[upstream] != sheet_of[downstream]:
            sheets += [sheet_of[upstream], sheet_of[downstream]]
    return sheets


def _sheet_row(
    plan: PlantPlanV2, stats: SheetStats, counts: Counter[tuple[str, ConnectorCode]]
) -> SheetConnectors:
    sheet = stats.sheet_group
    by_code = {code: counts[(sheet, code)] for code in ConnectorCode}
    if sum(by_code.values()) != stats.stubs:
        raise ValueError(f"expected sheet {sheet} to split into {stats.stubs} stubs, got {by_code}")
    return SheetConnectors(
        sheet_group=sheet,
        kind=sheet_kind(plan, sheet),
        equipment=stats.equipment,
        process=by_code[ConnectorCode.PROCESS],
        network=by_code[ConnectorCode.NETWORK],
        utility=by_code[ConnectorCode.UTILITY],
        signal=stats.signal_cuts,
    )
