"""The unchanged-path check (ADR-0060 point 1): which system-side files differ from the F1 freeze.

*F1* is the commit at which the system that produced v1's numbers was frozen. ADR-0053 checked an
allow-list of changed paths; for v2 the check is the reverse: a fixed list of **system-side** paths
(code that decides what a model is asked) must show no change since F1, except six named files that
carry the corpus's class list to the final answer step (RM-T1, commit `dc19941`).
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

_QA = "src/plantgraph/qa/"
#: Directories whose every file is system-side.
SYSTEM_DIRECTORIES = (
    f"{_QA}strategies/",
    f"{_QA}agent/",
    f"{_QA}plant_api/",
    f"{_QA}prompts/",
    f"{_QA}cascade/",
    f"{_QA}need/",
    f"{_QA}harness/",
    "src/plantgraph/llm/",
    "src/plantgraph/store/",
)
#: Single modules that are system-side.
_SYSTEM_MODULE_NAMES = (
    "serialize schema_text neo4j_view cypher graph_view final_answer primer fit scoring "
    "context_render context_budget anchors routing sheet_selection unit_router local_timer"
).split()
SYSTEM_MODULES = tuple(f"{_QA}{name}.py" for name in _SYSTEM_MODULE_NAMES)
#: Inside `harness/` these decide what the gold answer is, not what the model sees.
GOLD_SIDE_FILES = tuple(f"{_QA}harness/{name}.py" for name in ("gold", "family_meta", "need_gold"))
#: The six files RM-T1 changed so a v2 corpus's own class list reaches the final answer step.
NAMED_EXCEPTIONS = (
    f"{_QA}final_answer.py",
    f"{_QA}class_vocabulary.py",
    f"{_QA}strategies/base.py",
    f"{_QA}harness/attempt.py",
    f"{_QA}harness/attempt_models.py",
    f"{_QA}harness/runner.py",
)


def is_system_side(path: str) -> bool:
    """Whether `path` (repo-relative, forward slashes) is on the system-side list."""
    if path in GOLD_SIDE_FILES:
        return False
    return path in SYSTEM_MODULES or path.startswith(SYSTEM_DIRECTORIES)


def unexpected_changes(changed: Iterable[str]) -> list[str]:
    """The changed paths that are system-side and not one of the six named exceptions."""
    return sorted(p for p in changed if is_system_side(p) and p not in NAMED_EXCEPTIONS)


def _git(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"expected `git {' '.join(args)}` to succeed, found: {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def changed_since(repo: Path, commit: str) -> list[str]:
    """Files under `src/` that differ from `commit` in the working tree, new files included.

    Read-only git: `diff --name-only` (committed and uncommitted edits), `ls-files --others`.
    """
    edited = _git(repo, "diff", "--name-only", commit, "--", "src")
    new = _git(repo, "ls-files", "--others", "--exclude-standard", "--", "src")
    return sorted(set(edited) | set(new))


def check_paths(repo: Path, commit: str) -> list[str]:
    """The system-side files that changed since `commit` without being named exceptions."""
    return unexpected_changes(changed_since(repo, commit))
