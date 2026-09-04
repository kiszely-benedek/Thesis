"""Stage 2 belépési pontja: kiírja a végleges OPEN100 megoldókulcsot.

    uv run python -m plantgraph.benchmark.open100.stage2 <open100_dir> <out_dir>

A stage 1-gyel ellentétben ez nem néz képet — az annotations.py-ban rögzített,
már elolvasott feliratokból építi fel a manifestet (lásd manifest.py). Amit
kiír:

  - open100_manifest.json: a teljes SplitManifest,
  - open100_connectors.csv: ugyanaz táblázatban, hogy táblázatkezelőben is
    átnézhető legyen — ez a kézi ellenőrzés eszköze, nem a végeredmény.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from plantgraph.benchmark.open100.corpus import Open100Corpus
from plantgraph.benchmark.open100.manifest import build_manifest


def _fate_of(key: str, manifest) -> tuple[str, str]:  # noqa: ANN001 — belső segéd, a manifest típusa nyilvánvaló a hívásból
    """Egy csatlakozó sorsa és a hozzá tartozó megjegyzés, a CSV-sor kedvéért."""
    for pair in manifest.connector_pairs:
        if key in (pair.from_key, pair.to_key):
            return f"paired ({pair.match_rule.value})", pair.note or ""
    for dangling in manifest.dangling:
        if dangling.from_key == key:
            return "dangling", dangling.reason
    for unresolved in manifest.unresolved:
        if unresolved.from_key == key:
            return "unresolved", unresolved.reason
    return "MISSING", "not classified — this is a bug"  # accounted_for() véd ez ellen


def write_csv(manifest, path: Path) -> None:  # noqa: ANN001 — lásd fent
    """Emberi átnézésre: egy sor csatlakozónként, a sorsával és a bizalmi jelzéssel együtt."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "side", "target", "grid_cell", "service", "line_number", "fate", "note"])
        for obs in manifest.connectors:
            fate, note = _fate_of(obs.key, manifest)
            writer.writerow(
                [
                    obs.key,
                    obs.side.value,
                    obs.target.canonical() if obs.target else "",
                    obs.grid_cell or "",
                    obs.service or "",
                    obs.line_number or "",
                    fate,
                    note,
                ]
            )


def _summary(manifest) -> str:  # noqa: ANN001 — lásd fent
    by_rule: dict[str, int] = {}
    for pair in manifest.connector_pairs:
        by_rule[pair.match_rule.value] = by_rule.get(pair.match_rule.value, 0) + 1
    lines = [
        f"connectors:  {len(manifest.connectors)}",
        f"pairs:       {len(manifest.connector_pairs)}  {by_rule}",
        f"dangling:    {len(manifest.dangling)}",
        f"unresolved:  {len(manifest.unresolved)}",
        f"accounted_for: {manifest.accounted_for()}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("open100_dir", type=Path, help="a 'PID2Graph OPEN100' mappa")
    parser.add_argument("out_dir", type=Path, help="ide kerül a manifest és a csv")
    args = parser.parse_args()

    corpus = Open100Corpus(args.open100_dir)
    manifest = build_manifest(corpus.observations())

    if not manifest.accounted_for():
        raise RuntimeError(
            "manifest.accounted_for() is False — a connector was dropped; "
            "check ANNOTATIONS in annotations.py against the observation list"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "open100_manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    write_csv(manifest, args.out_dir / "open100_connectors.csv")
    print(_summary(manifest))


if __name__ == "__main__":
    main()
