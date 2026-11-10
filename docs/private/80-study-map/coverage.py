"""Coverage check for the study map: every ADR, design note, teaching note and package has a home.

Usage: python docs/private/80-study-map/coverage.py   (exit code 1 when something is missing)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAP = Path(__file__).resolve().parent / "study_map.json"


def mentioned(stations: list[dict]) -> str:
    """Every path-like value on the map, as one searchable text."""
    return json.dumps(stations, ensure_ascii=False).replace("\\\\", "/")


def adr_ids() -> list[str]:
    folder = ROOT / "docs/private/20-decisions"
    return sorted(p.name[:8] for p in folder.glob("ADR-*.md"))


def adr_ids_in_why(stations: list[dict]) -> set[str]:
    return {item.get("adr", "")[:8] for st in stations for item in st.get("why", [])}


def design_notes() -> list[str]:
    folder = ROOT / "docs/private/40-design"
    return sorted(f"docs/private/40-design/{p.name}" for p in folder.glob("*.md"))


def teaching_notes() -> list[str]:
    tracked = subprocess.run(["git", "ls-files", "docs/Notes"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in tracked.stdout.splitlines() if line]


def packages() -> list[str]:
    src = ROOT / "src/plantgraph"
    found = [p.parent for p in src.rglob("__init__.py") if "__pycache__" not in p.parts]
    return sorted(p.relative_to(ROOT).as_posix() + "/" for p in found if p != src)


def how_files(stations: list[dict]) -> list[str]:
    return [item.get("file", "").replace("\\", "/") for st in stations for item in st.get("how", [])]


def main() -> int:
    stations = json.loads(MAP.read_text(encoding="utf-8"))["stations"]
    text = mentioned(stations)
    files = how_files(stations)
    missing = {
        "ADR (not in any why)": [a for a in adr_ids() if a not in adr_ids_in_why(stations)],
        "design note": [d for d in design_notes() if d not in text],
        "teaching note": [n for n in teaching_notes() if n not in text],
        "package (not in any how)": [p for p in packages() if not any(f.startswith(p) for f in files)],
    }
    total = 0
    for kind, items in missing.items():
        for item in items:
            print(f"missing {kind}: {item}")
        total += len(items)
    print("coverage ok" if total == 0 else f"{total} missing")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
