"""The demo page's static files are served, and every API path its JavaScript calls exists."""

from __future__ import annotations

import re
from typing import cast

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from plantgraph.demo.app.server import STATIC_DIR, create_app
from plantgraph.demo.app.state import AppState

# These routes never touch the state, so a placeholder stands in for it.
APP = create_app(cast(AppState, None))
CLIENT = TestClient(APP)

# a path literal in app.js: "/api/...", "`/corpora/${id}/...`" (stops at a quote, `#` or `?`)
JS_PATH = re.compile(r"""[`"'](/(?:api|corpora)/[^`"'#?]*)""")


def _shape(path: str) -> str:
    """Make `${expr}` (JavaScript) and `{name}` (FastAPI) both read `{}`."""
    return re.sub(r"\$\{[^}]*\}|\{[^}]*\}", "{}", path)


def test_the_root_serves_the_page_that_links_its_assets() -> None:
    response = CLIENT.get("/")

    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    assert "/static/app.js" in response.text and "/static/app.css" in response.text


def test_the_static_assets_are_served() -> None:
    for name, media in (("app.js", "javascript"), ("app.css", "text/css")):
        response = CLIENT.get(f"/static/{name}")
        assert response.status_code == 200 and media in response.headers["content-type"]
        assert response.content == (STATIC_DIR / name).read_bytes()


def test_every_api_path_the_javascript_calls_exists_in_the_router() -> None:
    called = {_shape(path) for path in JS_PATH.findall((STATIC_DIR / "app.js").read_text("utf-8"))}
    served = {_shape(r.path) for r in APP.routes if isinstance(r, APIRoute)}

    assert called, "expected app.js to call the API, found no path literal"
    assert called <= served, f"app.js calls paths the server lacks: {sorted(called - served)}"


def test_the_page_has_no_per_question_payment_dialog() -> None:
    page = CLIENT.get("/").text
    script = (STATIC_DIR / "app.js").read_text("utf-8")

    assert "<dialog" not in page and "allow_paid" not in script
