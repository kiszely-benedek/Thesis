"""One plant of every T9 pattern: the input of the invariant, determinism and composition tests.

Not a test module (no `test_` prefix). `build_pattern_plant` writes, into one unit of a harness,
three tank farms, three flash drums, three filter packages and standalone pump sets of every pump
class; the second half of each list uses a context with every optional part switched on, so the
cascade, the alarms, the flow loop and the flexible connectors appear.
"""

from __future__ import annotations

import dataclasses

from pattern_harness import PatternHarness

from plantgraph.benchmark.v2.config import InstrumentConvention, InstrumentDensity, TrimConvention
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.pump_set import build_pump_set
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm

_ALL_ON_DENSITY = InstrumentDensity(
    p_optional_instrument=1.0,
    p_point_level_switch=1.0,
    p_bearing_temperature=1.0,
    p_indicator_alarm=1.0,
)


def _all_on(ctx: PatternContext) -> PatternContext:
    """The context with every optional instrument and trim switched on."""
    ctx.trim.config = TrimConvention(
        p_min_flow=1.0,
        p_cv_station=1.0,
        p_cv_reducers=1.0,
        p_cv_drain=1.0,
        p_limit_switches=1.0,
        p_psv_blocks=1.0,
        p_psv_drain=1.0,
        p_battery_limit=1.0,
        p_open_drain=1.0,
        p_flex_connector=1.0,
        p_flush_connection=1.0,
    )
    return dataclasses.replace(
        ctx, instruments=InstrumentConvention(p_cascade=1.0), density=_ALL_ON_DENSITY
    )


def build_pattern_plant(h: PatternHarness) -> list[PatternInstance]:
    """Write every pattern three times with default knobs, then three times with all-on knobs.

    The context is shared, so the all-on switch applies to everything built after it. Pump sets
    of each class follow; they are part of the plant but not pattern instances of their own.
    """
    instances: list[PatternInstance] = []
    for ctx in (h.pctx, _all_on(h.pctx)):
        for _ in range(3):  # three: the deck of the vessel and the tank count cycle once
            for build in (build_tank_farm, build_flash_drum, build_filter_package):
                instance = build(ctx)
                instance.plan.write(h.builder)
                instances.append(instance)
    _write_pump_sets(h)
    return instances


def _write_pump_sets(h: PatternHarness) -> None:
    """A pump set on its own vessel for each pump class."""
    for pump_class in ("CentrifugalPump", "RotaryPump", "ReciprocatingPump"):
        vessel = h.equipment("PressureVessel", "V")
        build_pump_set(h.pctx, vessel, pump_class, "pump").plan.write(h.builder)
