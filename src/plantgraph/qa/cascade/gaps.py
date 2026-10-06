"""Missing tier rows: refuse the join and say exactly which harness run would fill them."""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.cascade.checks import JoinRefused, LoadedRun
from plantgraph.qa.cascade.models import TierSpec

_SHOWN_IDS = 10


class IncompleteJoinError(JoinRefused):
    """Some questions reach a tier that has no row for them; `gaps` maps tier name to ids."""

    def __init__(self, gaps: dict[str, list[str]], message: str) -> None:
        super().__init__(message)
        self.gaps = gaps


def harness_command(tier: TierSpec, reference: LoadedRun, corpus_id: str, qsub_root: Path) -> str:
    """The harness command that answers the questions `needed` writes for `tier`.

    Placeholders in <angle brackets> are what the join cannot know: the pin file, the
    strategy parameters and the spend cap of a paid run.
    """
    parts = [
        "python -m plantgraph.qa.harness",
        f"--run-id <RUN_ID_{tier.name}>",
        "--experiment <EXPERIMENT>",
        f"--corpus {corpus_id}:{reference.record.role}",
        f"--strategy {tier.strategy}",
        "--strategy-params-json <PARAMS_JSON>",
        "--pin-json <PIN_JSON>",
        f"--questions-root {(qsub_root / tier.name).as_posix()}",
        "--allow-paid-calls --max-spend-usd <CAP_USD>",
    ]
    if not reference.config.primer:
        parts.append("--no-primer")
    return " ".join(parts)


def gap_message(
    gaps: dict[str, list[str]],
    tiers: tuple[TierSpec, ...],
    reference: LoadedRun,
    corpus_id: str,
    qsub_root: Path,
) -> str:
    """One refusal message: per tier the missing ids, and the commands that fill them."""
    lines = ["the join is incomplete: these questions reach a tier with no row for them"]
    for tier in tiers:
        ids = gaps.get(tier.name)
        if not ids:
            continue
        shown = ", ".join(ids[:_SHOWN_IDS]) + (" ..." if len(ids) > _SHOWN_IDS else "")
        lines.append(f"  tier {tier.name}: {len(ids)} missing: {shown}")
        lines.append(
            f"    1. python -m plantgraph.qa.cascade needed --tier {tier.name} "
            f"--corpus {corpus_id} --out-root {qsub_root.as_posix()} <same --policy/--run args>"
        )
        lines.append(f"    2. {harness_command(tier, reference, corpus_id, qsub_root)}")
    return "\n".join(lines)
