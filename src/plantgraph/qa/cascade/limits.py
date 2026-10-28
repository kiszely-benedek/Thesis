"""The two time-limit settings V2T is measured under (ADR-0061, status of 2026-10-27).

The agent tier and every other V2T choice are shared; the settings differ in two numbers only:
how long one Cypher query may run, and what limits one question's total time.

- **A**: the Cypher query timeout is 30 s and a question gets 120 s in total; an answer that
  arrives later counts as no answer.
- **B**: the Cypher query timeout is 120 s and a question has no deadline. A 900 s *hang
  guard* stays, so a stuck call cannot block a run for ever; a question that hits it fails.

A setting is applied in two places: the harness (the Cypher timeout is in the strategy params
file, the deadline is `--question-deadline-s`) and the evaluation here (`cutoff_s`, so a stored
run is scored the way a live run would have been). `run_problems` checks that the two agree.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from plantgraph.qa.cascade.checks import LoadedRun
from plantgraph.qa.final_answer_variants import V2T_TEMPLATE_PATH
from plantgraph.qa.strategies.cypher_rag import LINES_NAME


class LimitSetting(BaseModel):
    """One setting: Cypher timeout plus exactly one of a question deadline or a hang guard."""

    model_config = ConfigDict(frozen=True)

    name: Literal["A", "B"]
    cypher_timeout_s: float
    #: Setting A: total seconds one question may take; later answers count as wrong.
    question_deadline_s: float | None = None
    #: Setting B: the only limit; a question slower than this is a hung question and fails.
    hang_guard_s: float | None = None

    @model_validator(mode="after")
    def _exactly_one_limit(self) -> LimitSetting:
        if (self.question_deadline_s is None) == (self.hang_guard_s is None):
            raise ValueError(
                f"expected exactly one of question_deadline_s and hang_guard_s for setting "
                f"{self.name}, found deadline={self.question_deadline_s}, guard={self.hang_guard_s}"
            )
        return self

    @property
    def cutoff_s(self) -> float:
        """The latency above which an answer does not count (deadline for A, guard for B)."""
        limit = self.question_deadline_s if self.hang_guard_s is None else self.hang_guard_s
        assert limit is not None  # the validator guarantees one of the two
        return limit


SETTING_A = LimitSetting(name="A", cypher_timeout_s=30.0, question_deadline_s=120.0)
SETTING_B = LimitSetting(name="B", cypher_timeout_s=120.0, hang_guard_s=900.0)
SETTINGS: dict[str, LimitSetting] = {s.name: s for s in (SETTING_A, SETTING_B)}

_TEMPLATE_KEY = V2T_TEMPLATE_PATH.name


def run_problems(setting: LimitSetting, runs: Mapping[str, LoadedRun]) -> list[str]:
    """Ways the stored runs do not match `setting`; empty when they do."""
    problems: list[str] = []
    for tier, run in runs.items():
        problems += _timeout_problems(setting, tier, run)
        problems += _deadline_problems(setting, tier, run)
    hashes = {tier: run.config.prompt_hashes.get(_TEMPLATE_KEY) for tier, run in runs.items()}
    if None in hashes.values() or len(set(hashes.values())) > 1:
        problems.append(
            f"expected every V2T tier to record the same sha256 of {_TEMPLATE_KEY}, found {hashes}"
        )
    return problems


def _timeout_problems(setting: LimitSetting, tier: str, run: LoadedRun) -> list[str]:
    if run.tier.strategy != LINES_NAME:
        return []
    params = run.config.strategies.get(LINES_NAME, {})
    if params.get("timeout_s") == setting.cypher_timeout_s:
        return []
    return [
        f"tier {tier!r}: expected Cypher timeout_s {setting.cypher_timeout_s:g} for setting "
        f"{setting.name}, found {params.get('timeout_s')!r}"
    ]


def _deadline_problems(setting: LimitSetting, tier: str, run: LoadedRun) -> list[str]:
    deadline = run.config.question_deadline_s
    if deadline is None or deadline >= setting.cutoff_s:
        return []  # a longer deadline than the limit is harmless: later answers are cut offline
    return [
        f"tier {tier!r}: its {deadline:g} s question deadline is shorter than setting "
        f"{setting.name}'s {setting.cutoff_s:g} s limit, so it cut answers the setting would keep"
    ]
