"""Az OPEN100 csatlakozók előkészítése olvasásra.

    uv run python -m plantgraph.benchmark.open100 <open100_dir> <out_dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.benchmark.open100.corpus import Open100Corpus


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("open100_dir", type=Path, help="a 'PID2Graph OPEN100' mappa")
    parser.add_argument("out_dir", type=Path, help="ide kerülnek a montázsok")
    args = parser.parse_args()

    corpus = Open100Corpus(args.open100_dir)
    observations = corpus.observations()
    tag_to_key = corpus.prepare_reading(args.out_dir)

    by_side: dict[str, int] = {}
    for obs in observations:
        by_side[obs.side.value] = by_side.get(obs.side.value, 0) + 1

    print(f"connectors found: {len(observations)}")
    print(f"  by page edge:   {by_side}")
    print(f"  montages:       {len(list(args.out_dir.glob('montage_*.png')))}")
    print(f"  tag map:        {len(tag_to_key)} entries -> {args.out_dir}")


if __name__ == "__main__":
    main()
