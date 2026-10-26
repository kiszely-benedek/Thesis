"""Every trim in one plant: the input of the determinism and the whole-plant round-trip tests.

Not a test module (no `test_` prefix). `ALL_ON` switches every optional part on; the repeated calls
deal each role deck through all of its classes.
"""

from __future__ import annotations

from trim_harness import STYLE, TrimHarness

from plantgraph.benchmark.v2 import trims, trims_extra, trims_utility, trims_valves, trims_vessel
from plantgraph.benchmark.v2.trim_plan import TrimDraft

ALL_ON: dict[str, object] = {
    "p_pump_vent_drain": 1.0,
    "p_min_flow": 1.0,
    "p_cv_station": 1.0,
    "p_cv_reducers": 1.0,
    "p_cv_drain": 1.0,
    "p_limit_switches": 1.0,
    "p_psv_blocks": 1.0,
    "p_psv_drain": 1.0,
    "p_thermal_relief": 1.0,
    "p_exchanger_vent_drain": 1.0,
    "p_battery_limit": 1.0,
    "p_open_drain": 1.0,
    "p_skillet": 1.0,
    "p_flex_connector": 1.0,
    "p_flush_connection": 1.0,
}


def _line_between_hosts(h: TrimHarness, make: object) -> None:
    """Close the `run` of the plan `make(h)` into a line between two fresh hosts."""
    src = h.equipment("PressureVessel", "V")
    dst = h.equipment("Tank", "TK")
    h.write(make(h), src, dst)  # type: ignore[operator]


def _tee_on_a_line(h: TrimHarness) -> str:
    """A line with a tee on it, for trims that start at a tee; returns the tee's id."""
    draft = TrimDraft(h.ctx, STYLE)
    tee = trims_extra.tee_part(draft, "host_tee")
    src = h.equipment("PressureVessel", "V")
    dst = h.equipment("Tank", "TK")
    h.write(draft.finish(run=(tee,)), src, dst)
    return tee.node_id


def _pumps(h: TrimHarness) -> None:
    vessel = h.equipment("PressureVessel", "V")
    sink = h.equipment("Tank", "TK")
    for pump_class in ("CentrifugalPump", "RotaryPump", "ReciprocatingPump"):
        pump = h.equipment(pump_class, "P")
        h.write(trims.pump_trims(h.ctx, STYLE, pump, pump_class, vessel, sink))
    header = _tee_on_a_line(h)
    h.write(trims_extra.header_pressure_tap(h.ctx, STYLE, header))


def _compressor(h: TrimHarness) -> None:
    drum = h.equipment("PressureVessel", "V")
    machine = h.equipment("CentrifugalCompressor", "K")
    after = h.equipment("PressureVessel", "V")
    h.write(trims.compressor_suction(h.ctx, STYLE), drum, machine)
    h.write(trims.compressor_discharge(h.ctx, STYLE), machine, after)


def _valves(h: TrimHarness) -> None:
    for _ in range(4):  # the control-valve decks hold four cards
        _line_between_hosts(h, lambda h: trims_valves.control_valve(h.ctx, STYLE, "F"))
        _line_between_hosts(h, lambda h: trims_valves.control_valve(h.ctx, STYLE, "L", True))
        _line_between_hosts(h, lambda h: trims_valves.flow_element(h.ctx, STYLE, "gas"))
    for _ in range(3):
        _line_between_hosts(h, lambda h: trims_valves.flow_element(h.ctx, STYLE, "liquid"))
        _line_between_hosts(h, lambda h: trims_valves.battery_limit(h.ctx, STYLE))
        _line_between_hosts(h, lambda h: trims_extra.sight_glass(h.ctx, STYLE))
        _line_between_hosts(h, lambda h: trims_extra.dosing_isolation(h.ctx, STYLE))
    _line_between_hosts(h, lambda h: trims_valves.on_off_valve(h.ctx, STYLE))
    _line_between_hosts(h, lambda h: trims_valves.double_block_and_bleed(h.ctx, STYLE))
    for _ in range(2):
        _line_between_hosts(h, lambda h: trims_extra.skillet_blind(h.ctx, STYLE))
    _line_between_hosts(h, lambda h: trims_extra.spec_break(h.ctx, STYLE))


def _vessels(h: TrimHarness) -> None:
    for vessel_class in ("PressureVessel", "ProcessColumn", "GravitationalSeparator"):
        vessel = h.equipment(vessel_class)
        sink = h.equipment("Tank", "TK")
        h.write(trims_vessel.vessel_trims(h.ctx, STYLE, vessel, vessel_class), vessel, sink)
    for flammable in (True, False):
        tank = h.equipment("Tank", "TK")
        h.write(trims_vessel.tank_vent(h.ctx, STYLE, tank, flammable))
        h.write(trims_extra.tank_bottom_drain(h.ctx, STYLE, tank, viscous=not flammable))
    for _ in range(3):  # the PSV deck holds three cards
        vessel = h.equipment("PressureVessel", "V")
        h.write(trims_vessel.vessel_psv(h.ctx, STYLE, vessel))


def _exchangers(h: TrimHarness) -> None:
    cooler = h.equipment("TubularHeatExchanger", "E")
    h.write(trims_utility.utility_supply_stub(h.ctx, STYLE, "CWS", cooler))
    h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "CWS", cooler))
    h.write(trims_utility.exchanger_vent_drain(h.ctx, STYLE, cooler))
    for mode in ("trap", "trap_station", "drain_pot"):  # one steam exchanger per condensate mode
        weights = {mode: 1.0}
        h.ctx.config = h.ctx.config.model_copy(update={"condensate_mode_weights": weights})
        heater = h.equipment("TubularHeatExchanger", "E")
        supply = trims_utility.utility_supply_stub(h.ctx, STYLE, "LPS", heater, relief_tee=True)
        h.write(supply)
        h.write(trims_utility.steam_stub_relief(h.ctx, STYLE, supply.ports["relief_tee"]))
        h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "LPS", heater))
    ejector = h.equipment("AirEjector", "EJ")
    h.write(trims_utility.ejector_discharge_silencer(h.ctx, STYLE, ejector))


def build_everything(h: TrimHarness) -> None:
    """Write every trim, at least once, to the harness's backends."""
    _pumps(h)
    _compressor(h)
    _valves(h)
    _vessels(h)
    _exchangers(h)
