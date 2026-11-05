"""EXP-0004 claim I4 (descriptive): pair F1, candidates and D4 cost from 100 to 1,000 sheets.

PREREG.md §5: "F1 at H1000 minus H100 per decider, with CI; candidate and cost elasticity
e = ln(c1000/c100)/ln(10)". The two corpora of a pair are independent plants, so each is resampled
over its own blocks (the same cluster bootstrap as `score`, 2,000 resamples, seed 20261104) and the
difference is taken resample by resample. No model call; reads only the committed P3 outputs.

    .venv/Scripts/python data/runs/exp0004/i4_scale.py > data/runs/exp0004/test/i4_scale.md
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from plantgraph.exp0004 import storage
from plantgraph.exp0004.bootstrap import N_RESAMPLES, SEED, interval_of, resample_f1
from plantgraph.exp0004.deciders import DECIDER_IDS, DeciderRun
from plantgraph.exp0004.pairs import PairFile
from plantgraph.exp0004.scoring import block_counts, subsets_of

TEST = Path("data/runs/exp0004/test")
#: (100-sheet corpus, 1,000-sheet corpus): same duplication rate, same families
PAIRS = [("H100g2d100V", "H1000g2d100V"), ("H100g2V", "H1000g2V")]


def resampled_f1(corpus: str) -> tuple[dict[str, list[float | None]], int]:
    """F1 of every decider|subset on each block resample of one corpus, and its candidate count."""
    directory = TEST / corpus
    pairs = storage.read_model(storage.pairs_path(directory), PairFile).pairs
    runs = [
        storage.read_model(storage.decision_path(directory, d), DeciderRun) for d in DECIDER_IDS
    ]
    subsets = subsets_of(pairs)
    metrics = [f"{run.decider}|{subset}" for run in runs for subset in subsets]
    return resample_f1(block_counts(pairs, runs, subsets), metrics, N_RESAMPLES, SEED), len(pairs)


def point_f1(corpus: str) -> dict[str, float | None]:
    """The point F1 of every decider|subset, as `score.json` recorded it."""
    score = json.loads((TEST / corpus / "score.json").read_text(encoding="utf-8"))
    return {
        f"{d['decider']}|{name}": sub["prf"]["f1"]
        for d in score["deciders"]
        for name, sub in d["subsets"].items()
    }


def recorded_cost(corpus: str) -> float:
    """D4's provider cost of every answer on the corpus, cached answers counted at their price."""
    summary = json.loads((TEST / corpus / "d4_summary.json").read_text(encoding="utf-8"))
    return float(summary["llm"]["cost_usd_recorded"])


def elasticity(small: float, large: float) -> float:
    """Elasticity ln(large / small) / ln(10): 1.0 means linear in the sheet count."""
    return math.log(large / small) / math.log(10)


def scale_rows(small: str, large: str) -> list[str]:
    """Markdown rows: per decider and subset, F1 at 100, at 1,000, the difference and its CI."""
    small_resampled, n_small = resampled_f1(small)
    large_resampled, n_large = resampled_f1(large)
    small_point, large_point = point_f1(small), point_f1(large)
    rows = [
        f"### {small} -> {large}",
        "",
        "| metric | F1 100 | F1 1,000 | difference | 95 % CI |",
        "|---|---|---|---|---|",
    ]
    for metric in sorted(set(small_point) & set(large_point)):
        differences = [
            b - a
            for a, b in zip(small_resampled[metric], large_resampled[metric], strict=True)
            if a is not None and b is not None
        ]
        ci = interval_of(differences)
        a, b = small_point[metric], large_point[metric]
        estimate = "n/a" if a is None or b is None else f"{b - a:+.3f}"
        interval = "n/a" if ci.low is None else f"[{ci.low:+.3f}, {ci.high:+.3f}]"
        rows.append(f"| {metric} | {_num(a)} | {_num(b)} | {estimate} | {interval} |")
    cost_small, cost_large = recorded_cost(small), recorded_cost(large)
    rows += [
        "",
        f"Candidates {n_small} -> {n_large}: elasticity {elasticity(n_small, n_large):.3f}. "
        f"D4 recorded cost ${cost_small:.6f} -> ${cost_large:.6f}: elasticity "
        f"{elasticity(cost_small, cost_large):.3f}.",
        "",
    ]
    return rows


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def main() -> None:
    """Print the I4 tables for both corpus pairs."""
    lines = [
        "## EXP-0004 I4: 100 -> 1,000 sheets (descriptive)",
        "",
        f"Independent block resamples per corpus, {N_RESAMPLES} each, seed {SEED}.",
        "",
    ]
    for small, large in PAIRS:
        lines += scale_rows(small, large)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
