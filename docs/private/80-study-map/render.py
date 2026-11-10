"""Render the study map: study_map.json -> study_map.html (one self-contained page).

Usage: python docs/private/80-study-map/render.py
The page is published as an Artifact; see .claude/skills/study-map/SKILL.md.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "study_map.json"
TARGET = HERE / "study_map.html"
TEMPLATE = HERE / "study_map.template.html"


def embed(data: dict) -> str:
    """Return the map as JSON that is safe inside a <script> element."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/")


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    page = TEMPLATE.read_text(encoding="utf-8").replace("__MAP_DATA__", embed(data))
    TARGET.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.name}: {len(page) // 1024} KiB, {len(data['stations'])} stations")


if __name__ == "__main__":
    main()
