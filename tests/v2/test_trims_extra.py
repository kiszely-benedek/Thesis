"""Part groups of pid-vocabulary 5.4 that trims reuse: flex connector, spool, orifice set."""

from __future__ import annotations

from trim_harness import (
    STYLE,
    TrimHarness,
    assert_round_trip,
    classes_of,
    convention,
    ids_with_role,
    send_to_path,
    sensor_tags_on,
)

from plantgraph.benchmark.v2 import trims, trims_extra
from plantgraph.benchmark.v2.trim_plan import TrimDraft


def test_flexible_connector_sits_at_the_pump_flange_on_both_sides() -> None:
    """Samples W2: a `Compensator` (bellows) at the pump nozzles, chance `p_flex_connector`."""
    h = TrimHarness(config=convention(p_flex_connector=1.0))
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment("CentrifugalPump", "P")
    header = h.equipment("Tank", "TK")
    h.write(trims.centrifugal_suction(h.ctx, STYLE), vessel, pump)
    h.write(trims.pump_discharge(h.ctx, STYLE, False, False, False), pump, header)
    graph = assert_round_trip(h)
    assert classes_of(graph, send_to_path(graph, vessel, pump))[-2] == "Compensator"
    assert classes_of(graph, send_to_path(graph, pump, header))[1] == "Compensator"


def test_no_flexible_connector_when_its_chance_is_zero() -> None:
    h = TrimHarness(config=convention(p_flex_connector=0.0))
    assert trims_extra.flex_connector_items(TrimDraft(h.ctx, STYLE)) == ()


def test_removable_spool_puts_a_flanged_connection_either_side_of_the_strainer() -> None:
    """Every temporary strainer can be unbolted: flange, strainer, flange."""
    h = TrimHarness()
    draft = TrimDraft(h.ctx, STYLE)
    strainer = draft.part("ConicalStrainer", "strainer")
    items = trims_extra.removable_spool_items(draft, strainer)
    assert [item.node_class for item in items] == [
        "FlangedConnection", "ConicalStrainer", "FlangedConnection"
    ]  # fmt: skip
    assert items[0].tag is None and items[2].tag is None  # a flange prints no tag


def test_orifice_flange_set_is_flange_orifice_flange_and_the_orifice_is_tagged_fo() -> None:
    """DEXPI C03: every restriction orifice is drawn between two flanges."""
    h = TrimHarness()
    items = trims_extra.orifice_flange_set_items(TrimDraft(h.ctx, STYLE))
    assert [item.node_class for item in items] == ["Flange", "RestrictionOrifice", "Flange"]
    assert items[1].tag is not None and items[1].tag.startswith("FO-")


def test_header_pressure_tap_is_a_transmitter_with_an_indicator_on_a_blind_flange() -> None:
    """Pump pressure shown once on the header: `PT-n` located on the tap flange feeding `PI-n`."""
    h = TrimHarness()
    src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    draft = TrimDraft(h.ctx, STYLE)
    tee = trims_extra.tee_part(draft, "header_tee")
    h.write(draft.finish(run=(tee,)), src, dst)
    plan = h.write(trims_extra.header_pressure_tap(h.ctx, STYLE, tee.node_id))
    graph = assert_round_trip(h)
    flange = ids_with_role(plan, "header_pressure_flange")[0]
    (transmitter,) = sensor_tags_on(graph, flange)
    indicator = graph.nodes[ids_with_role(plan, "header_pressure_pi")[0]]
    assert transmitter.startswith("PT-") and indicator["tag"].startswith("PI-")
    assert transmitter.partition("-")[2] == indicator["tag"].partition("-")[2]  # one loop number
    assert graph.has_edge(plan.ports["transmitter"], ids_with_role(plan, "header_pressure_pi")[0])
