"""Stage 2's entry point: writes out the final OPEN100 answer key.

    uv run python -m plantgraph.benchmark.open100.stage2 <open100_dir> <out_dir>

Unlike stage 1, this does not look at images — it builds the manifest from the
labels already recorded and read in annotations.py (see manifest.py). What it writes:

  - open100_manifest.json: the complete SplitManifest,
  - open100_connectors.csv: the same data in a table, so it can also be
    reviewed in a spreadsheet — this is a manual-review tool, not the final result.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.open100.corpus import Open100Corpus
from plantgraph.benchmark.open100.manifest import build_manifest


def _fate_of(key: str, manifest: SplitManifest) -> tuple[str, str, str]:
    """A connector's fate, its partner (if any), and the note, for the CSV row.

    The partner's key gets its own column so that manual review doesn't need to
    dig through the manifest JSON to find which two crops belong side by side.
    """
    for pair in manifest.connector_pairs:
        if key in (pair.from_key, pair.to_key):
            partner = pair.to_key if key == pair.from_key else pair.from_key
            return f"paired ({pair.match_rule.value})", partner, pair.note or ""
    for dangling in manifest.dangling:
        if dangling.from_key == key:
            return "dangling", "", dangling.reason
    for unresolved in manifest.unresolved:
        if unresolved.from_key == key:
            return "unresolved", "", unresolved.reason
    return "MISSING", "", "not classified — this is a bug"  # accounted_for() guards against this


def write_csv(manifest: SplitManifest, path: Path) -> None:
    """For human review: one row per connector, with its fate, partner, and confidence note."""
    header = [
        "key",
        "side",
        "target",
        "grid_cell",
        "service",
        "line_number",
        "fate",
        "partner",
        "note",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for obs in manifest.connectors:
            fate, partner, note = _fate_of(obs.key, manifest)
            writer.writerow(
                [
                    obs.key,
                    obs.side.value,
                    obs.target.canonical() if obs.target else "",
                    obs.grid_cell or "",
                    obs.service or "",
                    obs.line_number or "",
                    fate,
                    partner,
                    note,
                ]
            )


def _summary(manifest: SplitManifest) -> str:
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
    """Command-line entry point: writes out the manifest and the review CSV."""
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
