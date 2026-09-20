"""A `DexpiPlantBuilder` közvetlen tesztjei (`plant-generator.md` §3.5).

Ide csak az kell, ami a `DexpiPlantBuilder`-t magát nézi (a pyDEXPI-objektumok
alakja, a szegmens-felépítés, az érzékelő fúvóka szabálya) — a teljes
generátor -> `DiGraph` útvonalat `test_pydexpi_adapter.py` fedi.
"""

from __future__ import annotations

import pytest
from pydexpi.loaders.graph_loader import GraphAbstractor, GraphLoader

from plantgraph.adapters.pydexpi_builder import DexpiPlantBuilder
from plantgraph.benchmark.generator_models import LoopSpec, ValveSpec


def _two_equipment_builder() -> DexpiPlantBuilder:
    """Egy egységet, benne egy tankot és egy szivattyút tartalmazó builder — még áram nélkül."""
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


# ---- stream szelepszáma -----------------------------------------------------------------


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
    # a szegmens elemei a szelepek; a pipe-ok száma mindig eggyel több (§3.5:
    # "len(pipes) = len(valves) + 1"), mert a nyitott végeket is le kell zárni
    assert len(segment.items) == n_valves
    assert len(segment.connections) == n_valves + 1
    tags = [item.pipingComponentNumber for item in segment.items]
    assert tags == [valve.tag for valve in valves]


# ---- dedikált érzékelő fúvóka -------------------------------------------------------------


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
    # a tanknak két fúvókája van: az egyik a stream végén, a másik csak az érzékeléshez
    assert len(tank.nozzles) == 2
    assert psgf.sensingLocation is tank.nozzles[1]
    assert psgf.sensingLocation is not tank.nozzles[0]


def test_dedicated_sensing_nozzle_keeps_both_the_pipe_and_the_sensing_edge() -> None:
    """A §3.5 mérése: egy megosztott fúvókán pyDEXPI absztrakciója elnyelte volna mindkét élt."""
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


# ---- azonosítók: nincs uuid ---------------------------------------------------------------


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
