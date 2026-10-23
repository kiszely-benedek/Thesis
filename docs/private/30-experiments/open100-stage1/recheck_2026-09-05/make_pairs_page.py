"""Egy helyi HTML oldal a 22 párról: a két csatlakozó kivágása egymás mellett, az
értékeikkel — így a párosítás kézzel ellenőrizhető a CSV és 96 fájl közti
ugrálás nélkül.

    uv run python docs/private/30-experiments/open100-stage1/recheck_2026-09-05/make_pairs_page.py

A képek a szomszédos wide_crops_2026-09-05/ mappából jönnek, relatív úttal —
az oldalt a mappájából kell megnyitni (böngészőben), nem áthelyezni.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE1 = HERE.parent
MANIFEST = STAGE1 / "open100_manifest.json"
OUT = STAGE1 / "pairs_review.html"


def _crop_name(key: str) -> str:
    sheet, node = key.split(":")
    return f"wide_crops_2026-09-05/{sheet}_{''.join(ch for ch in node if ch.isdigit())}_wide.png"


def _cell(obs: dict, key: str) -> str:
    target = obs.get("target")
    target_txt = f"PID-{target['pid']}-{target['sheet_no']}" if target else "—"
    rows = [
        ("key", key),
        ("side", obs.get("side", "")),
        ("target", target_txt),
        ("grid_cell", obs.get("grid_cell") or "—"),
        ("service", obs.get("service") or "—"),
        ("line_number", obs.get("line_number") or "—"),
    ]
    table = "".join(f"<tr><th>{k}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return (
        f'<div class="side"><table>{table}</table>'
        f'<img src="{_crop_name(key)}" alt="{html.escape(key)}"></div>'
    )


def main() -> None:
    """Felépíti az oldalt a manifestből."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_key = {c["sheet_file"] + ":" + c["node_id"]: c for c in manifest["connectors"]}

    blocks = []
    for i, pair in enumerate(manifest["connector_pairs"], 1):
        frm, to = pair["from_key"], pair["to_key"]
        note = html.escape(pair.get("note") or "")
        blocks.append(
            f'<section><h2>{i}. {html.escape(frm)} ↔ {html.escape(to)} '
            f'<span class="rule {pair["match_rule"]}">{pair["match_rule"]}</span></h2>'
            f'<p class="note">{note}</p>'
            f'<div class="pair">{_cell(by_key[frm], frm)}{_cell(by_key[to], to)}</div></section>'
        )

    unresolved = "".join(
        f'<li><b>{html.escape(u["from_key"])}</b> — {html.escape(u["reason"])}'
        f'<br><img src="{_crop_name(u["from_key"])}"></li>'
        for u in manifest["unresolved"]
    )

    style = """
    body{font-family:system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}
    section{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin-bottom:28px}
    h2{font-size:16px;margin:0 0 6px}
    .rule{font-size:12px;padding:2px 8px;border-radius:10px;margin-left:8px;color:#fff}
    .line_number{background:#2a7} .grid_mutual{background:#e90} .service_direction{background:#d33}
    .note{color:#555;font-size:13px;margin:0 0 10px}
    .pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    .side table{font-size:12px;border-collapse:collapse;margin-bottom:6px}
    .side th{text-align:left;padding:1px 10px 1px 0;color:#666;font-weight:normal}
    .side td{font-family:ui-monospace,monospace}
    img{max-width:100%;border:1px solid #ccc;background:#fff}
    ul{list-style:none;padding:0} li{margin-bottom:24px}
    """
    page = (
        "<!doctype html><meta charset='utf-8'><title>OPEN100 pairs review</title>"
        f"<style>{style}</style>"
        "<h1>OPEN100 — 22 pairs to check</h1>"
        "<p>For each pair: the left flag should name the right flag's drawing and vice versa; "
        "one arrow should point <i>into</i> its flag (outgoing), the other <i>away</i> (incoming); "
        "and, for <span class='rule line_number'>line_number</span> pairs, the same number "
        "should be printed on both pipes (prefix may differ). Grid cells are known to be off by a row or more.</p>"
        + "".join(blocks)
        + "<h1>10 unresolved — confirm there is really no partner</h1><ul>"
        + unresolved
        + "</ul>"
    )
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(blocks)} pairs, {len(manifest['unresolved'])} unresolved)")


if __name__ == "__main__":
    main()
