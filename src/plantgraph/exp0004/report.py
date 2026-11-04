"""Render score files as a Markdown report: one section per corpus, tables of F1 with intervals."""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.exp0004.bootstrap import Interval
from plantgraph.exp0004.scoring import Contrast, DeciderScore, ScoreFile


def render_report(scores: Sequence[ScoreFile]) -> str:
    """The report for one or more corpora, in the order given."""
    if not scores:
        raise ValueError("expected at least one score file to report on, got none")
    return "\n".join(line for score in scores for line in _corpus_section(score)) + "\n"


def _corpus_section(score: ScoreFile) -> list[str]:
    return [
        f"## {score.corpus_id}",
        "",
        f"{score.n_pairs} candidate pairs in {score.n_blocks} blocks; 95 % intervals from "
        f"{score.n_resamples} block resamples (seed {score.bootstrap_seed}).",
        "",
        *_pair_level_table(score.deciders),
        "",
        *_group_level_table(score.deciders),
        "",
        *_operator_table(score.deciders),
        "",
        *_contrast_table(score.contrasts),
        "",
    ]


def _pair_level_table(deciders: Sequence[DeciderScore]) -> list[str]:
    lines = [
        "### Pair level (candidate set, after grouping)",
        "",
        "| decider | tau | subset | P | R | F1 | F1 95 % CI |",
        "|---|---|---|---|---|---|---|",
    ]
    for decider in deciders:
        for subset, sub in decider.subsets.items():
            lines.append(
                f"| {decider.decider} | {_num(decider.threshold)} | {subset} | "
                f"{_num(sub.prf.precision)} | {_num(sub.prf.recall)} | {_num(sub.prf.f1)} | "
                f"{_interval(sub.f1_ci)} |"
            )
    return lines


def _group_level_table(deciders: Sequence[DeciderScore]) -> list[str]:
    lines = [
        "### Group level (`score_identity_groups`)",
        "",
        "| decider | P | R | F1 | dropped one-to-one | identity conflicts |",
        "|---|---|---|---|---|---|",
    ]
    for decider in deciders:
        group = decider.group_level
        lines.append(
            f"| {decider.decider} | {_num(group.precision)} | {_num(group.recall)} | "
            f"{_num(group.f1)} | {decider.n_dropped_one_to_one} | {decider.n_identity_conflicts} |"
        )
    return lines


def _operator_table(deciders: Sequence[DeciderScore]) -> list[str]:
    lines = [
        "### Recovered gold pairs per operator (descriptive)",
        "",
        "| decider | operator | gold | recovered |",
        "|---|---|---|---|",
    ]
    for decider in deciders:
        for operator, recovery in decider.per_operator.items():
            lines.append(
                f"| {decider.decider} | {operator} | {recovery.gold} | {recovery.recovered} |"
            )
    return lines


def _contrast_table(contrasts: Sequence[Contrast]) -> list[str]:
    lines = [
        "### Paired differences in F1 (plus minus minus)",
        "",
        "| plus | minus | difference | 95 % CI |",
        "|---|---|---|---|",
    ]
    for c in contrasts:
        lines.append(f"| {c.plus} | {c.minus} | {_num(c.estimate)} | {_interval(c.ci)} |")
    return lines


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _interval(interval: Interval) -> str:
    if interval.low is None or interval.high is None:
        return "n/a"
    return f"[{interval.low:.3f}, {interval.high:.3f}]"
