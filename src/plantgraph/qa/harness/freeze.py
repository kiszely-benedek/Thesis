"""Freezing a run's configuration before its first call (ADR-0014; `qa-system.md` §4, §11).

"Freezing" means `run_config.json` is written once, before any model call, and
a later resume must match it. A **reported** run (one whose numbers may be
cited in the thesis) is refused unless everything its numbers depend on is
already known.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from plantgraph.llm.models import ContextWall
from plantgraph.qa.models import RunConfig

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

#: `RunConfig` fields that may differ between the original run and a resume or
#: replay of it: they say when, where and how the run was started, not what it measures.
_FIELDS_ALLOWED_TO_CHANGE = {
    "created_at",
    "git_commit",
    "git_dirty",
    "allow_paid_calls",
    "max_spend_usd",
}


def prompt_hashes() -> dict[str, str]:
    """Sha256 of every prompt template, by file name, so a prompt edit shows in the record."""
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_PROMPTS_DIR.glob("*.txt"))
    }


def question_set_sha256(question_files: list[Path]) -> str:
    """Sha256 over the questions files' bytes, concatenated in the order given."""
    digest = hashlib.sha256()
    for path in question_files:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_git_state(repo_root: Path) -> tuple[str, bool]:
    """The current commit hash and whether the working tree has uncommitted changes.

    Read-only git: `rev-parse` and `status --porcelain`.

    Raises:
        RuntimeError: git is unavailable or `repo_root` is not a repository.
    """
    commit = _git(repo_root, "rev-parse", "HEAD").strip()
    dirty = bool(_git(repo_root, "status", "--porcelain").strip())
    return commit, dirty


def _git(repo_root: Path, *args: str) -> str:
    command = ["git", *args]
    try:
        completed = subprocess.run(
            command, cwd=repo_root, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(
            f"expected `{' '.join(command)}` to work in {repo_root}: {error}"
        ) from error
    return completed.stdout


def check_reportable(config: RunConfig) -> None:
    """Refuse a `reported` run whose frozen record is incomplete (gate G2, §13.3).

    Raises:
        ValueError: listing every missing piece, so one message fixes the config.
    """
    if not config.reported:
        return
    problems = _missing_for_reported(config)
    if problems:
        raise ValueError(
            f"run {config.run_id!r} is reported but its frozen config is incomplete: "
            + "; ".join(problems)
        )


def _missing_for_reported(config: RunConfig) -> list[str]:
    problems: list[str] = []
    if not config.prompt_hashes:
        problems.append("no prompt hashes")
    if not config.question_set_sha256:
        problems.append("no question-set hash")
    if not config.strategies:
        problems.append("no strategies")
    if config.context_wall is None:
        problems.append("no context wall (run the pilot's wall probe first)")
    else:
        problems.extend(_wall_problems(config, config.context_wall))
    return problems


def _wall_problems(config: RunConfig, wall: ContextWall) -> list[str]:
    # a wall measured for another model says nothing about this one
    if wall.pin_hash != config.answer_pin.pin_hash():
        return [f"the context wall was measured for pin {wall.pin_hash!r}, not the answer pin"]
    return []


def differing_fields(frozen: RunConfig, requested: RunConfig) -> list[str]:
    """Names of the measured fields in which a resume's config differs from the frozen one."""
    frozen_values = frozen.model_dump(mode="json", exclude=_FIELDS_ALLOWED_TO_CHANGE)
    requested_values = requested.model_dump(mode="json", exclude=_FIELDS_ALLOWED_TO_CHANGE)
    return [name for name in frozen_values if frozen_values[name] != requested_values[name]]
