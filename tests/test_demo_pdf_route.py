"""The drawing-PDF route and the viewer's versioned URL (DP-T8), without a model or a database."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from plantgraph.demo.app.server import PDF_CACHE_CONTROL, STATIC_DIR, create_app
from plantgraph.demo.app.state import AppState, UnknownCorpus

PDF_BYTES = b"%PDF-1.4\n" + b"x" * 200 + b"\n%%EOF\n"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    pdf = tmp_path / "drawings.pdf"
    pdf.write_bytes(PDF_BYTES)

    def configured_corpus(corpus_id: str) -> SimpleNamespace:
        if corpus_id != "D1":
            raise UnknownCorpus(f"unknown corpus {corpus_id}")
        return SimpleNamespace(pdf_path=pdf)

    # the route only calls `configured_corpus`, so a stand-in for the whole state is enough
    state = cast(AppState, SimpleNamespace(configured_corpus=configured_corpus))
    return TestClient(create_app(state))


def test_pdf_is_inline_and_cacheable(client: TestClient) -> None:
    response = client.get("/corpora/D1/drawings.pdf?v=abc")

    assert response.status_code == 200 and response.content == PDF_BYTES
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["cache-control"] == PDF_CACHE_CONTROL == "private, max-age=86400"


def test_the_version_query_does_not_change_the_file(client: TestClient) -> None:
    plain = client.get("/corpora/D1/drawings.pdf")
    versioned = client.get("/corpora/D1/drawings.pdf?v=other")

    assert plain.content == versioned.content


def test_a_byte_range_is_served(client: TestClient) -> None:
    # the browsers' PDF viewers fetch the file in ranges
    response = client.get("/corpora/D1/drawings.pdf", headers={"Range": "bytes=0-8"})

    assert response.status_code == 206 and response.content == PDF_BYTES[:9]


def test_unknown_plant_has_no_pdf(client: TestClient) -> None:
    assert client.get("/corpora/NOPE/drawings.pdf").status_code == 404


def test_the_viewer_builds_a_versioned_page_url_in_a_fresh_iframe() -> None:
    source = (STATIC_DIR / "viewer.js").read_text("utf-8")

    assert "drawings.pdf?v=${PDF_VERSION}" in source
    assert "#page=${pageNumber}" in source
    assert "replaceChildren(frame)" in source  # a new iframe per jump, not a hash-only change
