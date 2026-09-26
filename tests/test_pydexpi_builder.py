"""Direct tests of `DexpiPlantBuilder` (`plant-generator.md` §3.5).

Only what looks at `DexpiPlantBuilder` itself belongs here (the shape of the
pyDEXPI objects, segment construction, the sensing-nozzle rule) — the full
generator -> `DiGraph` path is covered by `test_pydexpi_adapter.py`.
"""

from __future__ import annotations

import pytest
from pydexpi.loaders.graph_loader import GraphAbstractor, GraphLoader

from plantgraph.adapters.pydexpi_builder import DexpiPlantBuilder
from plantgraph.benchmark.generator_models import LoopSpec, ValveSpec


def _two_equipment_builder() -> DexpiPlantBuilder:
    """A builder holding one unit with a tank and a pump in it — no stream yet."""
    builder = DexpiPlantBuilder("plant0")
    builder.add_section(unit_no=1)
    builder.add_equipment(
        node_id="plant0-u1-eq1",
        node_class="Tank",
        unit_no=1,
        tag="TK-1-1",
        tag_prefix="TK",
        tag_seq=1,
    )
    builder.add_equipment(
        node_id="plant0-u1-eq2",
        node_class="CentrifugalPump",
        unit_no=1,
        tag="P-1-1",
        tag_prefix="P",
        tag_seq=1,
    )
    return builder


# ---- stream valve count -----------------------------------------------------------------


@pytest.mark.parametrize("n_valves", [0, 1, 2])
def test_stream_carries_the_requested_number_of_valves(n_valves: int) -> None:
    builder = _two_equipment_builder()
    valves = [
        ValveSpec(node_id=f"plant0-u1-va{i}", node_class="GlobeValve", tag=f"GV-1-{i}")
        for i in range(1, n_valves + 1)
    ]
    builder.add_stream(
        line_number="PL-1",
        fluid_code="PL",
        src_id="plant0-u1-eq1",
        dst_id="plant0-u1-eq2",
        valves=valves,
    )
    model = builder.build()

    system = model.conceptualModel.pipingNetworkSystems[0]
    segment = system.segments[0]
    # the segment's items are the valves; the pipe count is always one more (§3.5:
    # "len(pipes) = len(valves) + 1"), because the open ends need closing too
    assert len(segment.items) == n_valves
    assert len(segment.connections) == n_valves + 1
    tags = [item.pipingComponentNumber for item in segment.items]
    assert tags == [valve.tag for valve in valves]


# ---- dedicated sensing nozzle -------------------------------------------------------------


def test_sensing_location_is_a_dedicated_nozzle_distinct_from_the_stream_nozzle() -> None:
    builder = _two_equipment_builder()
    valve = ValveSpec(node_id="plant0-u1-va1", node_class="GlobeValve", tag="GV-1-1")
    builder.add_stream(
        line_number="PL-1",
        fluid_code="PL",
        src_id="plant0-u1-eq1",
        dst_id="plant0-u1-eq2",
        valves=[valve],
    )
    loop = LoopSpec(
        equipment_id="plant0-u1-eq1",
        valve_id="plant0-u1-va1",
        variable="L",
        unit_no=1,
        loop_no=1,
        psgf_id="plant0-u1-in1",
        pif_id="plant0-u1-in2",
        af_id="plant0-u1-in3",
    )
    builder.add_control_loop(loop)
    model = builder.build()

    tank = model.conceptualModel.taggedPlantItems[0]
    pif = model.conceptualModel.processInstrumentationFunctions[0]
    psgf = pif.processSignalGeneratingFunctions[0]
    # the tank has two nozzles: one at the end of the stream, the other for sensing only
    assert len(tank.nozzles) == 2
    assert psgf.sensingLocation is tank.nozzles[1]
    assert psgf.sensingLocation is not tank.nozzles[0]


def test_dedicated_sensing_nozzle_keeps_both_the_pipe_and_the_sensing_edge() -> None:
    """Verified for §3.5: on a shared nozzle, pyDEXPI's abstraction would swallow both edges."""
    builder = _two_equipment_builder()
    valve = ValveSpec(node_id="plant0-u1-va1", node_class="GlobeValve", tag="GV-1-1")
    builder.add_stream(
        line_number="PL-1",
        fluid_code="PL",
        src_id="plant0-u1-eq1",
        dst_id="plant0-u1-eq2",
        valves=[valve],
    )
    loop = LoopSpec(
        equipment_id="plant0-u1-eq1",
        valve_id="plant0-u1-va1",
        variable="L",
        unit_no=1,
        loop_no=1,
        psgf_id="plant0-u1-in1",
        pif_id="plant0-u1-in2",
        af_id="plant0-u1-in3",
    )
    builder.add_control_loop(loop)
    model = builder.build()

    complete = GraphLoader().dexpi_to_graph(model)
    conceptual = GraphAbstractor.build_conceptual_graph(complete)

    has_pipe_edge = any(
        d.get("label") == "Pipe" and u == "plant0-u1-eq1" and v == "plant0-u1-va1"
        for u, v, d in conceptual.edges(data=True)
    )
    has_sensing_edge = any(
        d.get("attr_name") == "sensingLocation" and v == "plant0-u1-eq1"
        for _, v, d in conceptual.edges(data=True)
    )
    assert has_pipe_edge, "the tank -> valve pipe edge should survive alongside the sensing edge"
    assert has_sensing_edge, "the PSGF -> tank sensing edge should survive"


# ---- identifiers: no uuid ---------------------------------------------------------------


def test_backend_version_matches_the_installed_pydexpi() -> None:
    import importlib.metadata

    builder = DexpiPlantBuilder("plant0")
    assert builder.backend_version == importlib.metadata.version("pydexpi")


def test_add_stream_raises_on_an_unknown_equipment_id() -> None:
    builder = _two_equipment_builder()
    with pytest.raises(ValueError, match="never added via add_equipment"):
        builder.add_stream(
            line_number="PL-1",
            fluid_code="PL",
            src_id="not-an-id",
            dst_id="plant0-u1-eq2",
            valves=[],
        )
