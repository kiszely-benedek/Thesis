"""`python -m plantgraph.qa.exp0001 duplication-report`: cascade_v3 at three duplication rates.

*Duplication* is the share of equipment that a second sheet draws again as a reference (ADR-0028).
The same plant (same seed) is built at 0 %, 25 % (the preset) and 50 %, and the sealed run's two
tiers answer each plant's questions. A question's **stem** is its id without the corpus prefix
(`<family>:<anchors>`), so a question asked on two plants can be compared on the same item. The
differences are descriptive: ADR-0028 sets no claim on them (ADR-0060).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies
from plantgraph.qa.cascade.report_scopes import SCOPE_HEADLINE, load_splits, scope_ids
from plantgraph.qa.cascade.stats import Interval, interval_of, paired_bootstrap, wilson_interval
from plantgraph.qa.exp0001.report_cells import N_BOOT, SEED
from plantgraph.qa.exp0001.report_load import CorpusInputs, score_corpus
from plantgraph.qa.exp0001.report_models import AG, CASCADE, CYP, QuestionScore

#: Run-id prefix of the sealed v2 runs (`S7-CYP-<corpus>`, `S7-AG-<corpus>`).
RUN_PREFIX = "S7"
DEFAULT_POINTS = "H100g2d0=0,H100g2=25,H100g2d50=50"

#: A corpus's scores: (corpus id, duplication percent, headline scores).
ScoredPoint = tuple[str, int, list[QuestionScore]]


class RatePoint(BaseModel):
    """cascade_v3's accuracy on the headline questions of one plant."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    duplication_percent: int
    n: int
    correct_at_120: int
    acc_at_120: Interval


class StemPair(BaseModel):
    """`high` minus `low` duplication on the questions both plants ask (same stem)."""

    model_config = ConfigDict(frozen=True)

    high: str
    low: str
    n_common: int
    n_only_high: int
    n_only_low: int
    delta: float
    ci: Interval


class DuplicationReport(BaseModel):
    """The accuracy at each rate and the paired differences between rates."""

    model_config = ConfigDict(frozen=True)

    points: list[RatePoint]
    pairs: list[StemPair]


def stem_of(question_id: str, corpus_id: str) -> str:
    """The question id without its corpus prefix.

    Raises:
        ValueError: the id does not start with `<corpus_id>:`.
    """
    prefix = f"{corpus_id}:"
    if not question_id.startswith(prefix):
        raise ValueError(f"expected question id {question_id!r} to start with {prefix!r}")
    return question_id[len(prefix) :]


def rate_point(corpus_id: str, percent: int, scores: Sequence[QuestionScore]) -> RatePoint:
    """Wilson interval of acc@cutoff over the given scores."""
    right = sum(s.correct_at_cutoff for s in scores)
    return RatePoint(
        corpus_id=corpus_id,
        duplication_percent=percent,
        n=len(scores),
        correct_at_120=right,
        acc_at_120=wilson_interval(right, len(scores)),
    )


def pair_by_stem(
    high: tuple[str, Sequence[QuestionScore]], low: tuple[str, Sequence[QuestionScore]]
) -> StemPair:
    """Paired bootstrap of acc@cutoff (high minus low) over the stems both corpora ask.

    Raises:
        ValueError: the corpora share no question stem.
    """
    by_stem_high = {stem_of(s.qid, high[0]): s for s in high[1]}
    by_stem_low = {stem_of(s.qid, low[0]): s for s in low[1]}
    common = sorted(by_stem_high.keys() & by_stem_low.keys())
    if not common:
        raise ValueError(f"expected {high[0]} and {low[0]} to share question stems, found none")
    x = [float(by_stem_high[stem].correct_at_cutoff) for stem in common]
    y = [float(by_stem_low[stem].correct_at_cutoff) for stem in common]
    difference = paired_bootstrap(x, y, n_resamples=N_BOOT, seed=SEED)
    return StemPair(
        high=high[0],
        low=low[0],
        n_common=len(common),
        n_only_high=len(by_stem_high) - len(common),
        n_only_low=len(by_stem_low) - len(common),
        delta=difference.mean,
        ci=interval_of(difference),
    )


def build_duplication_report(scored: Sequence[ScoredPoint]) -> DuplicationReport:
    """Points and every pair of rates (higher minus lower), from the scored corpora."""
    ordered = sorted(scored, key=lambda item: item[1])
    points = [rate_point(corpus_id, percent, s) for corpus_id, percent, s in ordered]
    pairs = [pair_by_stem((b[0], b[2]), (a[0], a[2])) for a, b in combinations(ordered, 2)]
    return DuplicationReport(points=points, pairs=pairs)


def render_duplication_markdown(report: DuplicationReport) -> str:
    """The report as markdown: one table of rates, one of paired differences."""
    rates = ["| Corpus | Duplication % | n | acc@120 [95% CI] |", "|---|---|---|---|"]
    for p in report.points:
        a = p.acc_at_120
        rates.append(
            f"| {p.corpus_id} | {p.duplication_percent} | {p.n} | "
            f"{a.estimate:.3f} [{a.ci_low:.3f}, {a.ci_high:.3f}] |"
        )
    pairs = [
        "| High - low | Common stems | Only in high / low | Delta [95% CI] |",
        "|---|---|---|---|",
    ]
    for q in report.pairs:
        pairs.append(
            f"| {q.high} - {q.low} | {q.n_common} | {q.n_only_high} / {q.n_only_low} | "
            f"{q.delta:+.3f} [{q.ci.ci_low:+.3f}, {q.ci.ci_high:+.3f}] |"
        )
    title = "# cascade_v3 at three duplication rates (descriptive)"
    return "\n".join([title, "", *rates, "", *pairs, ""])


def parse_points(text: str) -> list[tuple[str, int]]:
    """`H100g2d0=0,H100g2=25` as (corpus id, duplication percent) pairs.

    Raises:
        ValueError: an item is not `ID=PERCENT`.
    """
    result = []
    for item in text.split(","):
        corpus_id, separator, percent = item.partition("=")
        if not separator or not corpus_id or not percent.isdigit():
            raise ValueError(f"expected --points items like H100g2d0=0, found {item!r}")
        result.append((corpus_id, int(percent)))
    return result


def add_duplication_arguments(parser: argparse.ArgumentParser) -> None:
    """The `duplication-report` command's options."""
    parser.add_argument("--root", type=Path, required=True, help="holds questions/ corpora/ runs/")
    parser.add_argument("--points", default=DEFAULT_POINTS, help="ID=PERCENT,...")
    parser.add_argument("--cutoff-s", type=float, default=120.0)
    parser.add_argument("--out", type=Path, required=True)


def _headline_scores(inputs: CorpusInputs, cutoff_s: float) -> list[QuestionScore]:
    policy = load_policies(POLICIES_DIR)["cascade_v3"]
    scored = score_corpus(inputs, {CASCADE: policy}, cutoff_s)
    _, questions = load_questions_file(inputs.questions_root, inputs.corpus_id)
    splits = load_splits(inputs.questions_root, inputs.corpus_id, questions)
    keep = scope_ids(questions, splits)[SCOPE_HEADLINE]
    return [s for s in scored.scores[CASCADE] if s.qid in keep]


def _inputs(root: Path, corpus_id: str) -> CorpusInputs:
    runs = {arm: root / "runs" / f"{RUN_PREFIX}-{arm.upper()}-{corpus_id}" for arm in (CYP, AG)}
    return CorpusInputs(corpus_id, root / "questions", root / "corpora", runs)


def duplication_command(args: argparse.Namespace) -> None:
    """Score cascade_v3 on every point's headline questions, write the files and print them."""
    scored = [
        (corpus_id, percent, _headline_scores(_inputs(args.root, corpus_id), args.cutoff_s))
        for corpus_id, percent in parse_points(args.points)
    ]
    report = build_duplication_report(scored)
    args.out.mkdir(parents=True, exist_ok=True)
    json_text = report.model_dump_json(indent=2) + "\n"
    (args.out / "duplication.json").write_text(json_text, encoding="utf-8")
    markdown = render_duplication_markdown(report)
    (args.out / "duplication.md").write_text(markdown, encoding="utf-8")
    print(markdown)
