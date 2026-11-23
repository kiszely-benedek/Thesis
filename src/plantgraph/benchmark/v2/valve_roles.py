"""Which valve role has which normal position, and which service a valve's fail action follows.

Two terms. A **blocking valve** is a manual valve that isolates a pipe part (a pump's suction
block, a PSV's inlet block). An **automatic valve** has an actuator: a control valve throttles
under a controller, an on-off valve is only open or shut. A valve's **role** is the name the
pattern gave its place in the drawing (`suction_block`, `cv_bypass_valve`), which is how the
generator and its checks know what a valve is for.

The tables below are the only place the position rules (design 4.2) are written down. They are
keyed by role, so a rule never depends on a tag or on the random draws of a pattern.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.plan_models import OperatingPosition, StreamKindV2
from plantgraph.benchmark.v2.vocabulary import ItemKind

# rule TOG114-VENT-DRAIN-NC: vent and drain valves are closed in operation (Toghraei 2019 p.114)
#: A flush valve and the bleed of a double block and bleed are service connections of the same kind.
VENT_DRAIN_ROLES = frozenset(
    {
        "pump_vent_valve",
        "pump_drain_valve",
        "vessel_vent_valve",
        "vessel_drain_valve",
        "tank_drain_valve",
        "cv_drain_valve",
        "shell_drain_valve",
        "channel_vent_valve",
        "psv_drain_valve",
        "flush_valve",
        "dbb_bleed_valve",
    }
)

# rule TOG120-CV-BYPASS-NC: the bypass of a control-valve station is closed (Toghraei 2019 p.120)
CV_BYPASS_ROLES = frozenset({"cv_bypass_valve"})

# rule TOG224-PSV-BLOCKS-CSO: PSV blocks are car-sealed open (Toghraei 2019 p.224)
PSV_BLOCK_ROLES = frozenset({"psv_inlet_block", "psv_outlet_block"})

# rule TOG114-BLOCK-DEFAULT-NO: every other blocking valve is normally open (Toghraei 2019 p.114)
#: Includes the root valve of an instrument tap, which only isolates the gauge for maintenance.
BLOCKING_ROLES = frozenset(
    {
        "battery_limit_block",
        "receipt_manifold_valve",
        "tank_inlet_block",
        "tank_outlet_block",
        "tank_fill_block",
        "suction_block",
        "discharge_block",
        "discharge_pi_root",
        "inlet_pi_root",
        "outlet_pi_root",
        "dp_tap_root",
        "steam_supply_pi_root",
        "condensate_pi_root",
        "header_pressure_root",
        "filter_inlet_block",
        "filter_outlet_block",
        "cv_block_in",
        "cv_block_out",
        "min_flow_block",
        "ejector_inlet_block",
        "ejector_outlet_block",
        "utility_supply_block",
        "utility_return_block",
        "condensate_block",
        "pot_inlet_block",
        "pot_outlet_block",
        "trap_block_in",
        "trap_block_out",
        "makeup_gas_block",
        "recycle_gas_block",
        "fuel_gas_block",
        "letdown_outlet_block",
        "side_draw_block",
        "compressor_suction_block",
        "compressor_discharge_block",
        "dosing_isolation_valve",
    }
)

#: manual valves no checked page gives a position: Toghraei states the closed bypass for a control
#: valve only, and a steam-trap bypass is not one
NO_POSITION_ROLES = frozenset({"trap_bypass_valve"})

_POSITION_BY_GROUP: tuple[tuple[frozenset[str], OperatingPosition], ...] = (
    (VENT_DRAIN_ROLES, "NC"),
    (CV_BYPASS_ROLES, "NC"),
    (PSV_BLOCK_ROLES, "CSO"),
    (BLOCKING_ROLES, "NO"),
)


def operating_position_of(role: str) -> OperatingPosition | None:
    """The normal position of the valve with this role; None for a role that has none.

    Raises:
        ValueError: the role is in two groups, which would make the position ambiguous.
    """
    found = [position for roles, position in _POSITION_BY_GROUP if role in roles]
    if len(found) > 1:
        raise ValueError(f"expected role {role!r} in one position group, found {len(found)}")
    return found[0] if found else None


def is_positioned_role(role: str) -> bool:
    """True when the role is a known manual valve (positioned, or deliberately without one)."""
    return operating_position_of(role) is not None or role in NO_POSITION_ROLES


# ---- fail action service ------------------------------------------------------------------------

#: the roles of a pump's minimum-flow valve; Toghraei p.115 says it fails open
MIN_FLOW_VALVE_ROLES = frozenset({"min_flow_control_valve", "min_flow_switch_valve"})
#: the control valve on the exchanger's own branch of a TOG322 pair (its partner is on the bypass)
HX_MAIN_SERVICE = "hx_main_cv"
_COOLING_WATER = frozenset({"CWS", "CWR"})
_STEAM = frozenset({"LPS", "MPS"})
_FUEL_GAS = "FG"


def fail_action_service(
    role: str, kind: ItemKind, fluid_code: str, stream_kind: StreamKindV2 | None
) -> str:
    """The key of `HandbookKnobs.fail_action_table` for an automatic valve.

    Args:
        role: the valve's role.
        kind: `CONTROL_VALVE` or `ON_OFF_VALVE`.
        fluid_code: the service code of the line the valve sits on (`FG`, `CWS`, `LPS`, `P`, ...).
        stream_kind: why that line exists; a control valve on a recycle line is an anti-surge or
            spillback valve.
    """
    if role in MIN_FLOW_VALVE_ROLES:
        # rule TOG114-FAIL-ACTION: a min-flow control valve fails open (Toghraei 2019 p.114–115)
        return "min_flow_fv"
    if role == "hx_main_control_valve":
        return HX_MAIN_SERVICE
    if fluid_code == _FUEL_GAS:
        return "fuel_xv" if kind is ItemKind.ON_OFF_VALVE else "fuel_tv"
    if kind is ItemKind.CONTROL_VALVE:
        return _control_valve_service(fluid_code, stream_kind)
    return "other"


def _control_valve_service(fluid_code: str, stream_kind: StreamKindV2 | None) -> str:
    if fluid_code in _COOLING_WATER:
        return "cooling_water_tv"
    if fluid_code in _STEAM:
        return "steam_tv"
    if stream_kind is StreamKindV2.RECYCLE:
        return "anti_surge_fv"
    return "other"
