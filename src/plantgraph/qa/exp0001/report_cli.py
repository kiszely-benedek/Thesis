"""`python -m plantgraph.qa.exp0001 report`: read the stored runs, write the EXP-0001 report.

Run directories follow the run script's names under `<runs-root>`: `E1-CTXH-<corpus>` (ContextRAG
high), `E1-CTXL-<corpus>` (low), `E1-CYP-<corpus>` and `E1-AG-<corpus>` (the cascade's tiers).
A run that is not there is listed as absent in the report, not an error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies, load_policy
from plantgraph.qa.exp0001.report import LADDER_IDS, build_ladder_report
from plantgraph.qa.exp0001.report_claims import WallSettings
from plantgraph.qa.exp0001.report_load import CorpusInputs, score_corpus
from plantgraph.qa.exp0001.report_models import AG, CASCADE, CTX_HIGH, CTX_LOW, CYP
from plantgraph.qa.exp0001.report_render import write_report

_RUN_PREFIX = {CTX_HIGH: "E1-CTXH", CTX_LOW: "E1-CTXL", CYP: "E1-CYP", AG: "E1-AG"}
_SEALED = Path("data") / "runs" / "sealed"


def add_report_arguments(parser: argparse.ArgumentParser) -> None:
    """The `report` command's options (all paths default to the run script's layout)."""
    root = Path("data") / "runs" / "exp0001"
    parser.add_argument("--root", type=Path, default=root, help="the EXP-0001 data directory")
    parser.add_argument("--out", type=Path, help="default: <root>/report")
    parser.add_argument("--sizes", default=",".join(LADDER_IDS), help="ladder corpus ids")
    parser.add_argument("--cutoff-s", type=float, default=DEFAULT_CUTOFF_S)
    parser.add_argument("--max-prompt-tokens", type=int, default=WallSettings().max_prompt_tokens)
    parser.add_argument("--ctx-high-policy", type=Path)
    parser.add_argument("--ctx-low-policy", type=Path)
    parser.add_argument(
        "--h100-tiers",
        help="CYP_RUN_DIR,AG_RUN_DIR of the sealed H100 runs; adds H100 when E1-CTXH-H100 exists",
    )
    parser.add_argument("--h100-corpora-root", type=Path, default=_SEALED / "corpora")
    parser.add_argument("--h100-tier-questions-root", type=Path, default=_SEALED / "questions")


def _policies(args: argparse.Namespace) -> dict[str, CascadePolicy]:
    inputs = args.root / "inputs"
    shipped = load_policies(POLICIES_DIR)
    return {
        CTX_HIGH: load_policy(args.ctx_high_policy or inputs / "always_ctx_high.json"),
        CTX_LOW: load_policy(args.ctx_low_policy or inputs / "always_ctx_low.json"),
        CYP: shipped["always_c_luna"],
        AG: shipped["always_g_luna"],
        CASCADE: shipped["cascade_v3"],
    }


def _existing_runs(runs_root: Path, corpus_id: str) -> dict[str, Path]:
    candidates = {arm: runs_root / f"{prefix}-{corpus_id}" for arm, prefix in _RUN_PREFIX.items()}
    return {arm: path for arm, path in candidates.items() if path.is_dir()}


def _ladder_inputs(args: argparse.Namespace) -> list[CorpusInputs]:
    return [
        CorpusInputs(
            corpus_id=corpus_id,
            questions_root=args.root / "questions",
            corpora_root=args.root / "corpora",
            run_dirs=_existing_runs(args.root / "runs", corpus_id),
        )
        for corpus_id in args.sizes.split(",")
    ]


def _h100_inputs(args: argparse.Namespace) -> CorpusInputs | None:
    """Stage C: ContextRAG-high on H100 beside the sealed tier runs; `None` if it was not run."""
    ctx_run = args.root / "runs" / "E1-CTXH-H100"
    if not args.h100_tiers or not ctx_run.is_dir():
        return None
    cyp_dir, _, ag_dir = args.h100_tiers.partition(",")
    if not ag_dir:
        raise SystemExit(
            f"error: expected --h100-tiers CYP_RUN_DIR,AG_RUN_DIR, found {args.h100_tiers!r}"
        )
    return CorpusInputs(
        corpus_id="H100",
        questions_root=args.root / "questions_c",
        corpora_root=args.h100_corpora_root,
        run_dirs={CTX_HIGH: ctx_run, CYP: Path(cyp_dir), AG: Path(ag_dir)},
        tier_questions_root=args.h100_tier_questions_root,
    )


def report_command(args: argparse.Namespace) -> None:
    """Score every corpus, build the report, write it and print where it went."""
    policies = _policies(args)
    h100 = _h100_inputs(args)
    inputs = _ladder_inputs(args) + ([h100] if h100 else [])
    corpora = [score_corpus(i, policies, args.cutoff_s) for i in inputs]
    wall = WallSettings(max_prompt_tokens=args.max_prompt_tokens)
    report = build_ladder_report(corpora, args.cutoff_s, args.sizes.split(","), wall)
    paths = write_report(report, args.out or args.root / "report")
    print("\n".join(f"wrote {path}" for path in paths))
    print("\n".join(f"{c.id} {c.verdict}: {c.value}" for c in report.claims))
