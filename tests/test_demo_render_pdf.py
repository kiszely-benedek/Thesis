"""Tests for the PDF renderer: pages, searchable text, bookmarks, flag links, determinism."""

from __future__ import annotations

import io
import re
from typing import Any

import pytest
from pypdf import PdfReader

from demo_drawing_toy import toy_sheets
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing import SheetLayout, layout_sheet
from plantgraph.demo.drawing.glyphs import MIN_TEXT_PT
from plantgraph.demo.drawing.render_pdf import (
    BOOKMARK_GROUP_SIZE,
    RenderedPdf,
    render_drawing_set,
    sheet_order_key,
)


def toy_layouts() -> list[SheetLayout]:
    return [layout_sheet(sheet) for sheet in toy_sheets()]


def read(rendered: RenderedPdf) -> PdfReader:
    return PdfReader(io.BytesIO(rendered.data))


def expected_strings(sheet: SheetGraph) -> set[str]:
    """Every tag, loop tag, flag target and line number the page must show."""
    strings = {f"DWG {sheet.sheet_id}"}
    for _, attrs in sheet.graph.nodes(data=True):
        strings |= {str(attrs[key]) for key in ("tag", "loop_tag") if key in attrs}
        if "referenced_drawing_number" in attrs:
            strings.add(f"DWG {attrs['referenced_drawing_number']}")
    for _, _, attrs in sheet.graph.edges(data=True):
        if "line_number" in attrs:
            strings.add(str(attrs["line_number"]))
    return strings


def flatten_outline(items: list[Any]) -> list[tuple[int, str]]:
    """(depth, title) of every bookmark in document order."""
    flat: list[tuple[int, str]] = []

    def walk(entries: list[Any], depth: int) -> None:
        for entry in entries:
            if isinstance(entry, list):
                walk(entry, depth + 1)
            else:
                flat.append((depth, str(entry.title)))

    walk(items, 0)
    return flat


def link_targets(reader: PdfReader, page_number: int) -> list[int]:
    """The 1-based target page of every link annotation on a page."""
    page_ids = [page.indirect_reference.idnum for page in reader.pages]
    annotations = reader.pages[page_number - 1].get("/Annots", [])
    return [page_ids.index(a.get_object()["/Dest"][0].idnum) + 1 for a in annotations]


def test_one_page_per_sheet_in_natural_order() -> None:
    rendered = render_drawing_set("TOY", toy_layouts())
    assert len(read(rendered).pages) == 3
    assert rendered.pages == {"2": 1, "10": 2, "A": 3}
    assert sheet_order_key("2") < sheet_order_key("10") < sheet_order_key("A")


def test_page_text_has_every_tag_loop_tag_flag_target_and_line_number() -> None:
    rendered = render_drawing_set("TOY", toy_layouts())
    reader = read(rendered)
    by_id = {sheet.sheet_id: sheet for sheet in toy_sheets()}
    for sheet_id, page_number in rendered.pages.items():
        text = reader.pages[page_number - 1].extract_text()
        missing = {s for s in expected_strings(by_id[sheet_id]) if s not in text}
        assert not missing, f"sheet {sheet_id}: missing from page text: {missing}"


def test_bookmarks_are_in_page_order() -> None:
    reader = read(render_drawing_set("TOY", toy_layouts()))
    assert flatten_outline(reader.outline) == [
        (0, "DWG 2 - A"),
        (1, "DWG 2 - units U1"),
        (1, "DWG 10 - units U1"),
        (1, "DWG A - units U1"),
    ]


def test_bookmarks_are_grouped_by_hundreds() -> None:
    base = layout_sheet(toy_sheets()[0])
    layouts = [base.model_copy(update={"sheet_id": str(n)}) for n in range(250)]
    outline = flatten_outline(read(render_drawing_set("BIG", layouts)).outline)
    groups = [title for depth, title in outline if depth == 0]
    assert BOOKMARK_GROUP_SIZE == 100
    assert groups == ["DWG 0 - 99", "DWG 100 - 199", "DWG 200 - 249"]
    assert len(outline) == 250 + 3


def test_each_in_corpus_flag_links_to_its_target_page_and_the_dangling_one_does_not() -> None:
    rendered = render_drawing_set("TOY", toy_layouts())
    reader = read(rendered)
    # sheet "2" (page 1): the pipe flag and the signal flag both point at sheet "10" (page 2)
    assert link_targets(reader, 1) == [2, 2]
    # sheet "10" (page 2): the in flag points back at sheet "2"; the flag to "99" has no link
    assert link_targets(reader, 2) == [1]
    assert link_targets(reader, 3) == []
    assert (rendered.flags, rendered.flags_linked, rendered.dangling_flags) == (4, 3, 1)


def test_the_dangling_flag_is_still_drawn_with_its_target_text() -> None:
    reader = read(render_drawing_set("TOY", toy_layouts()))
    assert "TO DWG 99" in reader.pages[1].extract_text()


def test_counts_match_the_layouts() -> None:
    layouts = toy_layouts()
    rendered = render_drawing_set("TOY", layouts)
    assert rendered.symbols == sum(len(layout.symbols) for layout in layouts)
    assert rendered.lines == sum(len(layout.lines) for layout in layouts)
    assert rendered.min_scale == 1.0


def test_two_renders_are_byte_identical() -> None:
    first = render_drawing_set("TOY", toy_layouts())
    second = render_drawing_set("TOY", toy_layouts())
    assert first.data == second.data


def test_the_page_is_a3_landscape() -> None:
    page = read(render_drawing_set("TOY", toy_layouts())).pages[0]
    assert (round(float(page.mediabox.width)), round(float(page.mediabox.height))) == (1190, 842)


def test_repeated_sheet_ids_are_refused() -> None:
    layout = toy_layouts()[0]
    with pytest.raises(ValueError, match="unique"):
        render_drawing_set("TOY", [layout, layout])


def test_text_never_goes_below_the_four_point_floor() -> None:
    crowded = [layout.model_copy(update={"scale": 0.3}) for layout in toy_layouts()]
    reader = read(render_drawing_set("TOY", crowded))
    sizes = []
    for page in reader.pages:
        content = page.get_contents()
        assert content is not None
        sizes += [float(s) for s in re.findall(rb"/F\d+ ([\d.]+) Tf", content.get_data())]
    assert sizes
    assert min(sizes) >= MIN_TEXT_PT
