"""The demo page's static files: served, wired together, and consistent with the server and labels.

JavaScript has no test runner here, so these are string scans over `static/` that catch the usual
slips: a called API path the server lacks, a missing label or string, a module nobody imports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from plantgraph.demo.app.server import STATIC_DIR, create_app
from plantgraph.demo.app.state import AppState

# These routes never touch the state, so a placeholder stands in for it.
APP = create_app(cast(AppState, None))
CLIENT = TestClient(APP)

MODULES = sorted(STATIC_DIR.glob("*.js"))
ALL_FILES = sorted(p for p in STATIC_DIR.iterdir() if p.is_file())
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

# a path literal in a module: "/api/...", "`/corpora/${id}/...`" (stops at a quote, `#` or `?`)
JS_PATH = re.compile(r"""[`"'](/(?:api|corpora)/[^`"'#?]*)""")
STRINGS_USE = re.compile(r"\bSTRINGS\.(\w+)")
STRINGS_DEF = re.compile(r"^  (\w+):", re.MULTILINE)
LABEL_USE = re.compile(r"""\blabel\(\s*"(\w+)"\s*,\s*"([\w-]+)"\s*\)""")
ID_USE = re.compile(r"""\$\("([\w-]+)"\)""")
IMPORT = re.compile(r"""import\s+(?:\{([^}]*)\}\s+from\s+)?"\./(\w+)\.js";""")
# a glossary word: term("key", ...), a double-brace "key | word" mark in a string, or data-term
TERM_USE = re.compile(r"""(?<!\w)term\(\s*"(\w+)"|\{\{(\w+)\||data-term="(\w+)\"""")
HUNGARIAN = re.compile("[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]")


def _text(path: Path) -> str:
    return path.read_text("utf-8")


def _all_js() -> str:
    return "\n".join(_text(p) for p in MODULES)


def _shape(path: str) -> str:
    """Make `${expr}` (JavaScript) and `{name}` (FastAPI) both read `{}`."""
    return re.sub(r"\$\{[^}]*\}|\{[^}]*\}", "{}", path)


def test_the_root_serves_the_page_that_links_its_assets() -> None:
    response = CLIENT.get("/")

    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    for asset in ("/static/tokens.css", "/static/app.css", "/static/card.css", "/static/app.js"):
        assert asset in response.text, f"expected the page to link {asset}"


def test_the_static_assets_are_served_with_the_type_a_browser_needs() -> None:
    # a browser refuses an ES module that is not served as JavaScript
    media = {".js": "javascript", ".css": "text/css", ".json": "json"}
    for path in ALL_FILES:
        if path.suffix not in media:
            continue
        response = CLIENT.get(f"/static/{path.name}")
        assert response.status_code == 200, path.name
        assert media[path.suffix] in response.headers["content-type"], (
            f"{path.name} is served as {response.headers['content-type']}"
        )
        assert response.content == path.read_bytes()


def test_there_is_one_module_entry_script_and_no_other_script() -> None:
    page = _text(STATIC_DIR / "index.html")

    assert re.findall(r"<script[^>]*>", page) == ['<script type="module" src="/static/app.js">']


def test_no_static_file_is_longer_than_400_lines() -> None:
    too_long = {p.name: len(_text(p).splitlines()) for p in ALL_FILES}

    assert {n: c for n, c in too_long.items() if c > 400} == {}


def test_the_page_is_offline() -> None:
    for path in ALL_FILES:
        urls = re.findall(r"https?://[^\s\"')`]+", _text(path))
        assert [u for u in urls if u != SVG_NAMESPACE] == [], f"{path.name} reaches the network"


def test_every_api_path_the_javascript_calls_exists_in_the_router() -> None:
    called = {_shape(path) for path in JS_PATH.findall(_all_js())}
    served = {_shape(r.path) for r in APP.routes if isinstance(r, APIRoute)}

    assert called, "expected the modules to call the API, found no path literal"
    assert called <= served, f"the modules call paths the server lacks: {sorted(called - served)}"


def test_every_string_the_javascript_uses_is_defined() -> None:
    defined = set(STRINGS_DEF.findall(_text(STATIC_DIR / "strings.js")))
    used = set(STRINGS_USE.findall(_all_js()))

    assert used - defined == set(), f"STRINGS keys used but not defined: {sorted(used - defined)}"


def test_every_label_the_javascript_looks_up_exists_in_the_table() -> None:
    table = json.loads(_text(STATIC_DIR / "labels.en.json"))
    looked_up = set(LABEL_USE.findall(_all_js()))

    assert looked_up, "expected the modules to look up labels, found none"
    missing = [(s, k) for s, k in looked_up if k not in table.get(s, {})]
    assert missing == [], f"label lookups without an entry: {missing}"


def test_every_element_id_the_javascript_asks_for_is_in_the_page() -> None:
    page_ids = set(re.findall(r'\bid="([\w-]+)"', _text(STATIC_DIR / "index.html")))
    used = set(ID_USE.findall(_all_js()))

    assert used - page_ids == set(), (
        f"ids asked for but missing in index.html: {sorted(used - page_ids)}"
    )


def test_every_import_resolves_to_a_module_that_exports_the_name() -> None:
    for path in MODULES:
        for names, module in IMPORT.findall(_text(path)):
            target = STATIC_DIR / f"{module}.js"
            assert target.exists(), f"{path.name} imports ./{module}.js, which does not exist"
            exported = _text(target)
            for name in (n.strip() for n in names.split(",") if n.strip()):
                declaration = r"export\s+(?:async\s+)?(?:function|const|class|let)\s+"
                pattern = declaration + re.escape(name) + r"(?![\w$])"
                assert re.search(pattern, exported), f"{path.name} imports {name} from {module}.js"


@pytest.mark.parametrize("path", [p for p in MODULES if p.name != "app.js"], ids=lambda p: p.name)
def test_every_module_is_imported_by_another(path: Path) -> None:
    importers = [m for m in MODULES if m != path and f'"./{path.stem}.js"' in _text(m)]

    assert importers, f"expected another module to import {path.name}, found none"


def test_visitor_facing_files_hold_no_hungarian_letters() -> None:
    for name in ("strings.js", "labels.en.json", "index.html"):
        assert HUNGARIAN.search(_text(STATIC_DIR / name)) is None, f"{name} has Hungarian letters"


def test_the_page_has_no_payment_dialog_and_no_replay_state() -> None:
    page = _text(STATIC_DIR / "index.html")
    script = _all_js()

    assert "<dialog" not in page
    for retired in ("allow_paid", "needs_paid", "replay", "tier2_only"):
        assert retired not in script, f"the modules still mention {retired}"


def test_the_ask_request_carries_the_text_and_the_example_id() -> None:
    ask = _text(STATIC_DIR / "ask.js")

    assert "example_id" in ask and "benchmark_question_id" not in _all_js()


def test_both_themes_define_every_token_the_light_theme_does() -> None:
    css = _text(STATIC_DIR / "tokens.css")
    light = css.split(':root[data-theme="dark"]')[0]
    dark = css.split(':root[data-theme="dark"]')[1].split("}")[0]
    colour_tokens = set(re.findall(r"(--[\w-]+):\s*(?:#|rgb)", light))

    assert colour_tokens <= set(re.findall(r"(--[\w-]+):", dark))


def _glossary_keys_used() -> set[str]:
    sources = _all_js() + _text(STATIC_DIR / "index.html")
    return {key for match in TERM_USE.findall(sources) for key in match if key}


def test_every_glossary_word_has_text_and_every_text_is_used() -> None:
    glossary = json.loads(_text(STATIC_DIR / "labels.en.json"))["glossary"]
    used = _glossary_keys_used()

    assert used, "expected the modules to use glossary words, found none"
    assert used - set(glossary) == set(), (
        f"glossary words without text: {sorted(used - set(glossary))}"
    )
    assert set(glossary) - used == set(), (
        f"glossary texts nobody uses: {sorted(set(glossary) - used)}"
    )


def test_the_page_holds_the_one_shared_tooltip_the_glossary_fills() -> None:
    page = _text(STATIC_DIR / "index.html")

    assert page.count('id="glossary-tip"') == 1 and 'role="tooltip"' in page


def test_the_route_view_is_wired_into_the_answer_card_and_the_step_list() -> None:
    answer = _text(STATIC_DIR / "answer.js")
    steps = _text(STATIC_DIR / "steps.js")

    # the card builds the route view and hands the same current-step object to the step list
    assert "routeSection(" in answer and "createStepSync(" in answer
    assert "sync.select(" in steps, "the step list should select the route view's current step"
    for name in ("route", "route_controls", "route_draw", "route_layout", "step_sync"):
        assert (STATIC_DIR / f"{name}.js").exists(), f"expected static/{name}.js"
