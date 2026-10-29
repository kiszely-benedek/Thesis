"""`python -m plantgraph.qa.exp0001 report`: read the stored runs, write the EXP-0001 report.

Run directories follow the run script's names under `<root>/runs`: `<prefix>-CTXH-<corpus>`
(ContextRAG high), `-CTXL-` (low), `-CYP-` and `-AG-` (the cascade's tiers); the prefix is `E1` for
the v1 report and `E7` for `--edition v2` (the v2 re-measurement, ADR-0060). A run that is not there
is listed as absent in the report, not an error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import (
    POLICIES_DIR,
    V2T_POLICIES_DIR,
    V2T_REFERENCES_DIR,
    load_policies,
    load_policy,
)
from plantgraph.qa.exp0001.report import LADDER_IDS, LADDER_IDS_V2, build_ladder_report
from plantgraph.qa.exp0001.report_claims import (
    V1_BIG_PROMPTS,
    V1_EDITION,
    V2_EDITION,
    Edition,
    WallSettings,
)
from plantgraph.qa.exp0001.report_load import CorpusInputs, score_corpus
from plantgraph.qa.exp0001.report_models import AG, CASCADE, CTX_HIGH, CTX_LOW, CYP
from plantgraph.qa.exp0001.report_render import write_report

#: Arm -> run-id infix; the edition's prefix goes in front (`E1-CTXH-H30`, `E7-CTXH-H30g2`).
_RUN_INFIX = {CTX_HIGH: "CTXH", CTX_LOW: "CTXL", CYP: "CYP", AG: "AG"}
#: edition name -> (run-id prefix, default ladder ids, claim texts, report title)
_EDITIONS: dict[str, tuple[str, tuple[str, ...], Edition, str]] = {
    "v1": ("E1", LADDER_IDS, V1_EDITION, "EXP-0001 report"),
    "v2": ("E7", LADDER_IDS_V2, V2_EDITION, "EXP-0007 report (v2 plants)"),
}
_SEALED = Path("data") / "runs" / "sealed"


def add_report_arguments(parser: argparse.ArgumentParser) -> None:
    """The `report` command's options (all paths default to the run script's layout)."""
    root = Path("data") / "runs" / "exp0001"
    parser.add_argument("--root", type=Path, default=root, help="the EXP-0001 data directory")
    parser.add_argument("--out", type=Path, help="default: <root>/report")
    parser.add_argument("--edition", choices=sorted(_EDITIONS), default="v1")
    parser.add_argument(
        "--sizes", help="ladder corpus ids (default: the edition's ladder, e.g. H1,H3,H10,H30)"
    )
    parser.add_argument(
        "--wall-chars",
        help="ID=N,ID=N: prompt characters of corpora too big to call, for X5 "
        "(default: v1's H100 and H1000; none on v2, take them from `prompt-size`)",
    )
    parser.add_argument(
        "--h1000-sheets", type=int, default=1001, help="sheets of the figure's 'does not fit' mark"
    )
    parser.add_argument("--cutoff-s", type=float, default=DEFAULT_CUTOFF_S)
    parser.add_argument(
        "--system",
        choices=["f1", "v2t"],
        default="f1",
        help="what the cyp / ag / cascade arms stand for (v2t: V2T-A tiers, cascade_v4_iso)",
    )
    parser.add_argument("--footnote", help="text appended to report.md (what was not run, and why)")
    parser.add_argument("--max-prompt-tokens", type=int, default=WallSettings().max_prompt_tokens)
    parser.add_argument("--ctx-high-policy", type=Path)
    parser.add_argument("--ctx-low-policy", type=Path)
    parser.add_argument(
        "--h100-tiers",
        help="CYP_RUN_DIR,AG_RUN_DIR of the sealed H100 runs; adds H100 when E1-CTXH-H100 exists",
    )
    parser.add_argument("--h100-corpora-root", type=Path, default=_SEALED / "corpora")
    parser.add_argument("--h100-tier-questions-root", type=Path, default=_SEALED / "questions")


#: `--system` -> (cyp policy, ag policy, cascade policy) names, each with its directory.
_SYSTEMS = {
    "f1": (
        (POLICIES_DIR, "always_c_luna"),
        (POLICIES_DIR, "always_g_luna"),
        (POLICIES_DIR, "cascade_v3"),
    ),
    "v2t": (
        (V2T_REFERENCES_DIR, "always_c_v2t"),
        (V2T_REFERENCES_DIR, "always_g_v2t"),
        (V2T_POLICIES_DIR, "cascade_v4_iso"),
    ),
}


def _policies(args: argparse.Namespace) -> dict[str, CascadePolicy]:
    inputs = args.root / "inputs"
    (c_dir, c_name), (g_dir, g_name), (v_dir, v_name) = _SYSTEMS[args.system]
    return {
        CTX_HIGH: load_policy(args.ctx_high_policy or inputs / "always_ctx_high.json"),
        CTX_LOW: load_policy(args.ctx_low_policy or inputs / "always_ctx_low.json"),
        CYP: load_policies(c_dir)[c_name],
        AG: load_policies(g_dir)[g_name],
        # the arm key stays `cascade_v3` inside the report; `_relabel` renames it in the files
        CASCADE: load_policies(v_dir)[v_name],
    }


def _relabel(paths: list[Path], system: str, footnote: str | None) -> None:
    """Name the cascade arm after the system's real policy, and append the footnote to report.md."""
    name = _SYSTEMS[system][2][1]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if name != CASCADE:
            text = text.replace(CASCADE, name)
        if footnote and path.name == "report.md":
            text = text.rstrip("\n") + "\n\n" + footnote + "\n"
        path.write_text(text, encoding="utf-8")


def _existing_runs(runs_root: Path, prefix: str, corpus_id: str) -> dict[str, Path]:
    candidates = {arm: runs_root / f"{prefix}-{i}-{corpus_id}" for arm, i in _RUN_INFIX.items()}
    return {arm: path for arm, path in candidates.items() if path.is_dir()}


def _ladder_ids(args: argparse.Namespace) -> list[str]:
    return (args.sizes or ",".join(_EDITIONS[args.edition][1])).split(",")


def _ladder_inputs(args: argparse.Namespace) -> list[CorpusInputs]:
    prefix = _EDITIONS[args.edition][0]
    return [
        CorpusInputs(
            corpus_id=corpus_id,
            questions_root=args.root / "questions",
            corpora_root=args.root / "corpora",
            run_dirs=_existing_runs(args.root / "runs", prefix, corpus_id),
        )
        for corpus_id in _ladder_ids(args)
    ]


def parse_wall_chars(text: str) -> tuple[tuple[str, int], ...]:
    """`H100g2=3948282,H1000g2=39000000` as (id, chars) pairs.

    Raises:
        ValueError: an item is not `ID=N` with N a positive integer.
    """
    pairs = []
    for item in text.split(","):
        corpus_id, separator, chars = item.partition("=")
        if not separator or not corpus_id or not chars.isdigit() or int(chars) <= 0:
            raise ValueError(f"expected --wall-chars items like H100g2=3948282, found {item!r}")
        pairs.append((corpus_id, int(chars)))
    return tuple(pairs)


def _wall_settings(args: argparse.Namespace) -> WallSettings:
    if args.wall_chars:
        big = parse_wall_chars(args.wall_chars)
    else:
        big = V1_BIG_PROMPTS if args.edition == "v1" else ()
    return WallSettings(max_prompt_tokens=args.max_prompt_tokens, big_prompts=big)


def _h100_inputs(args: argparse.Namespace) -> CorpusInputs | None:
    """Stage C: ContextRAG-high on H100 beside the sealed tier runs; `None` if it was not run."""
    ctx_run = args.root / "runs" / "E1-CTXH-H100"
    if args.edition == "v2" and args.h100_tiers:
        raise SystemExit("error: --h100-tiers is stage C, which is not applicable on v2 (ADR-0060)")
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
    _, _, edition, title = _EDITIONS[args.edition]
    report = build_ladder_report(
        corpora, args.cutoff_s, _ladder_ids(args), _wall_settings(args), edition
    )
    out = args.out or args.root / "report"
    paths = write_report(report, out, args.h1000_sheets, title)
    _relabel(paths, args.system, args.footnote)
    shown = _SYSTEMS[args.system][2][1]
    print("\n".join(f"wrote {path}" for path in paths))
    print(
        "\n".join(f"{c.id} {c.verdict}: {c.value}".replace(CASCADE, shown) for c in report.claims)
    )
