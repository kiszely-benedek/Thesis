"""Loading one tier's stored run and checking it can be joined with the reference tier's run.

Two runs may be joined per question only if they answered the very same questions about the
very same plant, under the same shared prompts. Any difference is a refusal, never a warning.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import TypeAdapter

from plantgraph.qa.cascade.models import TierSpec
from plantgraph.qa.harness.freeze import question_set_sha256
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.models import CorpusRecord, Question, QuestionResult, RunConfig

#: Prompt files every tier shares; strategy-only ones (e.g. the query prompt) may differ.
SHARED_PROMPTS = ("final_answer.txt", "legend_plant.txt", "primer_pid_v1.txt")


class JoinRefused(ValueError):
    """The runs cannot be joined; the message names every field that differs."""


@dataclass(frozen=True)
class LoadedRun:
    """One tier's stored run, restricted to one corpus and to the tier's strategy."""

    tier: TierSpec
    config: RunConfig
    record: CorpusRecord
    rows: dict[str, QuestionResult]
    #: question id -> digest of (id, text), for the questions this run was asked.
    question_digests: dict[str, str]
    #: sha256 of the questions file this run was started from, as the config recorded it.
    questions_file_matches_config: bool
    #: question id -> local compute seconds from `timings.jsonl`; empty when the run has none.
    local_compute_s: dict[str, float] = field(default_factory=dict)


def question_digest(question: Question) -> str:
    """Sha256 over a question's id and text; gold columns are deliberately left out."""
    return hashlib.sha256(f"{question.question_id}\n{question.text}".encode()).hexdigest()


def load_questions_file(questions_root: Path, corpus_id: str) -> tuple[Path, list[Question]]:
    """The questions file of one corpus under `questions_root`, and its parsed rows."""
    path = questions_path(questions_root, corpus_id)
    if not path.exists():
        raise JoinRefused(f"expected a questions file at {path}, found none")
    return path, load_questions(path, corpus_id)


def load_run(tier: TierSpec, run_dir: Path, questions_root: Path, corpus_id: str) -> LoadedRun:
    """Read a run's config, corpus record and this tier's rows.

    Raises:
        JoinRefused: the run is not a single-corpus, single-repeat run of `corpus_id`.
    """
    run = RunDir(run_dir)
    if not run.config_path.exists() or not run.corpora_path.exists():
        raise JoinRefused(f"expected run_config.json and corpora.json in {run_dir}, found none")
    config = RunConfig.model_validate_json(run.config_path.read_text(encoding="utf-8"))
    if config.corpora != [corpus_id] or config.repeats != 1:
        raise JoinRefused(
            f"expected {run_dir.name} to be a one-corpus ({corpus_id!r}), one-repeat run, "
            f"found corpora {config.corpora} with {config.repeats} repeats"
        )
    path, questions = load_questions_file(questions_root, corpus_id)
    rows = _rows_of_strategy(run.read_rows(), tier, run_dir)
    return LoadedRun(
        tier=tier,
        config=config,
        record=_corpus_record(run, corpus_id),
        rows=rows,
        question_digests={q.question_id: question_digest(q) for q in questions},
        questions_file_matches_config=question_set_sha256([path]) == config.question_set_sha256,
        local_compute_s=_local_compute_by_question(run, tier),
    )


def _local_compute_by_question(run: RunDir, tier: TierSpec) -> dict[str, float]:
    """Local compute per question of this tier's strategy; a resumed question's last line wins."""
    if not run.timings_path.exists():
        return {}
    timings = [
        TimingRow.model_validate_json(line)
        for line in run.timings_path.read_text(encoding="utf-8").splitlines()
    ]
    return {t.question_id: t.local_compute_s for t in timings if t.strategy == tier.strategy}


def _corpus_record(run: RunDir, corpus_id: str) -> CorpusRecord:
    records = TypeAdapter(list[CorpusRecord]).validate_json(
        run.corpora_path.read_text(encoding="utf-8")
    )
    for record in records:
        if record.corpus_id == corpus_id:
            return record
    raise JoinRefused(
        f"expected a corpus record for {corpus_id!r} in {run.corpora_path}, found none"
    )


def _rows_of_strategy(
    rows: list[QuestionResult], tier: TierSpec, run_dir: Path
) -> dict[str, QuestionResult]:
    own = [row for row in rows if row.strategy == tier.strategy]
    wrong_repeat = [row.question_id for row in own if row.repeat != 0]
    if wrong_repeat:
        raise JoinRefused(
            f"expected repeat 0 only in {run_dir.name}, found repeat > 0 for {wrong_repeat[:3]}"
        )
    return {row.question_id: row for row in own}


def compatibility_problems(
    run: LoadedRun, reference: LoadedRun, reference_digests: dict[str, str]
) -> list[str]:
    """Every way `run` differs from the reference tier's run; empty when they can be joined."""
    name = run.tier.name
    problems = _setup_problems(name, run, reference)
    if not run.questions_file_matches_config:
        problems.append(
            f"{name}: its questions file no longer matches the run's question_set_sha256"
        )
    for question_id, digest in run.question_digests.items():
        if reference_digests.get(question_id) != digest:
            problems.append(
                f"{name}: question {question_id!r} differs in id or text from the reference"
            )
    unknown = sorted(set(run.rows) - set(run.question_digests))
    if unknown:
        problems.append(f"{name}: rows for questions not in its questions file, e.g. {unknown[:3]}")
    return problems


def _setup_problems(name: str, run: LoadedRun, reference: LoadedRun) -> list[str]:
    """Differences in plant, primer, shared prompts and pin."""
    problems: list[str] = []
    if run.record.source_graph_hash != reference.record.source_graph_hash:
        problems.append(f"{name}: source_graph_hash differs from the reference tier")
    if run.config.primer != reference.config.primer:
        problems.append(
            f"{name}: primer is {run.config.primer}, reference has {reference.config.primer}"
        )
    for prompt in SHARED_PROMPTS:
        if run.config.prompt_hashes.get(prompt) != reference.config.prompt_hashes.get(prompt):
            problems.append(f"{name}: prompt hash of {prompt} differs from the reference tier")
    if run.config.answer_pin.pin_hash() != run.tier.pin_sha256:
        problems.append(f"{name}: the run's answer pin does not match the tier's pin_sha256")
    return problems
