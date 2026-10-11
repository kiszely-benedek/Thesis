"""The report's own accuracy statement: checks M1..M7 of the design note, section 8.

Each check reads the parsed inputs and returns a `SelfCheck`; none changes a number.
"""

from __future__ import annotations

from plantgraph.infra.environment import RunEnvironment
from plantgraph.infra.report_inputs import CorpusData, ReportInputs, RunData
from plantgraph.infra.report_models import CorpusFootprintRow, SelfCheck
from plantgraph.ingest.models import IngestResult

#: The slowest clock step a timing may have; `perf_counter` on Windows is 1e-7 s.
MAX_CLOCK_RESOLUTION_S = 1e-6

#: Timer overhead allowed when the parts of a question's time are added up.
PARTS_TOLERANCE_S = 0.001


def run_all_checks(inputs: ReportInputs, footprints: list[CorpusFootprintRow]) -> list[SelfCheck]:
    """M1..M7 in order."""
    replays = [run for run in inputs.runs if run.basis == "replay"]
    timed = [run for run in inputs.runs if run.basis != "old_run"]  # replays and db-only replays
    return [
        _replays_identical(replays),
        _clock(inputs, timed),
        _parts_add_up(timed),
        _repeat_spread(footprints),
        _counts_match(inputs.corpora),
        _two_size_sources(footprints),
        _no_spend(timed),
    ]


def _outcome(name: str, problems: list[str], ok_detail: str) -> SelfCheck:
    if problems:
        return SelfCheck(name=name, status="fail", detail="; ".join(problems))
    return SelfCheck(name=name, status="pass", detail=ok_detail)


def _replays_identical(replays: list[RunData]) -> SelfCheck:
    bad = [
        f"{run.run_id} is {run.replay_status}"
        for run in replays
        if run.replay_status != "identical"
    ]
    return _outcome(
        "M1 replay answers byte-identical to the source run",
        [*bad, *(["no replay was given"] if not replays else [])],
        f"{len(replays)} of {len(replays)} replays identical",
    )


def _all_environments(inputs: ReportInputs) -> list[tuple[str, RunEnvironment | None]]:
    named: list[tuple[str, RunEnvironment | None]] = []
    for corpus in inputs.corpora:
        named += [(f"ingest {corpus.corpus_id}", i.environment) for i in corpus.ingests]
        named += [(f"probe {corpus.corpus_id}", p.environment) for p in corpus.startups]
        if corpus.memory is not None:
            named.append((f"memory probe {corpus.corpus_id}", corpus.memory.environment))
    for run in inputs.runs:
        named += [(run.run_id, environment) for environment in run.environments]
    return named


def _clock(inputs: ReportInputs, timed: list[RunData]) -> SelfCheck:
    problems: list[str] = []
    for label, environment in _all_environments(inputs):
        if environment is None:
            problems.append(f"{label} has no environment record")
        elif environment.clock_resolution_s > MAX_CLOCK_RESOLUTION_S:
            problems.append(f"{label} clock step {environment.clock_resolution_s:g} s")
    for run in timed:
        wrong = sum(row.clock != "perf_counter" for row in run.timings)
        if wrong:
            problems.append(f"{run.run_id} has {wrong} rows not timed with perf_counter")
    return _outcome(
        "M2 clock resolution",
        problems,
        f"every record has a clock step of at most {MAX_CLOCK_RESOLUTION_S:g} s "
        "and every replay row was timed with perf_counter",
    )


def count_part_violations(run: RunData) -> int:
    """Rows where the parts exceed the whole: db + graph API > local, or server > client time."""
    violations = 0
    for row in run.timings:
        parts_too_big = row.db_client_s + row.graph_api_s > row.local_compute_s + PARTS_TOLERANCE_S
        server_too_big = row.db_server_s > row.db_client_s + PARTS_TOLERANCE_S
        violations += parts_too_big or server_too_big
    return violations


def _parts_add_up(timed: list[RunData]) -> SelfCheck:
    counts = {run.run_id: count_part_violations(run) for run in timed}
    problems = [f"{run_id}: {n} rows" for run_id, n in counts.items() if n]
    total_rows = sum(len(run.timings) for run in timed)
    return _outcome(
        "M3 parts add up (db + graph API <= local; server <= client)",
        problems,
        f"0 violations in {total_rows} rows (tolerance {PARTS_TOLERANCE_S * 1000:g} ms)",
    )


def _repeat_spread(footprints: list[CorpusFootprintRow]) -> SelfCheck:
    flagged = [
        f"{row.corpus_id} {name} (x{spread.ratio:.2f})"
        for row in footprints
        for name, spread in row.quantities.items()
        if spread.flagged and spread.ratio is not None
    ]
    if flagged:
        return SelfCheck(
            name="M4 repeat spread (max/min within x1.5)",
            status="flag",
            detail="repeats disagree by more than x1.5: " + ", ".join(flagged),
        )
    return SelfCheck(
        name="M4 repeat spread (max/min within x1.5)",
        status="pass",
        detail="every repeated quantity stays within x1.5",
    )


def _ingest_count_problems(corpus_id: str, ingest: IngestResult) -> list[str]:
    counts = ingest.counts
    problems: list[str] = []
    footprint = ingest.store_footprint
    if footprint is None:
        return [f"{corpus_id} has no store footprint to compare with the load plan"]
    if (footprint.n_nodes, footprint.n_relationships) != (counts.n_nodes, counts.n_relationships):
        problems.append(
            f"{corpus_id} database holds {footprint.n_nodes}/{footprint.n_relationships} "
            f"nodes/relationships, plan {counts.n_nodes}/{counts.n_relationships}"
        )
    report = ingest.load_report
    if report is not None and (report.nodes_written, report.relationships_written) != (
        counts.n_nodes,
        counts.n_relationships,
    ):
        problems.append(f"{corpus_id} load wrote a different count than the plan")
    return problems


def _counts_match(corpora: list[CorpusData]) -> SelfCheck:
    problems: list[str] = []
    for corpus in corpora:
        for ingest in corpus.ingests:
            problems += _ingest_count_problems(corpus.corpus_id, ingest)
        if len({i.counts.model_dump_json() for i in corpus.ingests}) > 1:
            problems.append(f"{corpus.corpus_id} repeats built different corpora")
    return _outcome(
        "M5 right corpus, right size",
        problems,
        "database counts equal the load plan and the load report in every repeat",
    )


def _two_size_sources(footprints: list[CorpusFootprintRow]) -> SelfCheck:
    notes = [f"{row.corpus_id}: {note}" for row in footprints for note in row.notes]
    if notes:
        return SelfCheck(name="M6 two size sources", status="flag", detail=" | ".join(notes))
    return SelfCheck(
        name="M6 two size sources",
        status="pass",
        detail="bytes on disk are primary; the server metric agrees or is absent",
    )


def _no_spend(timed: list[RunData]) -> SelfCheck:
    problems: list[str] = []
    for run in timed:
        spent = sum(row.spent_usd for row in run.timings)
        if run.allow_paid_calls or spent > 0:
            problems.append(f"{run.run_id} allow_paid_calls={run.allow_paid_calls}, spent ${spent}")
    return _outcome("M7 zero spend", problems, "no replay allowed paid calls, total spend $0")
