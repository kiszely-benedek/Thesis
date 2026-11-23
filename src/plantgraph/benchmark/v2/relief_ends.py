"""A relief device on a hydrocarbon line never ends open (design 17.14 N3).

A **relief device** opens to let a vessel or line discharge when its pressure gets too high: a
safety valve (PSV), a rupture disc (a thin plate that bursts at a set pressure), or the outlet
block valve of a PSV. Toghraei 2019 p.368 sends every one of them into the emergency release
(flare) network, so none may end in mid-air on a line that carries hydrocarbon. A water or steam
relief (a thermal PSV on cooling water, a steam stub's PSV) is innocent and may vent to the air
(TOG Table 8.9, pp.140-141), so only the fluid class of the line decides.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.hidden_state import FluidClass
from plantgraph.benchmark.v2.network_models import FLUID_CLASS_OF_SERVICE
from plantgraph.benchmark.v2.trim_plan import TrimPlan

#: the roles of the parts that end a relief line: a PSV or its outlet block, a rupture disc
RELIEF_ROLES = frozenset(
    {"psv", "psv_outlet_block", "compressor_discharge_psv", "reactor_rupture_disc"}
)


def open_hydrocarbon_reliefs(plans: Sequence[TrimPlan]) -> list[str]:
    """The relief parts that end a hydrocarbon line with no line starting from them.

    `plans` must hold every unit: the line that continues a relief end (a sub-header, or the feeder
    of a header unit) belongs to another plan than the relief device.
    """
    continued = {line.src_id for plan in plans for line in plan.lines}
    found = []
    for plan in plans:
        for line in plan.lines:
            if line.dst_id is not None or not line.items:
                continue
            last = line.items[-1].node_id
            hydrocarbon = FLUID_CLASS_OF_SERVICE.get(line.fluid_code) is FluidClass.HYDROCARBON
            if hydrocarbon and plan.roles.get(last) in RELIEF_ROLES and last not in continued:
                found.append(last)
    return found


def assert_no_open_relief(plans: Sequence[TrimPlan]) -> None:
    """Raise if any relief device of any plan ends open on a hydrocarbon line.

    Raises:
        ValueError: naming the parts, so the tie pass that missed them can be found.
    """
    # rule TOG32-NETWORK-SHEETS: relief goes to the flare network (TOG p.32–34, p.368)
    open_ends = sorted(open_hydrocarbon_reliefs(plans))
    if open_ends:
        raise ValueError(
            "expected every relief device on a hydrocarbon line to join the flare network, "
            f"found {len(open_ends)} that end open: {open_ends[:5]}"
        )
