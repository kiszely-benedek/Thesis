"""Running the scope X gold cross-check on plants: P0's built corpora, or forced-tagging dev plants.

    # P0's plant, read only (rebuilds the B view from `ingest.json`; writes nothing there)
    uv run python -m plantgraph.qa.exp0009.gold_crosscheck_plants --out OUT_DIR \
        --files D100g22 --corpora-root data/runs/exp0009/corpora \
        --questions-root data/runs/exp0009/questions

    # own dev plants, built in memory (no Neo4j, no model call)
    uv run python -m plantgraph.qa.exp0009.gold_crosscheck_plants --out OUT_DIR \
        --seeds 1 2 3 4 5 --sheets 100 --tagging untagged tagged

`OUT_DIR` must lie outside `data/runs/exp0009/`: a running measurement owns that folder.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterator, Mapping
from pathlib import Path

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009.dev_plants import forced_config
from plantgraph.qa.exp0009.gold_crosscheck import (
    X_FAMILIES,
    CrossChecker,
    PlantCheck,
    candidate_tallies,
    tally,
)
from plantgraph.qa.exp0009.gold_crosscheck_graph import build_flow_graph
from plantgraph.qa.exp0009.scope_x_report import POOL_SEED
from plantgraph.qa.models import Question
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.questions.scope_x import scope_x_candidates
from plantgraph.qa.v2tb.positions import (
    POSITIONS_FILE_NAME,
    read_operating_positions,
    read_positions_file,
)
from plantgraph.qa.v2tb.store_b import positions_by_local_key
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB
from plantgraph.resolution.localize import OccurrenceMap

_TAGGING = {"untagged": True, "tagged": False}
_FROZEN_RUN_FOLDER = Path("data/runs/exp0009")


def roles_by_local_key(roles: Mapping[str, str], occurrence_map: OccurrenceMap) -> dict[str, str]:
    """Generator role of each occurrence (an annotation for reports only, never used to judge)."""
    by_key: dict[str, str] = {}
    for local_key in occurrence_map.local_to_original:
        original = occurrence_map.original_node_id(local_key)
        if original in roles:
            by_key[local_key] = roles[original]
    return by_key


def dev_plant_check(seed: int, sheets: int, tagging: str) -> PlantCheck:
    """Build one forced-tagging plant in memory and cross-check every scope X family on it."""
    started = time.perf_counter()
    config = forced_config(sheets, seed, untagged=_TAGGING[tagging])
    corpus = build_synthetic_corpus(config, HeadlinePresetV22().split_config(seed))
    generated = generate_plant_v2(config)
    # the B corpus's positions: read from the DEXPI model, re-keyed as `load_corpus_b` does
    read = read_operating_positions(generated.model)
    by_local_key = positions_by_local_key(read, corpus.occurrence_map)
    plant_id = f"D{sheets}g22s{seed}"
    view = NetworkxGraphViewB(plant_id, corpus.localized_sheets, corpus.resolution, by_local_key)
    plan_roles: dict[str, str] = {}
    for unit_plan in generated.plan.unit_plans:
        plan_roles.update(unit_plan.roles)
    checker = CrossChecker(
        build_flow_graph(view), roles_by_local_key(plan_roles, corpus.occurrence_map)
    )
    outcomes = scope_x_candidates(
        corpus.plant,
        corpus.manifest,
        corpus.sheets,
        positions_of(generated.plan.unit_plans),
        corpus_id=plant_id,
        seed=POOL_SEED,
    )
    questions = [q for outcome in outcomes.values() for q in outcome.kept]
    tallies, gaps = tally(questions, checker)
    stored = {f: (o.candidates, o.kept) for f, o in outcomes.items()}
    return PlantCheck(
        plant_id=plant_id,
        tagging=tagging,
        tallies=tallies,
        disagreements=gaps,
        candidates=candidate_tallies(checker, stored),
        seconds=round(time.perf_counter() - started, 1),
    )


def files_plant_check(plant_id: str, corpora_root: Path, questions_root: Path) -> PlantCheck:
    """Cross-check the X questions P0 wrote for the B twin of `plant_id` (read only)."""
    started = time.perf_counter()
    b_id = plant_id + "B"
    artifacts = load_corpus_artifacts(b_id, corpora_root / b_id / "ingest.json")
    positions, _sha = read_positions_file(corpora_root / b_id / POSITIONS_FILE_NAME)
    by_local_key = positions_by_local_key(positions, artifacts.gold.occurrence_map)
    view = NetworkxGraphViewB(b_id, artifacts.localized_sheets, artifacts.resolution, by_local_key)
    questions = _x_questions(questions_root / b_id / "questions.jsonl")
    checker = CrossChecker(build_flow_graph(view))
    tallies, gaps = tally(questions, checker)
    return PlantCheck(
        plant_id=b_id,
        tagging="drawn",
        tallies=tallies,
        disagreements=gaps,
        candidates=[],  # a sample file holds only the drawn questions, not the pool
        seconds=round(time.perf_counter() - started, 1),
    )


def _x_questions(path: Path) -> list[Question]:
    loaded, _lines = read_questions(path)
    return [q for q in loaded if q.family in X_FAMILIES]


def render_table(check: PlantCheck) -> str:
    """The per-family agree/disagree table of one plant, as text."""
    lines = [f"{check.plant_id} ({check.tagging}), {check.seconds}s"]
    lines.append(f"  {'family':36s} total agree disagree")
    for t in check.tallies:
        lines.append(f"  {t.family.value:36s} {t.total:5d} {t.agree:5d} {t.disagree:8d}")
    for c in check.candidates:
        lines.append(
            f"  candidates {c.family.value:30s} mine {c.mine_candidates}/{c.mine_kept} kept, "
            f"stored {c.stored_candidates}/{c.stored_kept} kept, "
            f"differ {len(c.only_mine_kept) + len(c.only_stored_kept)}"
        )
    return "\n".join(lines)


def _require_outside_run_folder(out: Path) -> None:
    if _FROZEN_RUN_FOLDER.resolve() in (out.resolve(), *out.resolve().parents):
        raise ValueError(f"expected --out outside {_FROZEN_RUN_FOLDER}, found {out}")


def main(argv: list[str] | None = None) -> None:
    """Run the requested plants, write one JSON per plant into `--out` and print the tables."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.gold_crosscheck_plants")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--files", nargs="*", default=[], help="plant ids built by P0")
    parser.add_argument("--corpora-root", type=Path)
    parser.add_argument("--questions-root", type=Path)
    parser.add_argument("--seeds", nargs="*", type=int, default=[])
    parser.add_argument("--sheets", type=int, default=100)
    parser.add_argument("--tagging", nargs="*", choices=sorted(_TAGGING), default=[])
    args = parser.parse_args(argv)
    _require_outside_run_folder(args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    for check in _run_plants(args):
        (args.out / f"{check.plant_id}_{check.tagging}.json").write_text(
            check.model_dump_json(indent=1) + "\n", encoding="utf-8"
        )
        print(render_table(check), flush=True)


def _run_plants(args: argparse.Namespace) -> Iterator[PlantCheck]:
    """The requested plants one at a time, so a long run reports as it goes."""
    for plant_id in args.files:
        if args.corpora_root is None or args.questions_root is None:
            raise ValueError("expected --corpora-root and --questions-root with --files")
        yield files_plant_check(plant_id, args.corpora_root, args.questions_root)
    for tagging in args.tagging:
        for seed in args.seeds:
            yield dev_plant_check(seed, args.sheets, tagging)


if __name__ == "__main__":
    main()
