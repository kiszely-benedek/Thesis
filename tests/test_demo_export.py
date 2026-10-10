"""Tests for the export: files written, sidecar report, determinism, acceptance checks."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
from pypdf import PdfReader

from demo_drawing_toy import toy_resolution, toy_sheets
from plantgraph.demo.drawing.export import INDEX_NAME, PDF_NAME, export_drawings
from plantgraph.demo.drawing.models import DrawingIndex

_DRAWING_DIR = Path(__file__).resolve().parent.parent / "src" / "plantgraph" / "demo" / "drawing"
_DRAWING_FILES = tuple(sorted(_DRAWING_DIR.glob("*.py")))
_BANNED_MODULES = (
    "plantgraph.benchmark.splitter",
    "plantgraph.benchmark.rejoin",
    "plantgraph.qa.questions",
    "plantgraph.eval",
)
_BANNED_NAMES = frozenset({"GoldCorpusData", "SplitManifest", "OccurrenceMap"})
_LOADER_MODULE = "plantgraph.qa.corpus"  # holds GoldCorpusData; only the CLI may load through it


def test_export_writes_pdf_and_sidecar(tmp_path: Path) -> None:
    sheets = toy_sheets()
    index = export_drawings("TOY", sheets, toy_resolution(sheets), tmp_path)

    pdf_path = tmp_path / "TOY" / PDF_NAME
    sidecar = DrawingIndex.model_validate_json((tmp_path / "TOY" / INDEX_NAME).read_text("utf-8"))
    assert sidecar == index
    assert len(PdfReader(pdf_path).pages) == 3
    assert index.pdf_sha256 == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert index.pages == {"2": 1, "10": 2, "A": 3}


def test_report_numbers_equal_the_corpus(tmp_path: Path) -> None:
    sheets = toy_sheets()
    resolution = toy_resolution(sheets)
    report = export_drawings("TOY", sheets, resolution, tmp_path).report
    assert report.pages == len(sheets)
    assert report.symbols == resolution.report.n_occurrences
    assert report.flags == resolution.report.n_connectors
    assert report.lines == sum(sheet.graph.number_of_edges() for sheet in sheets)
    assert (report.flags_linked, report.dangling_flags) == (3, 1)
    assert (report.overlaps, report.foreign_crossings) == (0, 0)
    assert report.min_scale == 1.0


def test_two_exports_give_byte_identical_pdfs(tmp_path: Path) -> None:
    sheets = toy_sheets()
    export_drawings("TOY", sheets, toy_resolution(sheets), tmp_path / "first")
    export_drawings("TOY", sheets, toy_resolution(sheets), tmp_path / "second")
    first = (tmp_path / "first" / "TOY" / PDF_NAME).read_bytes()
    assert first == (tmp_path / "second" / "TOY" / PDF_NAME).read_bytes()


def test_export_refuses_a_drawing_that_does_not_match_the_corpus(tmp_path: Path) -> None:
    sheets = toy_sheets()
    resolution = toy_resolution(sheets)
    resolution.report.n_occurrences += 1  # the resolver claims a symbol the drawing lacks
    with pytest.raises(ValueError, match="symbols"):
        export_drawings("TOY", sheets, resolution, tmp_path)


def _imports(path: Path) -> tuple[set[str], set[str]]:
    """Every dotted module path imported (also `from pkg import module`) and every imported name."""
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            names.update(alias.name for alias in node.names)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules, names


def _is_under(module: str, banned: str) -> bool:
    return module == banned or module.startswith(f"{banned}.")


def test_the_drawing_package_is_found_by_the_glob() -> None:
    names = {path.name for path in _DRAWING_FILES}
    assert names >= {"layout.py", "render_pdf.py", "export.py", "glyphs.py", "__main__.py"}


@pytest.mark.parametrize("path", _DRAWING_FILES, ids=lambda path: path.name)
def test_drawing_code_never_imports_the_answer_key(path: Path) -> None:
    modules, names = _imports(path)
    banned = _BANNED_MODULES if path.name == "__main__.py" else (*_BANNED_MODULES, _LOADER_MODULE)
    found = {m for m in modules for b in banned if _is_under(m, b)}
    assert not found, f"{path.name} imports banned module(s) {found}"
    assert not names & _BANNED_NAMES, f"{path.name} imports the answer key: {names & _BANNED_NAMES}"
