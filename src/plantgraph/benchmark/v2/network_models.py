"""The data of the network and interarea sheets (v2.2, design 7).

A **network** is a pipe system the whole plant shares: the flare header, the closed drain, the
cooling-water and steam mains, the fuel-gas main. Toghraei 2019 pp.32-34 draws them on their own
P&IDs, mostly pipes, so a process sheet shows only a short stub that ends at a connector. An
**interarea** sheet carries the lines between two areas (here: two trains). A **tie-in** is one
place where a process line joins a header. **Distribution** services flow from the header to the
process (cooling water supply, steam, fuel gas); **collection** services flow from the process
into the header (flare, closed drain, cooling water return, condensate).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config_v22 import NETWORK_SERVICES
from plantgraph.benchmark.v2.hidden_state import FluidClass
from plantgraph.benchmark.v2.sheets import UnitSheets
from plantgraph.benchmark.v2.trim_plan import TrimPlan

#: network unit numbers sit above every process unit number (H1000g21p1 has 608 units)
NETWORK_UNIT_BASE = 9000
INTERAREA = "INTERAREA"  # the "service" of an interarea unit
_INTERAREA_INDEX = len(NETWORK_SERVICES)


class TieDirection(str, Enum):
    """Whether the stream runs from the header into the process, or the other way."""

    DISTRIBUTION = "distribution"
    COLLECTION = "collection"


#: which way each network service flows (TOG p.360, Fig. 17.1)
SERVICE_DIRECTION: dict[str, TieDirection] = {
    "CWS": TieDirection.DISTRIBUTION,
    "LPS": TieDirection.DISTRIBUTION,
    "MPS": TieDirection.DISTRIBUTION,
    "FG": TieDirection.DISTRIBUTION,
    "FL": TieDirection.COLLECTION,
    "CHD": TieDirection.COLLECTION,
    "CWR": TieDirection.COLLECTION,
    "CD": TieDirection.COLLECTION,
}

#: the declared fluid class of every line service (design 6.1): the plant is a hydrocarbon plant
FLUID_CLASS_OF_SERVICE: dict[str, FluidClass] = {
    "P": FluidClass.HYDROCARBON,
    "PG": FluidClass.HYDROCARBON,
    "FG": FluidClass.HYDROCARBON,
    "FL": FluidClass.HYDROCARBON,
    "CHD": FluidClass.HYDROCARBON,
    "CWS": FluidClass.WATER,
    "CWR": FluidClass.WATER,
    "LPS": FluidClass.STEAM,
    "MPS": FluidClass.STEAM,
    "CD": FluidClass.STEAM,
    "IA": FluidClass.INERT,
    "N": FluidClass.INERT,
}


def network_unit_no(train_no: int, service: str) -> int:
    """`9000 + 10 * train + service index`; the interarea unit of a train is index 8."""
    index = _INTERAREA_INDEX if service == INTERAREA else NETWORK_SERVICES.index(service)
    return NETWORK_UNIT_BASE + 10 * train_no + index


def is_network_unit_no(unit_no: int) -> bool:
    """True for a number from the reserved block."""
    return unit_no >= NETWORK_UNIT_BASE


class NetworkUnit(BaseModel):
    """One network (or interarea) unit: a plan of header pipes, its sheets and where it belongs."""

    model_config = ConfigDict(frozen=True)

    unit_no: int
    train_no: int
    service: str  # a network service code, or `INTERAREA`
    title: str
    plan: TrimPlan
    sheets: UnitSheets

    @property
    def is_interarea(self) -> bool:
        """True for an interarea unit."""
        return self.service == INTERAREA


class Crossing(BaseModel):
    """A process-sheet end that leaves for a network sheet: what the header unit must connect to.

    `node_id` is the process part the feeder line attaches to: the last part of a collection
    sub-header, the first part of a distribution one.
    """

    model_config = ConfigDict(frozen=True)

    train_no: int
    unit_no: int
    sheet: str  # the process sheet, `3:1`
    service: str
    node_id: str

    @property
    def direction(self) -> TieDirection:
        """The way this crossing's service flows."""
        return SERVICE_DIRECTION[self.service]
