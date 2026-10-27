"""Tests for the ISO-style glyphs: every class has a symbol; v2 sheets lay out and render."""

from __future__ import annotations

import io
from functools import cache
from pathlib import Path

import pytest
from pypdf import PdfReader

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.demo.drawing.export import export_drawings
from plantgraph.demo.drawing.families import family_of
from plantgraph.demo.drawing.geometry import count_foreign_crossings, count_overlaps
from plantgraph.demo.drawing.glyph_families import GLYPH_FAMILIES, glyph_of, glyph_style_for
from plantgraph.demo.drawing.glyphs_iso import DRAWERS
from plantgraph.demo.drawing.layout import layout_sheet
from plantgraph.demo.drawing.models import LayoutConfig
from plantgraph.demo.drawing.render_pdf import render_drawing_set
from plantgraph.demo.drawing.specimen import specimen_sheets
from plantgraph.graph import schema
from plantgraph.graph.schema_vocabulary import VOCABULARY
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus

#: Flags are drawn by the shared flag glyph, in both styles, so they have no drawer of their own.
FLAG_GLYPH = "off_page_flag"
DRAWN_CLASSES = [row.name for row in VOCABULARY] + [schema.NodeClass.GENERIC_ITEM.value]


@cache
def v2_corpus() -> SyntheticCorpus:
    preset = HeadlinePresetV2()
    n_units = smallest_n_units_v2(10, preset, 1).n_units
    return build_synthetic_corpus(preset.generator_config(n_units, 1), preset.split_config(1))


def test_the_vocabulary_has_98_classes() -> None:
    assert len(VOCABULARY) == 98


@pytest.mark.parametrize("node_class", DRAWN_CLASSES)
def test_every_class_resolves_to_a_family_and_a_drawable_glyph(node_class: str) -> None:
    family_of(node_class)  # raises if the layout cannot place it
    glyph = glyph_of(node_class)
    assert glyph == FLAG_GLYPH or glyph in DRAWERS, f"{node_class} -> {glyph} has no drawer"


def test_every_named_glyph_has_a_drawer() -> None:
    missing = {g for g in GLYPH_FAMILIES.values() if g not in DRAWERS}
    assert not missing


def test_structural_classes_are_not_drawn() -> None:
    with pytest.raises(ValueError, match="cannot draw"):
        family_of(schema.NodeClass.SHEET.value)


def test_every_generated_class_has_its_own_glyph() -> None:
    emitted = {
        attrs["node_class"]
        for sheet in v2_corpus().localized_sheets
        for _, attrs in sheet.graph.nodes(data=True)
    }
    generated = {n for n in emitted | GENERATED_EQUIPMENT_CLASSES if glyph_of(n) != FLAG_GLYPH}
    # "own glyph" = the class or one of its ancestors is listed in the table, not a kind fallback
    unlisted = {
        name
        for name in generated
        if not any(label in GLYPH_FAMILIES for label in schema.labels_for(name))
    }
    assert not unlisted, f"drawn by a fallback rule: {sorted(unlisted)}"
    assert "equipment_box" not in {glyph_of(name) for name in generated}


def test_sibling_valves_and_exchangers_are_told_apart() -> None:
    names = ["GateValve", "GlobeValve", "BallValve", "ButterflyValve", "PlugValve", "NeedleValve"]
    assert len({glyph_of(name) for name in names}) == len(names)
    assert glyph_of("PlateHeatExchanger") != glyph_of("TubularHeatExchanger")


def test_style_is_classic_for_v1_classes_and_iso_beyond_them() -> None:
    assert glyph_style_for(["CentrifugalPump", "GlobeValve", "Tank"]) == "classic"
    assert glyph_style_for(["CentrifugalPump", "PipeTee"]) == "iso"


def test_v2_sheets_lay_out_without_overlaps_or_foreign_crossings() -> None:
    config = LayoutConfig(glyph_style="iso")
    for sheet in v2_corpus().localized_sheets:
        layout = layout_sheet(sheet, config)
        assert count_overlaps(layout) == 0, sheet.sheet_id
        assert count_foreign_crossings(layout) == 0, sheet.sheet_id


def test_v2_export_picks_the_iso_style_and_passes_its_own_checks(tmp_path: Path) -> None:
    corpus = v2_corpus()
    index = export_drawings("V2", corpus.localized_sheets, corpus.resolution, tmp_path)
    assert index.report.overlaps == 0
    assert index.report.symbols == corpus.resolution.report.n_occurrences
    reader = PdfReader(tmp_path / "V2" / "drawings.pdf")
    text = reader.pages[0].extract_text()
    assert "DWG 0" in text


def test_the_specimen_draws_every_class_and_writes_a_pdf() -> None:
    config = LayoutConfig(glyph_style="iso")
    layouts = [layout_sheet(sheet, config) for sheet in specimen_sheets()]
    drawn = {symbol.node_class for layout in layouts for symbol in layout.symbols}
    assert {n for n in DRAWN_CLASSES if family_of(n) not in ("pipe_flag", "signal_flag")} <= drawn
    rendered = render_drawing_set("SPECIMEN", layouts, config)
    assert len(PdfReader(io.BytesIO(rendered.data)).pages) == len(layouts)
    assert sum(count_overlaps(layout) for layout in layouts) == 0
