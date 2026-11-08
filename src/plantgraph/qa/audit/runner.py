"""Run a plan of audit rows through the judge, under the spend ledger.

One row at a time, in plan order, so the cap stops the run at the cheapest-to-lose end of the
budget order. Every judged row is appended to `verdicts.jsonl`; a restart skips rows already
there. Rows that cannot be judged are listed in the summary, never dropped silently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import CacheMiss, ChatResponse, ProviderError
from plantgraph.qa.audit.budget import WORST_CASE_CALL_USD, LedgerLine, SpendLedger
from plantgraph.qa.audit.excerpt import ExcerptTooLarge, QuestionSubgraph, render_excerpt
from plantgraph.qa.audit.judge import build_prompt, call_judge, parse_reply
from plantgraph.qa.audit.models import AuditItem, AuditRecord
from plantgraph.qa.audit.sources import LoadedRun, make_judge_input

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """What happened to each row of the plan."""

    judged: int = 0
    already_done: int = 0
    #: Replay mode and no cached reply: the row would be a paid call.
    not_run: int = 0
    stopped_by_cap: bool = False
    #: Row key and reason for rows that could not be judged.
    failed: list[tuple[str, str]] = field(default_factory=list)
    #: Prompt length of every row that got as far as a prompt.
    prompt_chars: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class RunContext:
    """Everything `run_plan` reads or writes besides the plan."""

    runs: dict[str, LoadedRun]
    subgraphs: dict[str, QuestionSubgraph]
    client: ChatClient
    ledger: SpendLedger
    verdicts_path: Path
    stage: str
    stage_cap_usd: float | None = None


def item_key(item: AuditItem) -> str:
    """Identity of a row in the verdicts file and the ledger."""
    row = item.row
    return f"{row.run_id}|{row.strategy}|{row.question_id}"


def read_records(verdicts_path: Path) -> list[AuditRecord]:
    """Every judged row on file."""
    if not verdicts_path.exists():
        return []
    text = verdicts_path.read_text(encoding="utf-8")
    return [AuditRecord.model_validate_json(line) for line in text.splitlines() if line]


def run_plan(items: list[AuditItem], context: RunContext) -> RunSummary:
    """Judge the rows in order until the plan, the stage cap or the hard cap ends the run."""
    summary = RunSummary()
    done = {item_key(record.item) for record in read_records(context.verdicts_path)}
    for item in items:
        if item_key(item) in done:
            summary.already_done += 1
            continue
        if not context.ledger.allows(WORST_CASE_CALL_USD, context.stage, context.stage_cap_usd):
            summary.stopped_by_cap = True
            break
        _judge_one(item, context, summary)
    return summary


def _judge_one(item: AuditItem, context: RunContext, summary: RunSummary) -> None:
    key = item_key(item)
    row = item.row
    subgraph = context.subgraphs.get(row.question_id)
    if subgraph is None:
        summary.failed.append((key, "no plant excerpt exported for this question"))
        return
    run = context.runs[row.run_id]
    try:
        excerpt = render_excerpt(subgraph)
    except ExcerptTooLarge as error:
        summary.failed.append((key, str(error)))
        return
    judge_input = make_judge_input(
        run.questions[row.question_id], run.results[(row.question_id, row.strategy)], excerpt
    )
    prompt_chars = len(build_prompt(judge_input))
    summary.prompt_chars.append(prompt_chars)
    try:
        response = call_judge(context.client, judge_input, run_id=row.run_id, question_id=key)
    except CacheMiss:
        summary.not_run += 1
        return
    except ProviderError as error:
        summary.failed.append((key, f"provider error: {error}"))
        return
    _record(item, response, prompt_chars, context, summary)


def _record(
    item: AuditItem,
    response: ChatResponse,
    prompt_chars: int,
    context: RunContext,
    summary: RunSummary,
) -> None:
    paid = _paid_usd(response)
    context.ledger.record(LedgerLine(stage=context.stage, item_key=item_key(item), paid_usd=paid))
    try:
        reply = parse_reply(response.text)
    except ValueError as error:  # the money is spent and booked; the row stays unjudged
        summary.failed.append((item_key(item), str(error)))
        return
    record = AuditRecord(
        item=item,
        reply=reply,
        prompt_chars=prompt_chars,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        paid_usd=paid,
    )
    with context.verdicts_path.open("ab") as handle:
        handle.write((record.model_dump_json() + "\n").encode("utf-8"))
    summary.judged += 1


def _paid_usd(response: ChatResponse) -> float:
    """Money this call cost; a live call with no reported cost is charged the worst case."""
    if response.from_cache:
        return 0.0
    if response.cost_usd is None:
        logger.warning("judge call reported no cost; charging the worst case")
        return WORST_CASE_CALL_USD
    return response.cost_usd
