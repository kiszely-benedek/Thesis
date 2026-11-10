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

_QA_DIR = Path(__file__).resolve().parents[1]
_PACKAGE_DIR = _QA_DIR.parent
_PROMPTS_DIR = _QA_DIR / "prompts"

#: Python modules (paths under `qa/`) whose code decides the text a model is sent. The prompt
#: templates are hashed already; these build the rest of the prompt around them, so an edit here
#: changes the prompt just as a template edit does. A module that only routes, scores or
#: logs is deliberately absent: it cannot change what the model reads.
PROMPT_BUILDING_MODULES: tuple[str, ...] = (
    # Cypher schema paragraphs shown to the query-writing model
    "schema_text.py",
    "schema_text_lines.py",
    # plant text in the prompt: serialization, sheet rendering, and the cut when it is too long
    "serialize.py",
    "context_render.py",
    "context_budget.py",
    # the shared final-answer step and the choice between F1's and V2T's template
    "final_answer.py",
    "final_answer_variants.py",
    # the optional drawing-reading primer and the unit-router prompt
    "primer.py",
    "unit_router.py",
    # agent: system prompt, tool list text, first guess, and how tool results read as text
    "agent/prompts.py",
    "agent/tool_text.py",
    "agent/seed.py",
    "plant_api/results.py",
    "plant_api/line_render.py",
    # agent behaviour that decides which prompts exist and what they contain: the loop and its
    # actions (what a step may do, when it stops), the strategies and parameters that build it,
    # and the tool registry (the tool list and arguments the model is told about)
    "agent/loop.py",
    "agent/actions.py",
    "agent/models.py",
    "agent/strategies.py",
    "plant_api/tool_registry.py",
    # what a tool call returns: the merged plant the tools walk (items, line view, traversal,
    # contraction of repeated drawings and off-page connectors) and the primitives built on it
    "plant_api/primitives.py",
    "plant_api/traversal.py",
    "plant_api/item_graph.py",
    "plant_api/line_graph.py",
    "plant_api/contraction.py",
    "plant_api/model.py",
    # strategies that fill a template: the Cypher prompts (incl. the repair prompt and row
    # rendering) and the context strategies that choose and assemble the plant text
    "strategies/cypher_rag.py",
    "strategies/cypher_rag_lines.py",
    "strategies/context_rag.py",
    "strategies/hierarchical.py",
    "strategies/hierarchical_need.py",
    # Cypher path: what a generated query may do and what the model reads back of a refused or
    # slow one (guard, row/result types), and the tag check that rewrites or flags tags
    "cypher.py",
    "cypher_guard.py",
    "tag_check.py",
    "class_vocabulary.py",
    # which part of the plant the context strategies pick: named anchors in the question, the
    # sheets between them, the in-memory graph, and the need label that chooses the program
    "anchors.py",
    "sheet_selection.py",
    "routing.py",
    "graph_view.py",
    "need/context.py",
    "need/programs.py",
    "need/rules.py",
    "need/labels.py",
)

#: Prompt-building modules outside `qa/` (paths under the `plantgraph` package). The line view
#: shapes the line-view tool text, yet lives in `graph/`. Hash keys start with `plantgraph/`.
PROMPT_BUILDING_MODULES_OUTSIDE_QA: tuple[str, ...] = ("graph/line_view.py",)

#: `RunConfig` fields that may differ between the original run and a resume or
#: replay of it: they say when, where and how the run was started, not what it measures.
_FIELDS_ALLOWED_TO_CHANGE = {
    "created_at",
    "git_commit",
    "git_dirty",
    "allow_paid_calls",
    "max_spend_usd",
}

#: Fields added after runs already existed. An older `run_config.json` holds them empty, and an
#: empty frozen value means "not recorded", so a resume is not compared on them.
_FIELDS_COMPARED_ONLY_WHEN_FROZEN = ("code_hashes", "corpus_ingest_sha256")


def prompt_hashes() -> dict[str, str]:
    """Sha256 of every prompt template, by file name, so a prompt edit shows in the record."""
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_PROMPTS_DIR.glob("*.txt"))
    }


def code_hashes() -> dict[str, str]:
    """Sha256 of every prompt-building module: names under `qa/`, plus `plantgraph/...` outside it.

    Raises:
        FileNotFoundError: a listed module is gone; the list must follow the rename.
    """
    listed = {name: _QA_DIR / name for name in PROMPT_BUILDING_MODULES}
    listed |= {
        f"plantgraph/{name}": _PACKAGE_DIR / name for name in PROMPT_BUILDING_MODULES_OUTSIDE_QA
    }
    hashes: dict[str, str] = {}
    for name, path in listed.items():
        if not path.is_file():
            raise FileNotFoundError(f"expected prompt-building module {path} to exist; found none")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def corpus_ingest_hashes(corpus_ids: list[str], corpora_root: Path) -> dict[str, str]:
    """Sha256 of each corpus's `ingest.json` (the plant every question is asked about).

    Raises:
        FileNotFoundError: a corpus has no `ingest.json` under `corpora_root`.
    """
    hashes: dict[str, str] = {}
    for corpus_id in corpus_ids:
        path = corpora_root / corpus_id / "ingest.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"expected {path} to exist for corpus {corpus_id!r}; found none"
            )
        hashes[corpus_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


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
    skipped = _FIELDS_ALLOWED_TO_CHANGE | _fields_not_recorded(frozen)
    frozen_values = frozen.model_dump(mode="json", exclude=skipped)
    requested_values = requested.model_dump(mode="json", exclude=skipped)
    return [name for name in frozen_values if frozen_values[name] != requested_values[name]]


def _fields_not_recorded(frozen: RunConfig) -> set[str]:
    """Optional fields the frozen config holds empty: an older run, nothing to compare."""
    return {name for name in _FIELDS_COMPARED_ONLY_WHEN_FROZEN if not getattr(frozen, name)}


def changed_inputs(config: RunConfig, corpora_root: Path) -> list[str]:
    """What the config recorded about code and corpora that no longer matches the disk.

    Empty hash fields (an older config) are not checked. Names read `code:<module>`
    or `corpus:<id>`.
    """
    return _changed_code(config) + _changed_corpora(config, corpora_root)


def _changed_code(config: RunConfig) -> list[str]:
    if not config.code_hashes:
        return []
    now = code_hashes()
    names = sorted(set(now) | set(config.code_hashes))
    return [f"code:{name}" for name in names if now.get(name) != config.code_hashes.get(name)]


def _changed_corpora(config: RunConfig, corpora_root: Path) -> list[str]:
    if not config.corpus_ingest_sha256:
        return []
    recorded = config.corpus_ingest_sha256
    now = corpus_ingest_hashes(list(recorded), corpora_root)
    return [
        f"corpus:{corpus_id}" for corpus_id in recorded if now[corpus_id] != recorded[corpus_id]
    ]
