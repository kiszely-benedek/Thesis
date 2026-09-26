"""Walk the 12 OPEN100 drawings and prepare their connectors for reading.

This is the first half of the annotation work. The goal is to recover from the
drawings which pipe continues onto which other sheet — this becomes the answer
key the system will later be measured against. The process has two stages:

  1. **this module**: find the connectors and produce images of them for reading,
  2. later: interpret the labels and pair connectors across sheets.

See docs/private/40-design/open100-annotation.md for the detailed plan.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from plantgraph.benchmark.models import ConnectorObservation, SplitManifest
from plantgraph.benchmark.open100 import crops, extract
from plantgraph.benchmark.open100.sheets import SHEETS

SOURCE_NAME = "PID2Graph/OPEN100"


class Open100Corpus:
    """The 12 OPEN100 drawings together with their annotation files."""

    def __init__(self, root: Path) -> None:
        """Check that all 12 sheets are present before reading anything.

        Args:
            root: the 'Complete/PID2Graph OPEN100' directory, holding the 0.png
            through 11.png drawings and their matching .graphml files.

        Raises:
            FileNotFoundError: if the directory is missing, or any sheet is
                missing. Better to fail here than to base a measurement on an
                answer key built from an incomplete drawing series.
        """
        self.root = root
        if not root.is_dir():
            raise FileNotFoundError(f"OPEN100 directory not found: {root}")
        missing = [
            stem
            for stem in SHEETS
            if not (root / f"{stem}.png").exists() or not (root / f"{stem}.graphml").exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"expected 12 png/graphml pairs in {root}; missing for sheets: "
                f"{', '.join(sorted(missing))}"
            )

    def image(self, file_stem: str) -> Image.Image:
        """Open one sheet's drawing image. Closing it is the caller's responsibility."""
        return Image.open(self.root / f"{file_stem}.png")

    def observations(self) -> list[ConnectorObservation]:
        """Every off-page connector from all 12 drawings, in sheet order.

        The drawing's width is needed because it determines whether a connector
        sits on the left or the right edge of the sheet.
        """
        found: list[ConnectorObservation] = []
        for stem in sorted(SHEETS, key=int):
            with self.image(stem) as img:
                width = img.width
            found.extend(extract.connectors_in_sheet(self.root / f"{stem}.graphml", width))
        return found

    def prepare_reading(self, out_dir: Path) -> dict[str, str]:
        """Write out the montages and their two companion files.

        What it leaves in the output directory:
          - montage_NN.png: images of the connectors, for reading,
          - tag_to_key.json: which montage row is which connector (for traceability),
          - manifest_stage1.json: the answer key's skeleton, without labels yet.
        """
        observations = self.observations()
        images = {stem: self.image(stem) for stem in SHEETS}
        try:
            tag_to_key = crops.write_montages(observations, images, out_dir)
        finally:
            # the 12 high-resolution drawings hold a lot of memory; release it even on error
            for img in images.values():
                img.close()

        (out_dir / "tag_to_key.json").write_text(json.dumps(tag_to_key, indent=2), encoding="utf-8")
        (out_dir / "manifest_stage1.json").write_text(
            self.draft_manifest(observations).model_dump_json(indent=2),
            encoding="utf-8",
        )
        return tag_to_key

    def draft_manifest(self, observations: list[ConnectorObservation]) -> SplitManifest:
        """The answer key's first draft: only where the connectors are.

        The labels and the pairings are added in the second stage.
        """
        return SplitManifest(
            source=SOURCE_NAME,
            sheet_files=sorted(SHEETS, key=int),
            connectors=observations,
        )
