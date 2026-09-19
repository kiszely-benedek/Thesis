"""A pyDEXPI JSON és Proteus perzisztencia tesztjei (`plant-generator.md` §3.7).

A JSON kerek-út a teljes gráfra nézve `test_pydexpi_adapter.py`-ban van
(invariáns 13); itt csak azt ellenőrizzük, amit ez a modul ad hozzá: a
típus-igazolást betöltéskor, és hogy a Proteus export tényleg csak berendezést
ír vissza — ahogy a modul docstringje mondja, nem többet.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.adapters.pydexpi_adapter import plant_graph
from plantgraph.adapters.pydexpi_builder import GeneratedPlant, generate_plant
from plantgraph.adapters.pydexpi_io import (
    load_json,
    load_proteus_equipment_only,
    save_json,
    save_proteus_equipment_only,
)
from plantgraph.benchmark.generator_models import GeneratorConfig


def test_json_round_trip_keeps_every_tag(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=1))
    save_json(generated.model, tmp_path, "plant")
    loaded_model = load_json(tmp_path, "plant")

    original_items = generated.model.conceptualModel.taggedPlantItems
    loaded_items = loaded_model.conceptualModel.taggedPlantItems
    original_tags = {item.id: item.tagName for item in original_items}
    loaded_tags = {item.id: item.tagName for item in loaded_items}
    assert loaded_tags == original_tags


def test_proteus_export_carries_equipment_but_drops_piping_and_instrumentation(
    tmp_path: Path,
) -> None:
    generated = generate_plant(GeneratorConfig(seed=1))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")
    reloaded = load_proteus_equipment_only(tmp_path, "plant")

    original_tags = {item.tagName for item in generated.model.conceptualModel.taggedPlantItems}
    reloaded_tags = {item.tagName for item in reloaded.conceptualModel.taggedPlantItems}
    assert reloaded_tags == original_tags

    # §3.7, mérve: a Proteus exporter csak a taggedPlantItems-en iterál —
    # a csővezeték és a műszerezés nem éli túl az exportot
    assert reloaded.conceptualModel.pipingNetworkSystems == []
    assert reloaded.conceptualModel.processInstrumentationFunctions == []


def test_proteus_reloaded_equipment_still_yields_a_schema_valid_but_edgeless_plant_graph(
    tmp_path: Path,
) -> None:
    generated = generate_plant(GeneratorConfig(seed=1))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")
    reloaded = load_proteus_equipment_only(tmp_path, "plant")

    plant, report = plant_graph(GeneratedPlant(model=reloaded, record=generated.record))
    assert plant.number_of_edges() == 0
    assert plant.number_of_nodes() == len(generated.model.conceptualModel.taggedPlantItems)
    assert report.nodes_mapped == plant.number_of_nodes()
