"""What the infrastructure report reads: the files the run script leaves behind.

Layout (written by `data/runs/cv1/run_infra.sh`):

```
<ingest-root>/<corpus>/rep<k>/ingest.json     one IngestResult per ingest repeat
<probe-root>/<corpus>/rep<k>.json             one StartupProbe per timing repeat
<probe-root>/<corpus>/memory.json             the MemoryProbe (one per corpus)
<runs-root>/<run>/                            a harness run directory, replays included
<runs-root>/<run>/replay_check.txt            "identical", "different" or "cache_miss"
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.infra.cypher_replay import REPLAY_META_FILE, CypherReplayMeta
from plantgraph.infra.environment import RunEnvironment
from plantgraph.infra.probe_models import MemoryProbe, StartupProbe
from plantgraph.infra.report_models import ReferencePrice, RowBasis
from plantgraph.ingest.models import IngestResult
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.models import RunConfig

#: The outcome of comparing a replay's `answers.jsonl` with its source run's, byte for byte.
ReplayStatus = Literal["identical", "different", "cache_miss"]

REPLAY_CHECK_FILE = "replay_check.txt"


class CorpusData(BaseModel):
    """All corpus-level measurements of one corpus: ingest repeats, probe repeats, memory."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    ingests: list[IngestResult]
    startups: list[StartupProbe]
    memory: MemoryProbe | None


class RunData(BaseModel):
    """What the report needs from one run directory (a replay, or an old run)."""

    model_config = ConfigDict(frozen=True)

    role: str
    corpus_id: str
    run_id: str
    basis: RowBasis
    strategy: str
    #: `None` for an old run, which has no replay to compare.
    replay_status: ReplayStatus | None
    allow_paid_calls: bool
    timings: list[TimingRow]
    environments: list[RunEnvironment]
    #: Sum of the answers' recorded total cost, and how many answers lacked a cost.
    answers_cost_usd: float
    n_cost_missing: int
    #: Sum of the answers' recorded model latency (final call plus retrieval calls).
    llm_latency_s: float


class ReportInputs(BaseModel):
    """Everything `build_infra_report` needs, already parsed."""

    model_config = ConfigDict(frozen=True)

    corpora: list[CorpusData]
    runs: list[RunData]
    price: ReferencePrice | None


def load_corpus_data(corpus_id: str, ingest_root: Path, probe_root: Path) -> CorpusData:
    """Read the ingest and probe repeats of one corpus.

    Raises:
        FileNotFoundError: no ingest repeat or no timing probe exists for the corpus.
    """
    ingests = [
        IngestResult.model_validate_json(path.read_text(encoding="utf-8"))
        for path in _sorted_files(ingest_root / corpus_id, "rep*/ingest.json")
    ]
    startups = [
        StartupProbe.model_validate_json(path.read_text(encoding="utf-8"))
        for path in _sorted_files(probe_root / corpus_id, "rep*.json")
    ]
    memory_path = probe_root / corpus_id / "memory.json"
    memory = (
        MemoryProbe.model_validate_json(memory_path.read_text(encoding="utf-8"))
        if memory_path.is_file()
        else None
    )
    return CorpusData(corpus_id=corpus_id, ingests=ingests, startups=startups, memory=memory)


def _sorted_files(folder: Path, pattern: str) -> list[Path]:
    files = sorted(folder.glob(pattern))
    if not files:
        raise FileNotFoundError(f"expected files matching {pattern} in {folder}, found none")
    return files


def load_run_data(
    runs_root: Path, run_name: str, role: str, corpus_id: str, basis: RowBasis
) -> RunData:
    """Read a run directory; a replay must carry its recorded byte-identity result.

    Raises:
        FileNotFoundError: a replay has no `replay_check.txt`, or the run has no config.
        ValueError: the check file holds an unknown word, or the run has not exactly one strategy.
    """
    run_dir = RunDir(runs_root / run_name)
    config = RunConfig.model_validate_json(run_dir.config_path.read_text(encoding="utf-8"))
    if len(config.strategies) != 1:
        raise ValueError(
            f"expected one strategy in run {run_name}, found {sorted(config.strategies)}"
        )
    rows = run_dir.read_rows()
    costs = [row.total_cost_usd for row in rows]
    return RunData(
        role=role,
        corpus_id=corpus_id,
        run_id=run_name,
        basis=basis,
        strategy=next(iter(config.strategies)),
        replay_status=_read_replay_status(run_dir.path) if basis == "replay" else None,
        allow_paid_calls=config.allow_paid_calls,
        timings=_read_jsonl(run_dir.timings_path, TimingRow),
        environments=_read_jsonl(run_dir.environment_path, RunEnvironment),
        answers_cost_usd=sum(cost for cost in costs if cost is not None),
        n_cost_missing=sum(cost is None for cost in costs),
        llm_latency_s=sum(row.total_llm_latency_s for row in rows),
    )


def _read_replay_status(run_path: Path) -> ReplayStatus:
    check_path = run_path / REPLAY_CHECK_FILE
    if not check_path.is_file():
        raise FileNotFoundError(
            f"expected {check_path} (the run script writes it after comparing the replay "
            "with its source), found none; a replay without it cannot be trusted"
        )
    word = check_path.read_text(encoding="utf-8").strip()
    if word not in get_args(ReplayStatus):
        raise ValueError(
            f"expected one of {get_args(ReplayStatus)} in {check_path}, found {word!r}"
        )
    return cast(ReplayStatus, word)


def _read_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [model.model_validate_json(line) for line in text.splitlines() if line.strip()]


def load_price(path: Path | None) -> ReferencePrice | None:
    """The hand-filled price file, or `None` when none is given or the file does not exist."""
    if path is None or not path.is_file():
        return None
    return ReferencePrice.model_validate_json(path.read_text(encoding="utf-8"))


class ReportRequest(BaseModel):
    """Where the report's files are and which runs to read (the CLI options, parsed)."""

    model_config = ConfigDict(frozen=True)

    ingest_root: Path
    probe_root: Path
    runs_root: Path
    #: Corpora with corpus-level measurements (ingest and probe), e.g. D100, D1000, D4000.
    corpora: list[str]
    #: Corpora that were replayed with questions (D4000 has none).
    compute_corpora: list[str]
    #: Role -> run name template with `{c}` for the corpus, e.g. `INF-CYPL-{c}`.
    replay_templates: dict[str, str]
    #: Role -> original run name template, used only if the role's replay is not usable.
    old_run_templates: dict[str, str]
    old_runs_root: Path
    #: Role -> name template of a database-only replay (`infra-cypher-replay`); it takes the
    #: place of the role's full replay and old run.
    db_replay_templates: dict[str, str] = Field(default_factory=dict)
    price_json: Path | None


def load_report_inputs(request: ReportRequest) -> ReportInputs:
    """Read every measurement the request names.

    Raises:
        FileNotFoundError: a listed corpus or replay has no files (see the loaders).
    """
    corpora = [
        load_corpus_data(corpus, request.ingest_root, request.probe_root)
        for corpus in request.corpora
    ]
    runs = [
        _load_db_replay(request, role, template, corpus)
        for corpus in request.compute_corpora
        for role, template in request.db_replay_templates.items()
    ] + [
        _load_role_run(request, role, template, corpus)
        for corpus in request.compute_corpora
        for role, template in request.replay_templates.items()
    ]
    return ReportInputs(corpora=corpora, runs=runs, price=load_price(request.price_json))


def _load_role_run(request: ReportRequest, role: str, template: str, corpus: str) -> RunData:
    """The replay, or the original run if the replay missed or differs and an original is named."""
    name = template.format(c=corpus)
    old_template = request.old_run_templates.get(role)
    try:
        replay = load_run_data(request.runs_root, name, role, corpus, "replay")
    except FileNotFoundError:
        if old_template is None:
            raise
        return _load_old_run(request, role, old_template, corpus)
    if replay.replay_status != "identical" and old_template is not None:
        return _load_old_run(request, role, old_template, corpus)
    return replay


def _load_old_run(request: ReportRequest, role: str, template: str, corpus: str) -> RunData:
    return load_run_data(request.old_runs_root, template.format(c=corpus), role, corpus, "old_run")


def _load_db_replay(request: ReportRequest, role: str, template: str, corpus: str) -> RunData:
    return load_db_replay_data(
        request.runs_root, template.format(c=corpus), request.old_runs_root, role, corpus
    )


def load_db_replay_data(
    runs_root: Path, run_name: str, source_runs_root: Path, role: str, corpus_id: str
) -> RunData:
    """Read a database-only replay: its timings, and cost and model latency from its source run.

    Raises:
        FileNotFoundError: the replay folder has no `db_replay.json`.
        ValueError: the replay does not time exactly the source run's questions.
    """
    folder = runs_root / run_name
    meta_path = folder / REPLAY_META_FILE
    if not meta_path.is_file():
        raise FileNotFoundError(
            f"expected {meta_path} (written by infra-cypher-replay), found none"
        )
    meta = CypherReplayMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
    source_rows = RunDir(source_runs_root / meta.source_run).read_rows()
    timings = _read_jsonl(folder / "timings.jsonl", TimingRow)
    if [t.question_id for t in timings] != [r.question_id for r in source_rows]:
        raise ValueError(
            f"expected {run_name} to time the {len(source_rows)} questions of {meta.source_run} "
            f"in order, found {len(timings)} timing rows that differ"
        )
    costs = [row.total_cost_usd for row in source_rows]
    return RunData(
        role=role,
        corpus_id=corpus_id,
        run_id=run_name,
        basis="db_replay",
        strategy=meta.strategy,
        replay_status=None,
        allow_paid_calls=False,  # no model is called
        timings=timings,
        environments=_read_jsonl(folder / "environment.jsonl", RunEnvironment),
        answers_cost_usd=sum(cost for cost in costs if cost is not None),
        n_cost_missing=sum(cost is None for cost in costs),
        llm_latency_s=sum(row.total_llm_latency_s for row in source_rows),
    )
