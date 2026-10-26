"""A line may start at the last part of another line: how the flowsheet joins two units."""

from __future__ import annotations

import pytest
from pattern_harness import PatternHarness
from trim_harness import assert_round_trip

from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import with_in_port_source
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec
from plantgraph.graph.schema import Relation


def test_a_joined_port_pair_gives_the_cross_unit_edge_and_drops_nothing() -> None:
    h = PatternHarness()
    drum = build_flash_drum(h.pctx)
    package = with_in_port_source(build_filter_package(h.pctx), "feed", drum.port("liquid").node_id)
    h.build(drum)
    h.build(package)
    graph = assert_round_trip(h)  # DEXPI graph == oracle graph, nothing dropped, valid
    edge = graph.edges[drum.port("liquid").node_id, package.port("feed").node_id]
    assert edge["relation"] == Relation.SEND_TO.value


def test_a_line_end_naming_an_unknown_part_is_refused_with_the_expected_kinds() -> None:
    builder = DexpiPlantBuilderV2("plant0")
    builder.add_section(1, "TKF test")
    stray = LineSpec(
        line_number="6-P-10001-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="nowhere",
        dst_id=None,
        items=(LineItemSpec(node_id="v1", node_class="GateValve", tag="HV-10001"),),
    )
    with pytest.raises(ValueError, match="inline part of a line added earlier.*'nowhere'"):
        builder.add_line(stray)
