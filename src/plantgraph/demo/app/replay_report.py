"""The freeze check and the JSON / Markdown output of a replay-agreement run.

The experiment's pre-registered *freeze* (`E9.sha256`) lists the sha256 of every file the
demo must not change. The check is done here in Python (no `sha256sum` needed), so the report
states in one place that the replay ran against the frozen code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.demo.app.replay_models import Agreement, CorpusReplay

#: How many mismatching paths a report lists before it only counts them.
_MAX_LISTED = 20


class FreezeCheck(BaseModel):
    """Result of hashing every file listed in an `E9.sha256`-style file."""

    model_config = ConfigDict(frozen=True)

    list_path: str
    n_files: int
    n_mismatch: int
    #: Changed or missing files (the first ones only).
    mismatched: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """True when every listed file has its recorded hash."""
        return self.n_mismatch == 0


class ReplayReport(BaseModel):
    """Everything one run of the command writes: the freeze check and one replay per corpus."""

    model_config = ConfigDict(frozen=True)

    freeze: FreezeCheck
    corpora: tuple[CorpusReplay, ...]


def sha256_of(path: Path) -> str:
    """Hex sha256 of a file, read in chunks (the cache is megabytes)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_freeze(list_path: Path, repo_root: Path) -> FreezeCheck:
    """Hash every file named in `list_path` (`<sha256> *<path>` lines) and count the mismatches.

    Raises:
        ValueError: a line is not in the `<sha256> *<path>` form.
    """
    lines = [line for line in list_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = [_parse_line(line) for line in lines]
    mismatched = [path for digest, path in entries if not _holds(repo_root / path, digest)]
    return FreezeCheck(
        list_path=str(list_path),
        n_files=len(lines),
        n_mismatch=len(mismatched),
        mismatched=tuple(mismatched[:_MAX_LISTED]),
    )


def _parse_line(line: str) -> tuple[str, str]:
    digest, separator, path = line.partition(" *")
    if not separator or len(digest) != 64:
        raise ValueError(f"expected a '<sha256> *<path>' line, found {line!r}")
    return digest, path


def _holds(path: Path, expected: str) -> bool:
    return path.is_file() and sha256_of(path) == expected


def write_report(report: ReplayReport, out_dir: Path) -> tuple[Path, Path]:
    """Write `replay_agreement.json` and `replay_agreement.md` into `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "replay_agreement.json"
    markdown_path = out_dir / "replay_agreement.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: ReplayReport) -> str:
    """A short human-readable summary: freeze result, one count row per corpus, the exceptions."""
    freeze = report.freeze
    lines = [
        "# Replay agreement: routed live cascade against the frozen offline walk",
        "",
        f"E9 freeze check: {'PASS' if freeze.passed else 'FAIL'} "
        f"({freeze.n_files} files hashed, {freeze.n_mismatch} changed or missing).",
        "",
        "| corpus | scope | questions | agree | disagree | miss | derived policy |",
        "|---|---|---|---|---|---|---|",
    ]
    for replay in report.corpora:
        scope = "routed only" if replay.routed_only else "all"
        lines.append(
            f"| {replay.corpus_id} | {scope} | {replay.n_questions} | {replay.n_agree} | "
            f"{replay.n_disagree} | {replay.n_miss} | {replay.n_derived_policy} |"
        )
    for replay in report.corpora:
        lines += _exceptions(replay)
    return "\n".join(lines) + "\n"


def _exceptions(replay: CorpusReplay) -> list[str]:
    """One line per disagreeing or missed question of a corpus; empty when all agree."""
    rows = [r for r in replay.rows if r.agreement is not Agreement.AGREE]
    if not rows:
        return []
    lines = ["", f"## {replay.corpus_id}: questions that did not agree", ""]
    for row in rows:
        detail = (
            f"cache miss at tier {row.missing_tier}"
            if row.agreement is Agreement.MISS
            else "differs in " + ", ".join(row.differs)
        )
        lines.append(f"- {row.question_id}: {detail}")
    return lines
